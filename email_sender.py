import smtplib
from email.message import EmailMessage
from pathlib import Path

GMAIL_USER = "ivan.espinoza.m@gmail.com"
APP_PASSWORD = "qgmo myef hjwo ytzp"  # tu App Password (16 chars, sin espacios si quieres)

def enviar_excel_gmail(
    archivo_xlsx: str,
    para: list[str],
    asunto: str = "Reporte",
    cuerpo: str = "Te adjunto el Excel.",
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
):
    msg = EmailMessage()
    msg["From"] = GMAIL_USER
    msg["To"] = ", ".join(para)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = asunto
    # Set both plain text and HTML content
    msg.set_content(cuerpo)
    # If the content contains HTML tags, set as HTML
    if '<' in cuerpo and '>' in cuerpo:
        msg.add_alternative(cuerpo, subtype='html')

    # Adjuntar el Excel
    ruta = Path(archivo_xlsx)
    with ruta.open("rb") as f:
        data = f.read()
    msg.add_attachment(
        data,
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=ruta.name,
    )

    # Enviar
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(GMAIL_USER, APP_PASSWORD)
        smtp.send_message(msg, to_addrs=para + (cc or []) + (bcc or []))
