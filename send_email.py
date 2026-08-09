"""
Stage 5: Send.
Sends the built HTML digest via SMTP. Works with any SMTP provider -
Amazon SES, Resend, Postmark, or a plain Gmail app password for testing.
Supports test mode: save to file instead of sending email.
"""
import smtplib
import os
from datetime import date, datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, FROM_EMAIL, DIGEST_RECIPIENT, DIGEST_TEST_MODE
from db import get_connection


def send_digest(html, recipient=None, cluster_ids=None):
    recipient = recipient or DIGEST_RECIPIENT
    if not recipient:
        raise ValueError("No recipient set. Set DIGEST_RECIPIENT in .env")
    
    # Test mode: save to file instead of sending email
    if DIGEST_TEST_MODE == 1:
        test_filename = f"digest_test_{date.today().strftime('%Y-%m-%d_%H%M%S')}.html"
        with open(test_filename, "w") as f:
            f.write(html)
        print(f"TEST MODE: Digest saved to {test_filename}")
        
        # Still log it in the database
        if cluster_ids:
            conn = get_connection()
            conn.execute(
                "INSERT INTO digest_log (sent_at, recipient, cluster_ids) VALUES (?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), f"TEST:{recipient}", ",".join(map(str, cluster_ids))),
            )
            conn.commit()
            conn.close()
        return
    
    # Production mode: send via SMTP
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASS]):
        raise ValueError("SMTP settings missing. Check your .env file.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"AI Daily — {date.today().strftime('%B %d, %Y')}"
    msg["From"] = FROM_EMAIL
    msg["To"] = recipient
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(FROM_EMAIL, recipient, msg.as_string())

    if cluster_ids:
        conn = get_connection()
        conn.execute(
            "INSERT INTO digest_log (sent_at, recipient, cluster_ids) VALUES (?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), recipient, ",".join(map(str, cluster_ids))),
        )
        conn.commit()
        conn.close()

    print(f"Sent digest to {recipient}.")
