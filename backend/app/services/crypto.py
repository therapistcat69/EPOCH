import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings
from app.errors import AppError


def _fernet() -> Fernet:
    secret = get_settings().session_secret
    if not secret:
        raise AppError("OAUTH_NOT_CONFIGURED", "SESSION_SECRET is not configured on the server.", 503)
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        # SESSION_SECRET changed: stored tokens are unreadable, so the user must log in again.
        raise AppError("TOKEN_INVALID", "Please reconnect your YouTube account.", 401)
