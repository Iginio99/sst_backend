from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class LoginRequest(BaseModel):
    # Usamos str para permitir dominios internos (.local) usados en los seeds
    email: str
    password: str


class LoginChallenge(BaseModel):
    pending_token: str
    otp_expires_in: int
    masked_email: str


class OTPVerifyRequest(BaseModel):
    pending_token: str
    code: str = Field(min_length=4, max_length=6)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class PermissionOut(BaseModel):
    code: str
    module: str
    action: str
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RoleOut(BaseModel):
    id: int
    name: str
    code: str
    description: Optional[str] = None
    permissions: List[PermissionOut] = []

    model_config = ConfigDict(from_attributes=True)


class RoleCreateRequest(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    permission_codes: List[str] = []


class RoleUpdateRequest(RoleCreateRequest):
    pass


class PermissionCreateRequest(BaseModel):
    code: str
    module: str
    action: str
    description: Optional[str] = None


class AssignPermissionsRequest(BaseModel):
    permission_codes: List[str]


class AssignUserRolesRequest(BaseModel):
    role_codes: List[str]


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    roles: List[str]
    permissions: List[str]


class AuthResponse(BaseModel):
    user: UserOut
    tokens: TokenResponse


class RefreshRequest(BaseModel):
    refresh_token: str
