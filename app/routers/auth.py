"""Authentication routes."""
import logging
import json
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    decode_token, hash_token, generate_verification_token, generate_password_reset_token
)
from app.core.deps import (
    get_current_user, get_current_user_optional, get_current_active_user,
    get_client_ip, get_user_agent
)
from app.core.config import settings
from app.models.user import User, Session, AuditLog, UserRole
from app.schemas.auth import (
    UserRegister, UserLogin, UserResponse, TokenResponse, AuthResponse,
    MessageResponse, PasswordResetRequest, PasswordReset, PasswordChange,
    EmailVerify, ResendVerification, UserProfile
)
from app.services.email import EmailService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Rate limiting constants
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30


async def log_audit(
    db: AsyncSession,
    action: str,
    user_id: Optional[int] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[dict] = None,
    success: bool = True,
    error_message: Optional[str] = None
):
    """Log an audit event."""
    audit = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details=json.dumps(details) if details else None,
        success=success,
        error_message=error_message
    )
    db.add(audit)
    await db.commit()


@router.post("/register", response_model=MessageResponse)
async def register(
    data: UserRegister,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user."""
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == data.email.lower()))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Generate verification token
    verify_token = generate_verification_token()
    token_expires = datetime.utcnow() + timedelta(hours=settings.EMAIL_VERIFY_TOKEN_EXPIRE_HOURS)
    
    # Create user
    user = User(
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        username=data.username,
        email_verify_token=verify_token,
        email_verify_token_expires=token_expires
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Log audit
    await log_audit(
        db,
        action="register",
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request)
    )
    
    # Send verification email
    await EmailService.send_verification_email(user.email, verify_token)
    
    return MessageResponse(message="Registration successful. Please check your email to verify your account.")


@router.post("/login", response_model=AuthResponse)
async def login(
    data: UserLogin,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Login with email and password."""
    # Find user
    result = await db.execute(select(User).where(User.email == data.email.lower()))
    user = result.scalar_one_or_none()
    
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    if not user:
        await log_audit(
            db, action="login_failed", ip_address=ip_address,
            user_agent=user_agent, success=False, error_message="User not found"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Check if account is locked
    if user.is_locked():
        await log_audit(
            db, action="login_failed", user_id=user.id,
            ip_address=ip_address, user_agent=user_agent,
            success=False, error_message="Account locked"
        )
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account is locked. Try again later."
        )
    
    # Verify password
    if not verify_password(data.password, user.password_hash):
        # Increment failed attempts
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
        await db.commit()
        
        await log_audit(
            db, action="login_failed", user_id=user.id,
            ip_address=ip_address, user_agent=user_agent,
            success=False, error_message="Invalid password"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Check if account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )
    
    # Reset failed attempts on successful login
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.utcnow()
    
    # Create tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    # Store session
    session = Session(
        user_id=user.id,
        token_hash=hash_token(access_token),
        refresh_token_hash=hash_token(refresh_token),
        user_agent=user_agent,
        ip_address=ip_address,
        expires_at=datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        refresh_expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(session)
    await db.commit()
    
    # Log audit
    await log_audit(
        db, action="login", user_id=user.id,
        ip_address=ip_address, user_agent=user_agent
    )
    
    # Set cookies for web clients
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )
    
    return AuthResponse(
        user=UserResponse.model_validate(user),
        tokens=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Logout current user."""
    # Clear cookies
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    
    # Log audit
    await log_audit(
        db, action="logout", user_id=user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request)
    )
    
    return MessageResponse(message="Logged out successfully")


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token."""
    # Get refresh token from cookie or body
    refresh_token_value = request.cookies.get("refresh_token")
    if not refresh_token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required"
        )
    
    # Decode token
    payload = decode_token(refresh_token_value)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Get user
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Create new access token
    access_token = create_access_token(data={"sub": str(user.id)})
    
    # Set cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    data: EmailVerify,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Verify email address with token."""
    result = await db.execute(
        select(User).where(User.email_verify_token == data.token)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification token"
        )
    
    if user.email_verify_token_expires and user.email_verify_token_expires < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token expired"
        )
    
    # Mark email as verified
    user.is_email_verified = True
    user.email_verified_at = datetime.utcnow()
    user.email_verify_token = None
    user.email_verify_token_expires = None
    await db.commit()
    
    # Log audit
    await log_audit(
        db, action="email_verified", user_id=user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request)
    )
    
    return MessageResponse(message="Email verified successfully")


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    data: ResendVerification,
    db: AsyncSession = Depends(get_db)
):
    """Resend verification email."""
    result = await db.execute(select(User).where(User.email == data.email.lower()))
    user = result.scalar_one_or_none()
    
    if not user:
        # Don't reveal if email exists
        return MessageResponse(message="If the email exists, a verification email has been sent.")
    
    if user.is_email_verified:
        return MessageResponse(message="Email is already verified.")
    
    # Generate new token
    verify_token = generate_verification_token()
    user.email_verify_token = verify_token
    user.email_verify_token_expires = datetime.utcnow() + timedelta(hours=settings.EMAIL_VERIFY_TOKEN_EXPIRE_HOURS)
    await db.commit()
    
    # Send email
    await EmailService.send_verification_email(user.email, verify_token)
    
    return MessageResponse(message="If the email exists, a verification email has been sent.")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    data: PasswordResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Request password reset."""
    result = await db.execute(select(User).where(User.email == data.email.lower()))
    user = result.scalar_one_or_none()
    
    if not user:
        # Don't reveal if email exists
        return MessageResponse(message="If the email exists, a password reset link has been sent.")
    
    # Generate reset token
    reset_token = generate_password_reset_token()
    user.password_reset_token = reset_token
    user.password_reset_token_expires = datetime.utcnow() + timedelta(hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS)
    await db.commit()
    
    # Send email
    await EmailService.send_password_reset_email(user.email, reset_token)
    
    # Log audit
    await log_audit(
        db, action="password_reset_requested", user_id=user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request)
    )
    
    return MessageResponse(message="If the email exists, a password reset link has been sent.")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    data: PasswordReset,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Reset password with token."""
    result = await db.execute(
        select(User).where(User.password_reset_token == data.token)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token"
        )
    
    if user.password_reset_token_expires and user.password_reset_token_expires < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token expired"
        )
    
    # Update password
    user.password_hash = hash_password(data.new_password)
    user.password_reset_token = None
    user.password_reset_token_expires = None
    user.failed_login_attempts = 0
    user.locked_until = None
    await db.commit()
    
    # Log audit
    await log_audit(
        db, action="password_reset", user_id=user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request)
    )
    
    return MessageResponse(message="Password reset successfully")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    data: PasswordChange,
    request: Request,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Change password for logged-in user."""
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    user.password_hash = hash_password(data.new_password)
    await db.commit()
    
    # Log audit
    await log_audit(
        db, action="password_changed", user_id=user.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request)
    )
    
    return MessageResponse(message="Password changed successfully")


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(
    user: User = Depends(get_current_active_user)
):
    """Get current user's profile."""
    return UserProfile.model_validate(user)

