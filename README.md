# SST Backend

API FastAPI para autenticacion, capacitaciones, checklists y chat.

## Variables de entorno

Copia `.env.example` a `.env` y ajusta al menos:

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
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Antes de publicar, configura `SECRET_KEY`, `DATABASE_URL` y `FRONTEND_URLS` en el proveedor.
