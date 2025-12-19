"""Security utilities for encryption, hashing, and JWT."""
import base64
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from passlib.context import CryptContext
from jose import jwt, JWTError
from app.core.config import settings


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============ Password Hashing ============

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ============ JWT Token ============

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def hash_token(token: str) -> str:
    """Create a hash of a token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


# ============ Email Verification & Password Reset Tokens ============

def generate_verification_token() -> str:
    """Generate a secure random token for email verification."""
    return secrets.token_urlsafe(32)


def generate_password_reset_token() -> str:
    """Generate a secure random token for password reset."""
    return secrets.token_urlsafe(32)


# ============ API Key Encryption (Envelope Encryption) ============

def _get_master_fernet() -> Fernet:
    """Get Fernet instance using MASTER_KEY for envelope encryption."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"trend_autostop_master_salt",
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(settings.MASTER_KEY.encode()))
    return Fernet(key)


def generate_data_key() -> Tuple[bytes, str]:
    """
    Generate a new data key for envelope encryption.
    Returns: (raw_data_key, wrapped_data_key)
    """
    # Generate random data key
    raw_data_key = Fernet.generate_key()
    
    # Wrap (encrypt) the data key with master key
    master_fernet = _get_master_fernet()
    wrapped_data_key = master_fernet.encrypt(raw_data_key).decode()
    
    return raw_data_key, wrapped_data_key


def unwrap_data_key(wrapped_data_key: str) -> bytes:
    """Unwrap (decrypt) a data key using master key."""
    master_fernet = _get_master_fernet()
    return master_fernet.decrypt(wrapped_data_key.encode())


def encrypt_with_data_key(data: str, data_key: bytes) -> str:
    """Encrypt data using a data key."""
    fernet = Fernet(data_key)
    return fernet.encrypt(data.encode()).decode()


def decrypt_with_data_key(encrypted_data: str, data_key: bytes) -> str:
    """Decrypt data using a data key."""
    fernet = Fernet(data_key)
    return fernet.decrypt(encrypted_data.encode()).decode()


# ============ Legacy API Key Encryption (for backward compatibility) ============

def _get_fernet() -> Fernet:
    """Get Fernet instance for encryption/decryption (legacy)."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"trend_autostop_salt",
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(settings.SECRET_KEY.encode()))
    return Fernet(key)


def encrypt_api_key(api_key: str) -> str:
    """Encrypt API key for secure storage (legacy)."""
    fernet = _get_fernet()
    encrypted = fernet.encrypt(api_key.encode())
    return encrypted.decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt API key for use (legacy)."""
    fernet = _get_fernet()
    decrypted = fernet.decrypt(encrypted_key.encode())
    return decrypted.decode()

