import mailtrap as mt
import os
from pathlib import Path
from mailtrap.exceptions import AuthorizationError

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

if load_dotenv is not None:
    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(project_root / ".env")

token = os.environ.get("MAILTRAP_API_TOKEN", "").strip()
if not token:
    if os.environ.get("MAIL_PASSWORD", "").strip():
        raise RuntimeError(
            "MAILTRAP_API_TOKEN is missing. MAIL_PASSWORD is SMTP-only and cannot be used for Mailtrap API send()."
        )
    raise RuntimeError("Set MAILTRAP_API_TOKEN before running EmailTest.py")

mail = mt.Mail(
    sender=mt.Address(
        email=os.environ.get("MAILTRAP_SENDER_EMAIL", "hello@demomailtrap.co"),
        name=os.environ.get("MAILTRAP_SENDER_NAME", "Mailtrap Test"),
    ),
    to=[mt.Address(email=os.environ.get("MAILTRAP_TEST_TO", "ondrejhanzl@seznam.cz"))],
    subject="You are awesome!",
    text="Congrats for sending test email with Mailtrap!",
    category="Integration Test",
)

client = mt.MailtrapClient(token=token)
try:
    response = client.send(mail)
    print(response)
except AuthorizationError:
    raise RuntimeError(
        "Mailtrap API unauthorized. Use a valid Sending API token in MAILTRAP_API_TOKEN (not SMTP password)."
    )
