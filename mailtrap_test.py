import mailtrap as mt

# 1. Create the verification link
dummy_token = "abc123xyz789"
verification_link = f"http://localhost:3000/verify?token={dummy_token}"

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
    sender=mt.Address(email="mailtrap@demomailtrap.com", name="Knihovna ZŠ TS"),
    to=[mt.Address(email="ondrejhanzl@seznam.cz")],
    subject="Potvrzení registrace – Knihovna ZŠ Trhové Sviny",
    text=f"Dobrý den, pro potvrzení Vašeho e-mailu přejděte na: {verification_link}",
    html=html_content,
    category="Registration Verification",
)

# 4. Connect using your API token over standard web traffic (HTTPS)
client = mt.MailtrapClient(token="5f3e5ffc8f8e8b6c9358b675b31fce5b")

try:
    response = client.send(mail)
    print("Success! Response from Mailtrap:", response)
except Exception as e:
    print("An error occurred while sending via API:", e)