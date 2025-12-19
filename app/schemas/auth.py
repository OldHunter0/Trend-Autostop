"""Pydantic schemas for authentication."""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime


# ============ Request Schemas ============

class UserRegister(BaseModel):
    """Schema for user registration."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    username: Optional[str] = Field(None, min_length=2, max_length=100)


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class PasswordResetRequest(BaseModel):
    """Schema for requesting password reset."""
    email: EmailStr


class PasswordReset(BaseModel):
    """Schema for resetting password."""
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class PasswordChange(BaseModel):
    """Schema for changing password (when logged in)."""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class EmailVerify(BaseModel):
    """Schema for email verification."""
    token: str


class ResendVerification(BaseModel):
    """Schema for resending verification email."""
    email: EmailStr


# ============ Response Schemas ============

class UserResponse(BaseModel):
    """Schema for user response (public info)."""
    id: int
    email: str
    username: Optional[str]
    role: str
    is_email_verified: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserProfile(BaseModel):
    """Schema for user profile (more details)."""
    id: int
    email: str
    username: Optional[str]
    role: str
    is_active: bool
    is_email_verified: bool
    email_verified_at: Optional[datetime]
    last_login_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Schema for token response."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int  # seconds


class AuthResponse(BaseModel):
    """Schema for authentication response."""
    user: UserResponse
    tokens: TokenResponse


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    success: bool = True


# ============ Admin Schemas ============

class UserListItem(BaseModel):
    """Schema for user list item (admin view)."""
    id: int
    email: str
    username: Optional[str]
    role: str
    is_active: bool
    is_email_verified: bool
    has_api_credentials: bool = False
    credentials_count: int = 0
    last_login_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema for updating user (admin)."""
    is_active: Optional[bool] = None
    role: Optional[str] = Field(None, pattern="^(user|admin)$")


class AuditLogResponse(BaseModel):
    """Schema for audit log response."""
    id: int
    user_id: Optional[int]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[int]
    ip_address: Optional[str]
    success: bool
    error_message: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

