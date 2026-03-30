import os
import re
from uuid import uuid4

import boto3
from botocore.client import Config
from fastapi import HTTPException, UploadFile, status

from app.config.settings import settings


class StorageService:
    def __init__(self) -> None:
        self._bucket = settings.SUPABASE_STORAGE_BUCKET
        self._project_id = settings.SUPABASE_PROJECT_ID
        self._endpoint_url = settings.SUPABASE_S3_DIRECT_HOST or settings.SUPABASE_S3_ENDPOINT
        self._client = None

        if settings.storage_enabled:
            self._client = boto3.client(
                "s3",
                endpoint_url=self._endpoint_url,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                config=Config(signature_version="s3v4"),
            )

    @property
    def enabled(self) -> bool:
        return self._client is not None and self._bucket is not None and self._project_id is not None

    def upload_lesson_asset(
        self,
        *,
        module_id: int,
        lesson_id: int,
        asset_kind: str,
        upload_file: UploadFile,
    ) -> dict:
        if not self.enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storage no configurado en el backend",
            )

        filename = upload_file.filename or f"{asset_kind}.bin"
        safe_name = self._sanitize_filename(filename)
        key = (
            f"training/modules/{module_id}/lessons/{lesson_id}/"
            f"{asset_kind}/{uuid4().hex}_{safe_name}"
        )

        extra_args = {}
        if upload_file.content_type:
            extra_args["ContentType"] = upload_file.content_type

        upload_file.file.seek(0, 2)
        size = upload_file.file.tell()
        upload_file.file.seek(0)
        self._client.upload_fileobj(
            upload_file.file,
            self._bucket,
            key,
            ExtraArgs=extra_args,
        )

        public_url = self._build_public_url(key)
        return {
            "key": key,
            "url": public_url,
            "mime_type": upload_file.content_type,
            "size_bytes": size,
            "original_filename": filename,
        }

    def delete_object(self, key: str | None) -> None:
        if not self.enabled or not key:
            return
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def _build_public_url(self, key: str) -> str:
        return f"https://{self._project_id}.supabase.co/storage/v1/object/public/{self._bucket}/{key}"

    def _sanitize_filename(self, filename: str) -> str:
        base, ext = os.path.splitext(filename)
        clean_base = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-") or "file"
        clean_ext = re.sub(r"[^A-Za-z0-9.]+", "", ext)
        return f"{clean_base}{clean_ext.lower()}"
