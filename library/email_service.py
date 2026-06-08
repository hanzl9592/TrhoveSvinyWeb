from __future__ import annotations

import os
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

try:
    from flask import current_app, has_app_context
except ImportError:  # pragma: no cover
    current_app = None

    def has_app_context() -> bool:  # type: ignore[override]
        return False


def _get_setting(name: str, default: str = "") -> str:
    if has_app_context() and current_app is not None:
        value = current_app.config.get(name, default)
        return "" if value is None else str(value)
    return os.environ.get(name, default)


def send_mailtrap_email(
    to_email: str,
    subject: str,
    text: str,
    *,
    category: str = "Integration Test",
) -> tuple[bool, str, str]:
    if requests is None:
        return False, "MAIL-API-00", "requests library missing"

    api_token = _get_setting("MAILTRAP_API_TOKEN").strip()
    if not api_token:
        return False, "MAIL-API-02", "MAILTRAP_API_TOKEN is not configured"

    sender_email = _get_setting("MAILTRAP_SENDER_EMAIL", "hello@demomailtrap.co").strip()
    sender_name = _get_setting("MAILTRAP_SENDER_NAME", "Mailtrap Test").strip()

    try:
        url = "https://send.api.mailtrap.io/api/send"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "from": {"email": sender_email, "name": sender_name},
            "to": [{"email": to_email}],
            "subject": subject,
            "text": text,
            "category": category,
        }
        response: Any = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 401:
            return False, "MAIL-API-04", "Unauthorized: Invalid API token"
        
        if response.status_code >= 400:
            error_detail = response.text or f"HTTP {response.status_code}"
            return False, "MAIL-API-01", error_detail
        
        return True, "MAIL-API-03", response.text or "Email sent successfully"
    except Exception as exc:  # pragma: no cover - external API failure path
        return False, "MAIL-API-01", str(exc)


def send_verification_email(to_email: str, verify_link: str, subject: str) -> tuple[bool, str, str]:
    return send_mailtrap_email(
        to_email=to_email,
        subject=subject,
        text=f"{verify_link}\n",
        category="Integration Test",
    )
