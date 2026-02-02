from flask import Flask, request, jsonify, render_template, send_file
import smtplib
import socket
import re
import csv
import io
import os
import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

GMAIL_MX_SERVERS = [
    "gmail-smtp-in.l.google.com",
    "alt1.gmail-smtp-in.l.google.com",
    "alt2.gmail-smtp-in.l.google.com"
]

def verify_gmail_advanced(email: str) -> str:
    match = re.match(r'^[_a-z0-9-]+(\.[_a-z0-9-]+)*@gmail\.com$', email.lower())
    if not match:
        return "Invalid Format"

    mx_host = random.choice(GMAIL_MX_SERVERS)
    
    try:
        server = smtplib.SMTP(timeout=7)
        server.connect(mx_host)
        server.helo(socket.gethostname())
        server.mail('admin@' + socket.gethostname()) # ডায়নামিক মেইল ব্যবহার
        code, message = server.rcpt(email)
        server.quit()

        if code == 250:
            return "Live"
        elif code == 550:
            return "Dead/Not Found"
        elif code == 421 or code == 450:
            return "Rate Limited (Try Later)"
        else:
            return f"Unknown ({code})"
            
    except smtplib.SMTPServerDisconnected:
        return "Server Disconnected"
    except socket.timeout:
        return "Timeout (Network Slow)"
    except Exception as e:
        return "Connection Blocked"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/check", methods=["POST"])
def api_check():
    try:
        body = request.get_json(silent=True) or {}
        mails = body.get("mail") or []
        
        if not mails:
            return jsonify({"error": "No emails provided"}), 400

        def check_task(email):
            return {
                "email": email, 
                "status": verify_gmail_advanced(email), 
                "timestamp": datetime.now().isoformat()
            }

        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(check_task, mails))

        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

application = app 
if __name__ == "__main__":
    app.run()
