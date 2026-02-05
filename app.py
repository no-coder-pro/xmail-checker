from flask import Flask, request, jsonify, render_template, send_file
import requests
import csv
import io
from datetime import datetime
from typing import List, Dict, Any

app = Flask(__name__)

headers_payload = {
    'accept': '*/*',
    'accept-language': 'en-US,en;q=0.9,bn;q=0.8',
    'dnt': '1',
    'priority': 'u=1, i',
    'referer': 'https://ychecker.com/',
    'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
}

headers_check_email = {
    'accept': '*/*',
    'accept-language': 'en-US,en;q=0.9,bn;q=0.8',
    'dnt': '1',
    'origin': 'https://ychecker.com',
    'priority': 'u=1, i',
    'referer': 'https://ychecker.com/',
    'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'cross-site',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
}

def check_single_email(session: requests.Session, email: str) -> Dict[str, Any]:
    try:
        url_payload = 'https://ychecker.com/app/payload'
        params_payload = {'email': email, 'use_credit_first': '0'}
        resp_payload = session.get(url_payload, params=params_payload, headers=headers_payload, timeout=15)
        
        if resp_payload.status_code != 200:
            return {"email": email, "status": "Connection Error", "timestamp": datetime.now().isoformat()}

        data_payload = resp_payload.json()
        enc = data_payload.get('items')
        if not enc:
            return {"email": email, "status": "Payload Error", "timestamp": datetime.now().isoformat()}

        url_check_email = f"https://api.sonjj.com/v1/check_email/?payload={enc}"
        response_check_email = session.get(url_check_email, headers=headers_check_email, timeout=15)
        
        if response_check_email.status_code != 200:
             return {"email": email, "status": "Check Error", "timestamp": datetime.now().isoformat()}

        data = response_check_email.json()
        status = "Unknown"
        
        if data.get("status"):
            status = str(data.get("status"))
        elif data.get("data") and isinstance(data["data"], list) and len(data["data"]) > 0:
            item = data["data"][0]
            status = item.get("status") or item.get("state") or "Unknown"
        elif data.get("message"):
            status = data.get("message")
        elif data.get("status") is False:
            status = "Invalid Request"

        return {
            "email": email,
            "status": status,
            "timestamp": datetime.now().isoformat()
        }

    except Exception:
        return {
            "email": email,
            "status": "Error",
            "timestamp": datetime.now().isoformat()
        }

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
        with requests.Session() as session:
            try:
                session.get('https://ychecker.com/', headers=headers_payload, timeout=15)
            except:
                pass
                
            for email in mails:
                detailed_results.append(check_single_email(session, email))

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
