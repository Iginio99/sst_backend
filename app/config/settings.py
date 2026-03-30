from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    APP_ENV: str = "development"
    APP_NAME: str = "SST Backend"
    SECRET_KEY: str = "change-me"
    DATABASE_URL: str = "postgresql+psycopg2://sst_user:sstpass123@localhost:5433/sstdb"
    DISABLE_2FA: bool = False
    FRONTEND_URLS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8080,http://127.0.0.1:8080"
    LOCAL_ORIGIN_REGEX: str = r"https?://(localhost|127\.0\.0\.1)(:\d+)?$"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 15
    OTP_EXPIRE_MINUTES: int = 5
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str = "no-reply@sst.local"
    STORAGE_PROVIDER: str | None = None
    SUPABASE_PROJECT_ID: str | None = None
    SUPABASE_STORAGE_BUCKET: str | None = None
    SUPABASE_S3_ENDPOINT: str | None = None
    SUPABASE_S3_DIRECT_HOST: str | None = None
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    MAX_IMAGE_UPLOAD_MB: int = 5
    MAX_DOCUMENT_UPLOAD_MB: int = 20
    MAX_VIDEO_UPLOAD_MB: int = 200

    @property
    def cors_origins(self) -> list[str]:
        origins: list[str] = []
        for origin in self.FRONTEND_URLS.split(","):
            cleaned = origin.strip().rstrip("/")
            if cleaned:
                origins.append(cleaned)
        return origins

    @property
    def storage_enabled(self) -> bool:
        return bool(
            self.STORAGE_PROVIDER
            and self.SUPABASE_PROJECT_ID
            and self.SUPABASE_STORAGE_BUCKET
            and self.SUPABASE_S3_ENDPOINT
            and self.AWS_ACCESS_KEY_ID
            and self.AWS_SECRET_ACCESS_KEY
        )


settings = Settings()
