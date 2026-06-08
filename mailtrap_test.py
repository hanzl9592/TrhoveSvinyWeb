import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

if load_dotenv is not None:
    project_root = Path(__file__).resolve().parents[0]
    load_dotenv(project_root / ".env")

from library.email_service import send_mailtrap_email

to_email = os.environ.get("MAILTRAP_TEST_TO", "ondrejhanzl@seznam.cz").strip()
verify_link = "http://127.0.0.1:5000/auth/verify-email/test-token-abc123xyz"
subject = "Verify your library account"

ok, code, detail = send_mailtrap_email(
    to_email=to_email,
    subject=subject,
    text=f"Click to verify your email: {verify_link}\n",
    category="Integration Test",
)

if ok:
    print(f"✓ Success [{code}] sent to {to_email}")
    print(f"  Verification link: {verify_link}")
    print(f"  Response: {detail}")
else:
    print(f"✗ Failed [{code}]: {detail}")
