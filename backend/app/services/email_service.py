from __future__ import annotations

import smtplib
from email.message import EmailMessage

from backend.app.core.config import get_settings


def smtp_configured() -> bool:
    settings = get_settings()
    return bool(settings.smtp_host and settings.smtp_user and settings.smtp_password and settings.smtp_from)


def send_login_code(email: str, code: str) -> None:
    settings = get_settings()
    if not smtp_configured():
        return

    message = EmailMessage()
    message["Subject"] = "Mag2Read 登录验证码"
    message["From"] = settings.smtp_from or settings.smtp_user or ""
    message["To"] = email
    message.set_content(
        "\n".join(
            [
                "你正在登录 Mag2Read。",
                "",
                f"验证码：{code}",
                "",
                "验证码 5 分钟内有效。如果不是你本人操作，可以忽略这封邮件。",
            ]
        )
    )

    with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port) as smtp:
        smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)
