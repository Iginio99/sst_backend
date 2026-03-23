from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import settings
from app.core.middleware import JWTAuthMiddleware
from app.modules.auth.auth_router import router as auth_router
from app.modules.chat.chat_router import router as chat_router
from app.modules.checklist.checklist_router import router as checklist_router
from app.modules.training.training_router import router as training_router

app = FastAPI(title=settings.APP_NAME)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.LOCAL_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.add_middleware(
#     JWTAuthMiddleware,
#     excluded_paths={"/auth/login", "/auth/verify-otp", "/auth/refresh", "/health", "/docs", "/openapi.json"},
# )

app.include_router(auth_router)
app.include_router(training_router)
app.include_router(checklist_router)
app.include_router(chat_router)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "sst-backend"}
