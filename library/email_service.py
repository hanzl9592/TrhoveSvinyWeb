from __future__ import annotations

import os
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

try:
    from flask import current_app, has_app_context, url_for
except ImportError:  # pragma: no cover
    current_app = None
    url_for = None  # type: ignore[assignment]

    def has_app_context() -> bool:  # type: ignore[override]
        return False


def _get_setting(name: str, default: str = "") -> str:
    if has_app_context() and current_app is not None:
        value = current_app.config.get(name, default)
        return "" if value is None else str(value)
    return os.environ.get(name, default)


def _logo_url() -> str:
    """Return an absolute URL for the school logo, usable inside emails."""
    try:
        if has_app_context() and url_for is not None:
            return url_for("static", filename="img/Sviny_znak_mesta.jpg", _external=True)
    except Exception:
        pass
    return ""


def _build_html_email(title: str, heading: str, body_html: str) -> str:
    logo_url = _logo_url()
    logo_block = (
        f'<img src="{logo_url}" alt="ZŠ Trhové Sviny" style="height:70px;width:auto;display:block;margin:0 auto 12px auto;">'
        if logo_url
        else ""
    )
    return f"""<!DOCTYPE html>
<html lang="cs">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#f0f4f8;font-family:Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background:#f0f4f8;padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="max-width:560px;background:#ffffff;border-radius:10px;
                      box-shadow:0 2px 12px rgba(0,0,0,0.08);overflow:hidden;">

          <!-- HEADER -->
          <tr>
            <td align="center"
                style="background:linear-gradient(135deg,#1a56a0 0%,#2d7dd2 100%);
                       padding:32px 24px 24px 24px;">
              {logo_block}
              <div style="color:#ffffff;font-size:13px;letter-spacing:1px;
                          text-transform:uppercase;opacity:0.85;margin-bottom:4px;">
                Základní škola
              </div>
              <div style="color:#ffffff;font-size:20px;font-weight:bold;letter-spacing:0.5px;">
                Trhové Sviny
              </div>
              <div style="margin-top:14px;width:40px;height:3px;
                          background:rgba(255,255,255,0.5);border-radius:2px;
                          display:inline-block;"></div>
            </td>
          </tr>

          <!-- BODY -->
          <tr>
            <td style="padding:36px 36px 28px 36px;">
              <h1 style="margin:0 0 20px 0;font-size:22px;color:#1a3a5c;
                         font-weight:bold;border-bottom:2px solid #e8f0fa;
                         padding-bottom:14px;">
                {heading}
              </h1>
              <div style="font-size:15px;color:#374151;line-height:1.7;">
                {body_html}
              </div>
            </td>
          </tr>

          <!-- FOOTER -->
          <tr>
            <td style="background:#f8fafd;border-top:1px solid #e2eaf5;
                       padding:20px 36px;text-align:center;">
              <p style="margin:0 0 6px 0;font-size:13px;font-weight:bold;color:#1a56a0;">
                Základní škola Trhové Sviny
              </p>
              <p style="margin:0;font-size:12px;color:#6b7280;line-height:1.8;">
                Trhové Sviny 5<br>
                📞 +420 380 311 183 &nbsp;|&nbsp; ✉️ trhovesviny@online.cz
              </p>
              <p style="margin:12px 0 0 0;font-size:11px;color:#9ca3af;">
                Tento e-mail byl vygenerován automaticky — neodpovídejte na něj.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def send_mailtrap_email(
    to_email: str,
    subject: str,
    text: str,
    *,
    html: str | None = None,
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
        payload: dict[str, Any] = {
            "from": {"email": sender_email, "name": sender_name},
            "to": [{"email": to_email}],
            "subject": subject,
            "text": text,
            "category": category,
        }
        if html:
            payload["html"] = html

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
    text = (
        f"Dobrý den,\n\n"
        f"pro dokončení registrace na portálu školní knihovny klikněte na odkaz níže:\n\n"
        f"{verify_link}\n\n"
        f"Platnost odkazu je 24 hodin.\n\n"
        f"Pokud jste si účet nezaložili vy, tento e-mail ignorujte.\n\n"
        f"Základní škola Trhové Sviny"
    )
    html = _build_html_email(
        title="Ověření e-mailové adresy",
        heading="Ověřte svou e-mailovou adresu",
        body_html=f"""
            <p>Dobrý den,</p>
            <p>děkujeme za registraci na portálu <strong>školní knihovny</strong>.
               Pro dokončení registrace prosím potvrďte svou e-mailovou adresu
               kliknutím na tlačítko níže.</p>
            <p style="text-align:center;margin:28px 0;">
              <a href="{verify_link}"
                 style="display:inline-block;background:#1a56a0;color:#ffffff;
                        font-size:15px;font-weight:bold;padding:13px 32px;
                        border-radius:6px;text-decoration:none;
                        letter-spacing:0.3px;">
                Ověřit e-mail
              </a>
            </p>
            <p style="font-size:13px;color:#6b7280;">
              Nebo zkopírujte tento odkaz do prohlížeče:<br>
              <a href="{verify_link}" style="color:#1a56a0;word-break:break-all;">{verify_link}</a>
            </p>
            <p style="font-size:13px;color:#6b7280;margin-top:20px;">
              Platnost odkazu je <strong>24 hodin</strong>.<br>
              Pokud jste si účet nezaložili vy, tento e-mail ignorujte.
            </p>
        """,
    )
    return send_mailtrap_email(
        to_email=to_email,
        subject=subject,
        text=text,
        html=html,
        category="Integration Test",
    )


def send_password_reset_email(to_email: str, reset_link: str, subject: str) -> tuple[bool, str, str]:
    text = (
        f"Dobrý den,\n\n"
        f"obdrželi jsme žádost o obnovu hesla k vašemu účtu.\n\n"
        f"Pro nastavení nového hesla klikněte na odkaz níže:\n\n"
        f"{reset_link}\n\n"
        f"Platnost odkazu je 2 hodiny.\n\n"
        f"Pokud jste o obnovu hesla nežádali, tento e-mail ignorujte.\n\n"
        f"Základní škola Trhové Sviny"
    )
    html = _build_html_email(
        title="Obnova hesla",
        heading="Obnova hesla",
        body_html=f"""
            <p>Dobrý den,</p>
            <p>obdrželi jsme žádost o <strong>obnovu hesla</strong>
               k vašemu účtu na portálu školní knihovny.</p>
            <p style="text-align:center;margin:28px 0;">
              <a href="{reset_link}"
                 style="display:inline-block;background:#1a56a0;color:#ffffff;
                        font-size:15px;font-weight:bold;padding:13px 32px;
                        border-radius:6px;text-decoration:none;
                        letter-spacing:0.3px;">
                Nastavit nové heslo
              </a>
            </p>
            <p style="font-size:13px;color:#6b7280;">
              Nebo zkopírujte tento odkaz do prohlížeče:<br>
              <a href="{reset_link}" style="color:#1a56a0;word-break:break-all;">{reset_link}</a>
            </p>
            <p style="font-size:13px;color:#6b7280;margin-top:20px;">
              Platnost odkazu je <strong>2 hodiny</strong>.<br>
              Pokud jste o obnovu hesla nežádali, tento e-mail ignorujte —
              váš účet je v bezpečí.
            </p>
        """,
    )
    return send_mailtrap_email(
        to_email=to_email,
        subject=subject,
        text=text,
        html=html,
        category="Integration Test",
    )
