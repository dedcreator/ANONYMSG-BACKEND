# backend/test_email.py
import smtplib
from email.mime.text import MIMEText

EMAIL = "hello.scalewithdestiny@gmail.com"
PASSWORD = "trdxdiwlhsttsnch"  # No spaces

msg = MIMEText("Test email from AnonMsg")
msg['Subject'] = 'Test Email'
msg['From'] = EMAIL
msg['To'] = EMAIL

try:
    # Try different ports
    ports = [587, 465]
    for port in ports:
        try:
            if port == 587:
                server = smtplib.SMTP('smtp.gmail.com', port)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL('smtp.gmail.com', port)
            
            server.login(EMAIL, PASSWORD)
            server.send_message(msg)
            server.quit()
            print(f"✅ Email sent successfully on port {port}!")
            break
        except Exception as e:
            print(f"Port {port} failed: {e}")
except Exception as e:
    print(f"❌ All attempts failed: {e}")