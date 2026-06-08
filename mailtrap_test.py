import mailtrap as mt
import os

# 1. Create the verification link
dummy_token = "abc123xyz789"
verification_link = f"http://localhost:3000/verify?token={dummy_token}"

mailtrap_token = (os.environ.get("MAILTRAP_API_TOKEN", "") or os.environ.get("MAIL_PASSWORD", "")).strip()
sender_email = os.environ.get("MAILTRAP_SENDER_EMAIL", "hello@demomailtrap.co").strip()
sender_name = os.environ.get("MAILTRAP_SENDER_NAME", "Knihovna ZS TS").strip()
to_email = os.environ.get("MAILTRAP_TEST_TO", "ondrejhanzl@seznam.cz").strip()

if not mailtrap_token:
  raise RuntimeError(
    "Missing Mailtrap token. Set MAILTRAP_API_TOKEN (or MAIL_PASSWORD fallback)."
  )

# 2. Design the verification email template
html_content = f"""
<html>
  <body>
    <h3>Vítej v knihovně ZŠ Trhové Sviny!</h3>
    <p>Děkujeme za registraci. Pro dokončení klikni na odkaz níže:</p>
    <p>
      <a href="{verification_link}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
        Potvrdit e-mailovou adresu
      </a>
    </p>
    <br>
    <p>Pokud jsi registraci neprováděl(a), můžeš tento e-mail ignorovat.</p>
  </body>
</html>
"""

# 3. Configure the email layout
mail = mt.Mail(
  sender=mt.Address(email=sender_email, name=sender_name),
  to=[mt.Address(email=to_email)],
    subject="Potvrzení registrace – Knihovna ZŠ Trhové Sviny",
    text=f"Dobrý den, pro potvrzení Vašeho e-mailu přejděte na: {verification_link}",
    html=html_content,
    category="Registration Verification",
)

# 4. Connect using your API token over standard web traffic (HTTPS)
client = mt.MailtrapClient(token=mailtrap_token)

try:
    response = client.send(mail)
    print("Success! Response from Mailtrap:", response)
except Exception as e:
    print("An error occurred while sending via API:", e)