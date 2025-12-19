"""Email service for sending verification and notification emails."""
import logging
import traceback
from typing import Optional, Tuple
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails."""
    
    @staticmethod
    def get_smtp_config() -> dict:
        """Get current SMTP configuration (for debugging)."""
        return {
            "host": settings.SMTP_HOST,
            "port": settings.SMTP_PORT,
            "user": settings.SMTP_USER[:3] + "***" if settings.SMTP_USER else None,
            "password_set": bool(settings.SMTP_PASSWORD),
            "from_email": settings.SMTP_FROM_EMAIL,
            "from_name": settings.SMTP_FROM_NAME,
        }
    
    @staticmethod
    async def send_email(
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Send an email.
        Returns: (success, error_message)
        """
        # Check SMTP configuration
        if not settings.SMTP_USER:
            error_msg = "SMTP_USER not configured"
            logger.warning(f"Email not sent to {to_email}: {error_msg}")
            return False, error_msg
        
        if not settings.SMTP_PASSWORD:
            error_msg = "SMTP_PASSWORD not configured"
            logger.warning(f"Email not sent to {to_email}: {error_msg}")
            return False, error_msg
        
        if not settings.SMTP_HOST:
            error_msg = "SMTP_HOST not configured"
            logger.warning(f"Email not sent to {to_email}: {error_msg}")
            return False, error_msg
        
        logger.info(f"Attempting to send email to {to_email} via {settings.SMTP_HOST}:{settings.SMTP_PORT}")
        
        try:
            message = MIMEMultipart("alternative")
            from_email = settings.SMTP_FROM_EMAIL or settings.SMTP_USER
            message["From"] = f"{settings.SMTP_FROM_NAME} <{from_email}>"
            message["To"] = to_email
            message["Subject"] = subject
            
            # Add text version if provided
            if text_content:
                message.attach(MIMEText(text_content, "plain"))
            
            # Add HTML version
            message.attach(MIMEText(html_content, "html"))
            
            # Send email with detailed logging
            logger.debug(f"Connecting to SMTP server {settings.SMTP_HOST}:{settings.SMTP_PORT}")
            
            await aiosmtplib.send(
                message,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USER,
                password=settings.SMTP_PASSWORD,
                start_tls=True
            )
            
            logger.info(f"✓ Email sent successfully to {to_email}")
            return True, None
            
        except aiosmtplib.SMTPAuthenticationError as e:
            error_msg = f"SMTP authentication failed: {e}"
            logger.error(f"✗ {error_msg}")
            return False, error_msg
            
        except aiosmtplib.SMTPConnectError as e:
            error_msg = f"Failed to connect to SMTP server: {e}"
            logger.error(f"✗ {error_msg}")
            return False, error_msg
            
        except aiosmtplib.SMTPException as e:
            error_msg = f"SMTP error: {e}"
            logger.error(f"✗ {error_msg}")
            return False, error_msg
            
        except Exception as e:
            error_msg = f"Unexpected error sending email: {type(e).__name__}: {e}"
            logger.error(f"✗ {error_msg}")
            logger.debug(traceback.format_exc())
            return False, error_msg
    
    @classmethod
    async def send_verification_email(cls, to_email: str, token: str) -> bool:
        """Send email verification email."""
        verify_url = f"{settings.BASE_URL}/auth/verify-email?token={token}"
        
        subject = "验证您的邮箱 - Trend-Autostop"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 8px 8px; }}
                .button {{ display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📈 Trend-Autostop</h1>
                </div>
                <div class="content">
                    <h2>验证您的邮箱</h2>
                    <p>感谢您注册 Trend-Autostop！请点击下方按钮验证您的邮箱地址：</p>
                    <p style="text-align: center;">
                        <a href="{verify_url}" class="button">验证邮箱</a>
                    </p>
                    <p>或者复制以下链接到浏览器：</p>
                    <p style="word-break: break-all; background: #eee; padding: 10px; border-radius: 4px;">
                        {verify_url}
                    </p>
                    <p>此链接将在 {settings.EMAIL_VERIFY_TOKEN_EXPIRE_HOURS} 小时后失效。</p>
                </div>
                <div class="footer">
                    <p>如果您没有注册 Trend-Autostop 账户，请忽略此邮件。</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        验证您的邮箱 - Trend-Autostop
        
        感谢您注册 Trend-Autostop！请访问以下链接验证您的邮箱地址：
        
        {verify_url}
        
        此链接将在 {settings.EMAIL_VERIFY_TOKEN_EXPIRE_HOURS} 小时后失效。
        
        如果您没有注册 Trend-Autostop 账户，请忽略此邮件。
        """
        
        success, error = await cls.send_email(to_email, subject, html_content, text_content)
        if not success:
            logger.warning(f"Failed to send verification email to {to_email}: {error}")
        return success
    
    @classmethod
    async def send_password_reset_email(cls, to_email: str, token: str) -> bool:
        """Send password reset email."""
        reset_url = f"{settings.BASE_URL}/auth/reset-password?token={token}"
        
        subject = "重置密码 - Trend-Autostop"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 8px 8px; }}
                .button {{ display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .warning {{ background: #fff3cd; border: 1px solid #ffc107; padding: 10px; border-radius: 4px; margin: 15px 0; }}
                .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📈 Trend-Autostop</h1>
                </div>
                <div class="content">
                    <h2>重置您的密码</h2>
                    <p>您请求重置 Trend-Autostop 账户的密码。请点击下方按钮设置新密码：</p>
                    <p style="text-align: center;">
                        <a href="{reset_url}" class="button">重置密码</a>
                    </p>
                    <p>或者复制以下链接到浏览器：</p>
                    <p style="word-break: break-all; background: #eee; padding: 10px; border-radius: 4px;">
                        {reset_url}
                    </p>
                    <div class="warning">
                        ⚠️ 此链接将在 {settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS} 小时后失效。
                    </div>
                </div>
                <div class="footer">
                    <p>如果您没有请求重置密码，请忽略此邮件，您的密码不会被更改。</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        重置密码 - Trend-Autostop
        
        您请求重置 Trend-Autostop 账户的密码。请访问以下链接设置新密码：
        
        {reset_url}
        
        此链接将在 {settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS} 小时后失效。
        
        如果您没有请求重置密码，请忽略此邮件，您的密码不会被更改。
        """
        
        success, error = await cls.send_email(to_email, subject, html_content, text_content)
        if not success:
            logger.warning(f"Failed to send password reset email to {to_email}: {error}")
        return success

