import smtplib
import ssl
import os
import re
import random
import socket
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Dict, Any, Tuple, Optional

# Enforce strict 15s timeout on all socket connections
socket.setdefaulttimeout(15)

def parse_spintax(text: str) -> str:
    """
    Parses spintax like '{Hi|Hello|Hey}' with '|' character.
    Leaves other brackets untouched.
    """
    pattern = re.compile(r"\{([^{}|]+\|[^{}]+)\}")
    while True:
        match = pattern.search(text)
        if not match:
            break
        choices = match.group(1).split("|")
        chosen = random.choice(choices)
        text = text[:match.start()] + chosen + text[match.end():]
    return text

def render_template(template_str: str, contact: Dict[str, Any], settings: Dict[str, str]) -> str:
    """
    Renders variables and spintax into a finalized string.
    Supports (first_name), {{first_name}}, {first_name}, etc.
    """
    text = parse_spintax(template_str)

    first_name = contact.get("first_name") or ""
    if not first_name and contact.get("full_name"):
        first_name = contact.get("full_name").strip().split(" ")[0]
    if not first_name:
        first_name = "Hiring Leader"
    first_name = first_name.strip().title()

    full_name = (contact.get("full_name") or first_name).strip().title()
    last_name = (contact.get("last_name") or "").strip().title()
    company_name = (contact.get("company_name") or "your organisation").strip()
    designation = (contact.get("designation") or "HR Leader").strip()
    target_role = (contact.get("target_role") or "SAP BTP Developer").strip()
    my_name = settings.get("sender_name") or "Dhruv Dalal"
    my_phone = settings.get("my_phone") or "+91 7391919546"
    my_linkedin = settings.get("my_linkedin") or "https://linkedin.com/in/dhruvdalal1513"
    my_portfolio = settings.get("my_portfolio") or "https://github.com/DHRUVDALAL"

    substitutions = [
        (r'(\{\{|\(|\{|\[)\s*first[_\s-]*name\s*(\}\}|\)|\}|\])|(?<=\b)first[_\s-]*name(?=\b)', first_name),
        (r'(\{\{|\(|\{|\[)\s*full[_\s-]*name\s*(\}\}|\)|\}|\])|(?<=\b)full[_\s-]*name(?=\b)', full_name),
        (r'(\{\{|\(|\{|\[)\s*last[_\s-]*name\s*(\}\}|\)|\}|\])|(?<=\b)last[_\s-]*name(?=\b)', last_name),
        (r'(\{\{|\(|\{|\[)\s*company[_\s-]*name\s*(\}\}|\)|\}|\])|(\{\{|\(|\{|\[)\s*company\s*(\}\}|\)|\}|\])|(?<=\b)company[_\s-]*name(?=\b)', company_name),
        (r'(\{\{|\(|\{|\[)\s*designation\s*(\}\}|\)|\}|\])|(\{\{|\(|\{|\[)\s*job[_\s-]*title\s*(\}\}|\)|\}|\])', designation),
        (r'(\{\{|\(|\{|\[)\s*target[_\s-]*role\s*(\}\}|\)|\}|\])', target_role),
        (r'(\{\{|\(|\{|\[)\s*my[_\s-]*name\s*(\}\}|\)|\}|\])', my_name),
        (r'(\{\{|\(|\{|\[)\s*my[_\s-]*phone\s*(\}\}|\)|\}|\])', my_phone),
        (r'(\{\{|\(|\{|\[)\s*my[_\s-]*linkedin\s*(\}\}|\)|\}|\])', my_linkedin),
        (r'(\{\{|\(|\{|\[)\s*my[_\s-]*portfolio\s*(\}\}|\)|\}|\])', my_portfolio),
    ]

    for pattern, value in substitutions:
        text = re.sub(pattern, value, text, flags=re.IGNORECASE)

    return text

def build_html_body(plain_text: str) -> str:
    """
    Converts plain text into clean, modern, responsive email HTML with high inbox deliverability.
    """
    escaped = plain_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    paragraphs = escaped.split("\n\n")
    html_paragraphs = []
    for p in paragraphs:
        if p.strip():
            formatted_p = p.replace("\n", "<br>")
            # Auto-link URLs
            formatted_p = re.sub(
                r'(https?://[^\s]+)',
                r'<a href="\1" style="color: #4f46e5; text-decoration: underline;">\1</a>',
                formatted_p
            )
            html_paragraphs.append(f'<p style="margin: 0 0 16px 0; line-height: 1.6; color: #1f2937;">{formatted_p}</p>')

    html_content = "".join(html_paragraphs)
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 15px; color: #1f2937; background-color: #ffffff; padding: 20px 0; margin: 0;">
    <div style="max-width: 600px; margin: 0 auto; padding: 0 20px;">
        {html_content}
    </div>
</body>
</html>"""

def get_ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()

def test_smtp_connection(settings: Dict[str, str]) -> Tuple[bool, str]:
    host = settings.get("smtp_host", "smtp.gmail.com")
    port = int(settings.get("smtp_port", "587"))
    user = settings.get("smtp_user", "").strip()
    password = settings.get("smtp_pass", "").strip().replace(" ", "")

    if not user or not password:
        return False, "SMTP Username and Password/App Password are required."

    try:
        context = get_ssl_context()
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, context=context, timeout=10)
        else:
            server = smtplib.SMTP(host, port, timeout=10)
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()

        server.login(user, password)
        server.quit()
        return True, "Successfully connected and authenticated with Gmail SMTP server!"
    except smtplib.SMTPAuthenticationError:
        return False, "Authentication failed. For Gmail, you MUST use a 16-character App Password (not your normal Gmail password)."
    except Exception as e:
        return False, f"Connection failed: {str(e)}"

def send_email_message(
    contact: Dict[str, Any],
    template: Dict[str, Any],
    settings: Dict[str, str],
    is_dry_run: bool = False
) -> Tuple[bool, str]:
    """
    Prepares and dispatches an email to the contact.
    """
    recipient_email = contact["email"].strip()
    subject = render_template(template["subject"], contact, settings)
    body_text = render_template(template["body"], contact, settings)
    body_html = build_html_body(body_text)

    sender_name = settings.get("sender_name", "Dhruv")
    sender_email = settings.get("sender_email") or settings.get("smtp_user", "")

    if is_dry_run:
        return True, f"[SIMULATED DRY RUN] Subject: {subject}"

    host = settings.get("smtp_host", "smtp.gmail.com")
    port = int(settings.get("smtp_port", "587"))
    user = settings.get("smtp_user", "").strip()
    password = settings.get("smtp_pass", "").strip().replace(" ", "")

    if not user or not password or not sender_email:
        return False, "Sender email and SMTP credentials are missing. Please configure Settings."

    # Build MIME message
    msg = MIMEMultipart("mixed")
    msg["From"] = f"{sender_name} <{sender_email}>"
    msg["To"] = recipient_email
    msg["Subject"] = subject

    # Plain text and HTML alternatives
    alt_part = MIMEMultipart("alternative")
    alt_part.attach(MIMEText(body_text, "plain", "utf-8"))
    alt_part.attach(MIMEText(body_html, "html", "utf-8"))
    msg.attach(alt_part)

    # Attach resume if configured
    resume_filename = settings.get("active_resume_filename")
    if resume_filename:
        resume_path = os.path.join(os.path.dirname(__file__), "uploads", resume_filename)
        if os.path.exists(resume_path):
            try:
                with open(resume_path, "rb") as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(resume_path))
                part["Content-Disposition"] = f'attachment; filename="{os.path.basename(resume_path)}"'
                msg.attach(part)
            except Exception as e:
                return False, f"Failed to attach resume PDF: {str(e)}"

    # Send
    try:
        context = get_ssl_context()
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, context=context, timeout=20)
        else:
            server = smtplib.SMTP(host, port, timeout=20)
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()

        server.login(user, password)
        server.sendmail(sender_email, [recipient_email], msg.as_string())
        server.quit()
        return True, "Email delivered successfully."
    except smtplib.SMTPAuthenticationError:
        return False, "SMTP Authentication Failed. Please verify your App Password."
    except smtplib.SMTPRecipientsRefused:
        return False, "Recipient email rejected by mail server (invalid address)."
    except Exception as e:
        return False, f"Delivery error: {str(e)}"
