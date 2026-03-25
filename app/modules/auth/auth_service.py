from datetime import datetime, timedelta
import random
from typing import Iterable, List, Set

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session, joinedload

from app.config.settings import settings
from app.core.security import (
    create_access_token,
    create_pending_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.infrastructure.respository import get_db
from app.modules.auth.auth_schema import (
    AssignPermissionsRequest,
    AssignUserRolesRequest,
    PermissionCreateRequest,
    RoleCreateRequest,
    RoleUpdateRequest,
    TokenResponse,
    UserOut,
)
from app.modules.models import Permission, RefreshToken, Role, TwoFactorCode, User
from app.shared.email import send_email

bearer_scheme = HTTPBearer(auto_error=False)


def validate_password_policy(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña debe tener al menos 8 caracteres",
        )
    if not any(c.isupper() for c in password) or not any(c.islower() for c in password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña debe incluir mayusculas y minusculas",
        )
    if not any(c.isdigit() for c in password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña debe incluir al menos un numero",
        )


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def login(self, email: str, password: str) -> dict:
        user = self._get_user_with_relations(email=email)
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales invalidas")
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario inactivo")

        # Si 2FA está desactivado, saltamos OTP para entornos de prueba.
        if settings.APP_ENV.lower() == "uat" or settings.DISABLE_2FA or not user.two_factor_enabled:
            return self._build_auth_response(user)

        otp, _raw_code = self._create_otp(user)
        pending_token = create_pending_token(user.id, otp.id, settings.OTP_EXPIRE_MINUTES)
        return {
            "pending_token": pending_token,
            "otp_expires_in": settings.OTP_EXPIRE_MINUTES * 60,
            "masked_email": self._mask_email(user.email),
        }

    def verify_otp(self, pending_token: str, code: str) -> dict:
        payload = decode_token(pending_token, expected_type="pending")
        user_id = int(payload.get("sub"))
        otp_id = int(payload.get("otp_id"))

        otp = (
            self.db.query(TwoFactorCode)
            .filter(TwoFactorCode.id == otp_id, TwoFactorCode.user_id == user_id, TwoFactorCode.purpose == "login")
            .first()
        )
        if not otp:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OTP no encontrado")
        if otp.consumed_at or otp.expires_at < datetime.utcnow():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OTP expirado")
        if otp.code != hash_token(code):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Codigo incorrecto")

        otp.consumed_at = datetime.utcnow()
        user = self._get_user_with_relations(user_id=user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")
        user.last_login_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)

        return self._build_auth_response(user)

    def refresh_session(self, refresh_token: str) -> dict:
        hashed = hash_token(refresh_token)
        token_row = (
            self.db.query(RefreshToken)
            .options(joinedload(RefreshToken.user).joinedload(User.roles).joinedload(Role.permissions))
            .filter(RefreshToken.token == hashed, RefreshToken.revoked.is_(False))
            .first()
        )
        if not token_row:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalido")
        if token_row.expires_at < datetime.utcnow():
            token_row.revoked = True
            self.db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expirado")

        user = token_row.user
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")

        token_row.revoked = True
        self.db.commit()
        return self._build_auth_response(user)

    def me(self, user: User) -> dict:
        return {"user": self._serialize_user(user)}

    def list_roles(self) -> List[Role]:
        return self.db.query(Role).options(joinedload(Role.permissions)).all()

    def list_permissions(self) -> List[Permission]:
        return self.db.query(Permission).all()

    def create_role(self, payload: RoleCreateRequest) -> Role:
        role = Role(name=payload.name, code=payload.code, description=payload.description)
        self.db.add(role)
        self.db.commit()
        self.db.refresh(role)
        if payload.permission_codes:
            self._sync_role_permissions(role, payload.permission_codes)
        return self._get_role_with_permissions(role.id)

    def update_role(self, role_id: int, payload: RoleUpdateRequest) -> Role:
        role = self._get_role_with_permissions(role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado")
        role.name = payload.name
        role.code = payload.code
        role.description = payload.description
        self.db.commit()
        if payload.permission_codes is not None:
            self._sync_role_permissions(role, payload.permission_codes)
        return self._get_role_with_permissions(role_id)

    def create_permission(self, payload: PermissionCreateRequest) -> Permission:
        perm = Permission(code=payload.code, module=payload.module, action=payload.action, description=payload.description)
        self.db.add(perm)
        self.db.commit()
        self.db.refresh(perm)
        return perm

    def assign_permissions(self, role_id: int, payload: AssignPermissionsRequest) -> Role:
        role = self._get_role_with_permissions(role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado")
        self._sync_role_permissions(role, payload.permission_codes)
        return self._get_role_with_permissions(role_id)

    def assign_roles_to_user(self, user_id: int, payload: AssignUserRolesRequest) -> User:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
        roles = self.db.query(Role).filter(Role.code.in_(payload.role_codes)).all()
        if not roles:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Roles no encontrados")
        user.roles = roles
        self.db.commit()
        self.db.refresh(user)
        return self._get_user_with_relations(user_id=user.id)

    # -------------------------
    # Helpers
    # -------------------------
    def _create_otp(self, user: User) -> tuple[TwoFactorCode, str]:
        # limpiar tokens vencidos previos
        self.db.query(TwoFactorCode).filter(
            TwoFactorCode.user_id == user.id,
            TwoFactorCode.purpose == "login",
            TwoFactorCode.expires_at < datetime.utcnow(),
        ).delete()
        code = f"{random.randint(0, 999999):06d}"
        hashed_code = hash_token(code)
        expires_at = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
        otp = TwoFactorCode(
            user_id=user.id,
            code=hashed_code,
            purpose="login",
            sent_to=user.email,
            expires_at=expires_at,
        )
        self.db.add(otp)
        self.db.commit()
        self.db.refresh(otp)
        try:
            send_email(
                recipient=user.email,
                subject="Codigo de acceso SST",
                body=f"Tu codigo OTP es: {code}. Expira en {settings.OTP_EXPIRE_MINUTES} minutos.",
            )
        except Exception as exc:  # pragma: no cover - SMTP depende de entorno
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"No se pudo enviar el correo OTP: {exc}",
            )
        return otp, code

    def _build_auth_response(self, user: User) -> dict:
        profile = self._serialize_user(user)
        access_payload = {
            "sub": str(user.id),
            "roles": profile.roles,
            "permissions": profile.permissions,
            "name": user.name,
        }
        access_token = create_access_token(access_payload, settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_raw, refresh_exp = create_refresh_token(user.id, settings.REFRESH_TOKEN_EXPIRE_DAYS)
        refresh_record = RefreshToken(
            user_id=user.id,
            token=hash_token(refresh_raw),
            expires_at=refresh_exp,
            revoked=False,
        )
        self.db.add(refresh_record)
        self.db.commit()
        expires_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

        return {
            "user": profile,
            "tokens": TokenResponse(
                access_token=access_token,
                refresh_token=refresh_raw,
                expires_in=expires_seconds,
            ),
        }

    def _serialize_user(self, user: User) -> UserOut:
        roles = [r.code for r in user.roles]
        permissions: Set[str] = set()
        for role in user.roles:
            for perm in role.permissions:
                permissions.add(perm.code)
        return UserOut(
            id=user.id,
            email=user.email,
            name=user.name,
            roles=roles,
            permissions=sorted(list(permissions)),
        )

    def _mask_email(self, email: str) -> str:
        name, _, domain = email.partition("@")
        if len(name) <= 2:
            return "***@" + domain
        return f"{name[0]}***{name[-1]}@{domain}"

    def _sync_role_permissions(self, role: Role, permission_codes: Iterable[str]) -> None:
        perms = self.db.query(Permission).filter(Permission.code.in_(list(permission_codes))).all()
        role.permissions = perms
        self.db.commit()
        self.db.refresh(role)

    def _get_user_with_relations(self, user_id: int | None = None, email: str | None = None) -> User | None:
        query = self.db.query(User).options(joinedload(User.roles).joinedload(Role.permissions))
        if user_id is not None:
            return query.filter(User.id == user_id).first()
        if email is not None:
            return query.filter(User.email == email).first()
        return None

    def _get_role_with_permissions(self, role_id: int) -> Role | None:
        return (
            self.db.query(Role)
            .options(joinedload(Role.permissions))
            .filter(Role.id == role_id)
            .first()
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Falta token")

    token = credentials.credentials
    try:
        payload = decode_token(token, expected_type="access")
    except HTTPException:
        raise
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido")

    service = AuthService(db)
    user = service._get_user_with_relations(user_id=int(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")
    return user


def require_roles(roles: List[str]):
    def wrapper(user: User = Depends(get_current_user)) -> User:
        user_roles = {r.code for r in user.roles}
        if not user_roles.intersection(set(roles)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rol no autorizado")
        return user

    return wrapper


def require_permissions(permissions: List[str]):
    def wrapper(user: User = Depends(get_current_user)) -> User:
        user_perms = {p.code for r in user.roles for p in r.permissions}
        if not set(permissions).issubset(user_perms):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes")
        return user

    return wrapper
