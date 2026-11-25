import os
import uuid
from fastapi import UploadFile, HTTPException, status
from app.core.config import settings

class StorageService:
    ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf", ".webp"}
    MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit

    @staticmethod
    def validate_file_signature(content: bytes, ext: str) -> None:
        """
        Validate actual binary file signature against claimed file extension.
        Rejects mismatched formats, executables, scripts, or disguised files.
        """
        if len(content) < 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content is empty or truncated.",
            )

        # Prohibit known malicious executable / script signatures regardless of claimed extension
        if content.startswith(b"MZ"):  # Windows PE / EXE / DLL
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security violation: Executable files are strictly prohibited.",
            )
        if content.startswith(b"\x7fELF"):  # Linux ELF executable
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security violation: Executable files are strictly prohibited.",
            )
        if content.startswith(b"#!") or content.lower().startswith(b"<?php") or content.lower().startswith(b"<script"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security violation: Script files are strictly prohibited.",
            )

        # Specific signature checks per extension
        if ext == ".pdf":
            # PDF must start with %PDF-
            if len(content) < 5 or not content.startswith(b"%PDF-"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="MIME mismatch: File does not match valid PDF binary signature.",
                )
        elif ext in [".jpg", ".jpeg"]:
            # JPEG starts with \xff\xd8\xff
            if len(content) < 3 or not content.startswith(b"\xff\xd8\xff"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="MIME mismatch: File does not match valid JPEG binary signature.",
                )
        elif ext == ".png":
            # PNG starts with \x89PNG\r\n\x1a\n
            if len(content) < 8 or not content.startswith(b"\x89PNG\r\n\x1a\n"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="MIME mismatch: File does not match valid PNG binary signature.",
                )
        elif ext == ".webp":
            # WebP starts with RIFF....WEBP
            if len(content) < 12 or not (content.startswith(b"RIFF") and content[8:12] == b"WEBP"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="MIME mismatch: File does not match valid WebP binary signature.",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file extension '{ext}'.",
            )

    @classmethod
    async def save_upload_file(cls, file: UploadFile, folder: str = "pods") -> str:
        filename = file.filename or "upload"
        _, ext = os.path.splitext(filename)
        ext = ext.lower()
        if ext not in cls.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type '{ext}'. Allowed: {sorted(list(cls.ALLOWED_EXTENSIONS))}",
            )

        content = await file.read()
        if len(content) > cls.MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds maximum allowed limit of {cls.MAX_FILE_SIZE_BYTES // (1024*1024)}MB.",
            )

        # Validate actual binary magic bytes
        cls.validate_file_signature(content, ext)

        target_dir = os.path.join(settings.UPLOAD_DIR, folder)
        os.makedirs(target_dir, exist_ok=True)

        unique_filename = f"{uuid.uuid4()}{ext}"
        filepath = os.path.join(target_dir, unique_filename)

        with open(filepath, "wb") as f:
            f.write(content)

        return f"/uploads/{folder}/{unique_filename}"

storage_service = StorageService()
