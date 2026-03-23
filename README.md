# SST Backend

API FastAPI para autenticacion, capacitaciones, checklists y chat.

## Variables de entorno

Copia `.env.example` a `.env` y ajusta al menos:

- `APP_ENV`
- `SECRET_KEY`
- `DATABASE_URL`
- `FRONTEND_URLS`

## Desarrollo local

```bash
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8010
```

## Despliegue

Usa estos comandos en un servicio Python tipo Render:

- Build command: `pip install -r requirements.txt`
- Pre-deploy command: `alembic upgrade head`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Antes de publicar, configura `SECRET_KEY`, `DATABASE_URL` y `FRONTEND_URLS` en el proveedor.

## Render / UAT

El repo ya incluye `render.yaml` y `.python-version`.

Con eso puedes desplegarlo como Blueprint:

1. En Render, entra a `New > Blueprint`.
2. Conecta `https://github.com/Iginio99/sst_backend`.
3. Render detectara `render.yaml` y creara un Web Service `sst-backend-uat`.
4. Durante la creacion, pega tu `DATABASE_URL` de UAT en el campo solicitado.

Despues del primer deploy, revisa estas variables en el servicio:

- `APP_ENV`: debe quedar en `uat`.
- `DISABLE_2FA`: queda en `true` para no exigir OTP por ahora.
- `FRONTEND_URLS`: cambia el valor local por la URL real de tu frontend cuando lo publiques.
- `DATABASE_URL`: si tu base tambien esta en Render, conviene usar la URL interna de Postgres desde la pantalla `Info` de la base para menor latencia.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`: si no configuras SMTP, el login con OTP no podra enviar correos.

Health check:

- `GET /health`
