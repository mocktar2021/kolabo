"""Encryption helpers for data at rest.

Verification documents are sensitive PII, so their bytes are encrypted with
Fernet before they are stored. In production the file bytes should live in
object storage with server side encryption; this module keeps the pilot honest
by never storing a raw document, and the same interface can wrap an object
store later.
"""
from cryptography.fernet import Fernet

from app.core.config import settings

_fernet = Fernet(settings.document_encryption_key.encode())


def encrypt_bytes(data: bytes) -> bytes:
    return _fernet.encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    return _fernet.decrypt(token)
