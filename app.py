from flask import Flask, request, jsonify, render_template, send_file
import requests
import re
import logging
import csv
import io
from datetime import datetime
from typing import List, Dict, Any, Optional

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

BASE_URL = "https://gmailver.com"
KEY_ENDPOINT = f"{BASE_URL}/php/key.php"
CHECK_ENDPOINT = f"{BASE_URL}/php/check1.php"

BROWSER_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

API_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json;charset=UTF-8",
    "origin": BASE_URL,
    "referer": f"{BASE_URL}/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

def extract_key_from_text(text: str) -> str:
    m = re.search(r"([0-9a-fA-F]{32})", text or "")
    if m:
        return m.group(1)
    m = re.search(r"([0-9a-fA-F]{24,64})", text or "")
    return m.group(1) if m else ""

def fetch_cookies_requests() -> Optional[requests.Session]:
    s = requests.Session()
    s.headers.update(BROWSER_HEADERS)
    try:
        r = s.get(BASE_URL + "/", timeout=30, allow_redirects=True)
        if r.status_code == 200:
            return s
    except Exception as e:
        logging.error(f"Error fetching cookies: {e}")
    return None

def get_session_with_cookies(manual_cookie: Optional[str] = None) -> requests.Session:
    if manual_cookie:
        s = requests.Session()
        s.headers.update(BROWSER_HEADERS)
        for part in manual_cookie.split(';'):
            if '=' in part:
                k, v = part.split('=', 1)
                s.cookies.set(k.strip(), v.strip())
        return s

    s = fetch_cookies_requests()
    if s:
        return s

    s = requests.Session()
    s.headers.update(BROWSER_HEADERS)
    return s

def call_key(session: requests.Session, mails: List[str]) -> Dict[str, Any]:
    payload = {"mail": mails}
    try:
        r = session.post(KEY_ENDPOINT, json=payload, headers=API_HEADERS, timeout=60)
        raw = r.text or ""
        key = extract_key_from_text(raw)
        return {"ok": bool(key), "key": key, "raw": raw[:1000], "status": r.status_code}
    except Exception as e:
        return {"ok": False, "error": str(e), "raw": ""}

def call_check(session: requests.Session, mails: List[str], key: str, fast_check: bool) -> Dict[str, Any]:
    payload = {"mail": mails, "key": key, "fastCheck": bool(fast_check)}
    try:
        r = session.post(CHECK_ENDPOINT, json=payload, headers=API_HEADERS, timeout=90)
        try:
            return {"json": r.json(), "status": r.status_code}
        except ValueError:
            text = r.text
            json_match = re.search(r'(\{.*\})', text, re.DOTALL)
            if json_match:
                import json
                try:
                    return {"json": json.loads(json_match.group(1)), "status": r.status_code}
                except:
                    pass
            return {"raw": r.text[:2000], "status": r.status_code}
    except Exception as e:
        return {"error": str(e)}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/check", methods=["POST"])
def api_check():
    body = request.get_json(silent=True) or {}
    mails = body.get("mail") or []
    fast_check = bool(body.get("fastCheck", False))
    manual_cookie = body.get("cookie")

    if not isinstance(mails, list) or not mails:
        return jsonify({"error": "Provide a non-empty 'mail' list"}), 400

    session = get_session_with_cookies(manual_cookie)
    key_resp = call_key(session, mails)
    if not key_resp.get("ok"):
        return jsonify({
            "error": "Could not extract key",
            "details": key_resp
        }), 502

    key = key_resp["key"].strip()
    check_resp = call_check(session, mails, key, fast_check)
    detailed_results = []
    
    if "json" in check_resp and isinstance(check_resp["json"], dict):
        data = check_resp["json"]
        if isinstance(data.get("data"), list):
            for item in data["data"]:
                mail = item.get("mail") or item.get("email")
                status = item.get("status") or item.get("state") or "unknown"
                
                if mail:
                    detailed_results.append({
                        "email": mail,
                        "status": status,
                        "timestamp": datetime.now().isoformat()
                    })
    
    if not detailed_results and "error" in check_resp:
         return jsonify({"error": check_resp["error"]}), 502

    return jsonify({
        "input_count": len(mails),
        "results": detailed_results,
        "debug": {
            "key_prefix": key[:5] + "..." if key else None
        }
    })

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
