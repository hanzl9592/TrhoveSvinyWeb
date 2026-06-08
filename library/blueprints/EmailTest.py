import mailtrap as mt

mail = mt.Mail(
    sender=mt.Address(email="skolni.knihovna.TS@demomailtrap.co", name="Skolni knihovna Trhove Sviny"),
    to=[mt.Address(email="ondrejhanzl@seznam.cz")],
    subject="You are awesome!",
    text="Congrats for sending test email with Mailtrap!",
    category="Integration Test",
)

client = mt.MailtrapClient(token="227bc8f49234e5edc6e3d37475fabc4e")
response = client.send(mail)

print(response)