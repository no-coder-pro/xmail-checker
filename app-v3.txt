from flask import Flask, request, jsonify, render_template, send_file
import smtplib
import socket
import re
import csv
import io
from datetime import datetime
from typing import List, Dict, Any, Optional

try:
    import dns.resolver
except ImportError:
    pass

app = Flask(__name__)

def verify_email_smtp(email: str) -> str:
    match = re.match('^[_a-z0-9-]+(\.[_a-z0-9-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,4})$', email)
    if not match:
        return "Syntax Error"

    domain = email.split('@')[1]
    
    try:
        records = dns.resolver.resolve(domain, 'MX')
        mx_record = str(records[0].exchange)
    except Exception:
        return "Unknown Domain"

    host = socket.gethostname()
    server = smtplib.SMTP()
    server.set_debuglevel(0)

    try:
        server.connect(mx_record)
        server.helo(host)
        server.mail('me@example.com')
        code, message = server.rcpt(str(email))
        server.quit()

        if code == 250:
            return "Live"
        else:
            return "Unregistered"
    except Exception:
        return "Verify"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/check", methods=["POST"])
def api_check():
    try:
        body = request.get_json(silent=True) or {}
        mails = body.get("mail") or []
        
        if not isinstance(mails, list) or not mails:
            return jsonify({"error": "Provide a non-empty 'mail' list"}), 400

        detailed_results = []
        for email in mails:
            status = verify_email_smtp(email)
            detailed_results.append({
                "email": email,
                "status": status,
                "timestamp": datetime.now().isoformat()
            })

        return jsonify({
            "input_count": len(mails),
            "results": detailed_results
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/download", methods=["POST"])
def download_results():
    data = request.get_json(silent=True) or {}
    results = data.get("results", [])
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Email", "Status", "Timestamp"])
    
    for result in results:
        writer.writerow([
            result.get("email", ""),
            result.get("status", ""),
            result.get("timestamp", "")
        ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'gmail_check_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )

if __name__ == "__main__":
    app.run(debug=True, port=5000)
