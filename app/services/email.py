"""Email service for sending verification and notification emails."""
import logging
from typing import Optional
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails."""
    
    @staticmethod
    async def send_email(
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """Send an email."""
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            logger.warning("SMTP not configured, skipping email send")
            return False
        
        try:
            message = MIMEMultipart("alternative")
            message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL or settings.SMTP_USER}>"
            message["To"] = to_email
            message["Subject"] = subject
            
            # Add text version if provided
            if text_content:
                message.attach(MIMEText(text_content, "plain"))
            
            # Add HTML version
            message.attach(MIMEText(html_content, "html"))
            
            # Send email
            await aiosmtplib.send(
                message,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USER,
                password=settings.SMTP_PASSWORD,
                start_tls=True
            )
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
    
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
        
        return await cls.send_email(to_email, subject, html_content, text_content)
    
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
        
        return await cls.send_email(to_email, subject, html_content, text_content)

