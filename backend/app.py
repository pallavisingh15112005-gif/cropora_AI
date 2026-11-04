"""Cropora AI alert backend.

- Login with a one-time code (OTP) sent to mobile (SMS) or email.
- Logged-in farmers set one-time price alerts (above or below a limit).
- /api/check runs after the daily price update and sends SMS for alerts that hit.
"""
import hashlib
import json
import os
import re
import secrets
import sqlite3
import time
from pathlib import Path

from flask import Flask, g, jsonify, request

import mail
import sms
from messages import build_message

BASE = Path(__file__).resolve().parent
DB_PATH = os.environ.get("DB_PATH", str(BASE / "cropora.db"))
PRICES_PATH = Path(os.environ.get("PRICES_PATH", str(BASE.parent / "data" / "prices.json")))
CRON_SECRET = os.environ.get("CRON_SECRET", "")
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")
# Only for local testing. Never set this on the live server, or codes leak in responses.
DEV_OTP_ECHO = os.environ.get("DEV_OTP_ECHO") == "1"

OTP_TTL = 300  # 5 minutes
SESSION_TTL = 30 * 24 * 3600  # 30 days
MAX_ACTIVE_ALERTS = 5
CROP_KEYS = {"gehu", "chawal", "sarson", "pyaaz", "aloo", "tamatar", "makka"}
LANGS = {"hi", "en", "both"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS otps (
    contact TEXT PRIMARY KEY, code_hash TEXT, expires_at INTEGER, attempts INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mobile TEXT UNIQUE, email TEXT UNIQUE, lang TEXT DEFAULT 'hi', created_at INTEGER
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY, user_id INTEGER, expires_at INTEGER
);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, crop TEXT, mandi TEXT, direction TEXT, price REAL,
    status TEXT DEFAULT 'active', created_at INTEGER,
    triggered_at INTEGER, triggered_price REAL, triggered_mandi TEXT
);
"""

with sqlite3.connect(DB_PATH) as _init:
    _init.executescript(SCHEMA)

app = Flask(__name__)


@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGIN
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Cron-Secret"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    return resp


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def now() -> int:
    return int(time.time())


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def err(msg: str, status: int = 400):
    return jsonify({"error": msg}), status


MOBILE_RE = re.compile(r"^(\+?91)?[6-9]\d{9}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_contact(raw):
    value = (raw or "").strip().replace(" ", "")
    if EMAIL_RE.match(value):
        return "email", value.lower()
    if MOBILE_RE.match(value):
        return "mobile", value[-10:]
    return None, None


def current_user():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    return db().execute(
        "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id "
        "WHERE s.token_hash = ? AND s.expires_at > ?",
        (digest(auth[7:]), now()),
    ).fetchone()


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.post("/api/otp/request")
def otp_request():
    kind, value = normalize_contact((request.get_json(silent=True) or {}).get("contact"))
    if not kind:
        return err("Sahi mobile number (10 digit) ya email likhein.")

    code = f"{secrets.randbelow(10**6):06d}"
    d = db()
    d.execute(
        "INSERT OR REPLACE INTO otps (contact, code_hash, expires_at, attempts) VALUES (?, ?, ?, 0)",
        (f"{kind}:{value}", digest(code), now() + OTP_TTL),
    )
    d.commit()

    text = f"Cropora AI login code: {code}. 5 minute mein expire hoga. Your code is valid for 5 minutes."
    try:
        if kind == "mobile":
            sms.send(value, text)
        else:
            mail.send(value, "Cropora AI login code", text)
    except Exception as exc:
        app.logger.error("OTP send failed: %s", exc)
        return err("Code abhi nahi bheja ja saka. Thodi der baad koshish karein.", 502)

    resp = {"ok": True}
    if DEV_OTP_ECHO:
        resp["dev_code"] = code
    return jsonify(resp)


@app.post("/api/otp/verify")
def otp_verify():
    body = request.get_json(silent=True) or {}
    kind, value = normalize_contact(body.get("contact"))
    code = str(body.get("code", "")).strip()
    if not kind:
        return err("Sahi mobile number ya email likhein.")

    key = f"{kind}:{value}"
    d = db()
    row = d.execute("SELECT * FROM otps WHERE contact = ?", (key,)).fetchone()
    if row is None or row["expires_at"] < now() or row["attempts"] >= 5:
        return err("Code expire ho gaya ya bahut galat koshish hui. Naya code mangwayein.")
    if row["code_hash"] != digest(code):
        d.execute("UPDATE otps SET attempts = attempts + 1 WHERE contact = ?", (key,))
        d.commit()
        return err("Code galat hai.")

    d.execute("DELETE FROM otps WHERE contact = ?", (key,))
    # kind is only ever "mobile" or "email", so this column name is safe.
    user = d.execute(f"SELECT id FROM users WHERE {kind} = ?", (value,)).fetchone()
    if user is None:
        user_id = d.execute(
            f"INSERT INTO users ({kind}, created_at) VALUES (?, ?)", (value, now())
        ).lastrowid
    else:
        user_id = user["id"]

    token = secrets.token_urlsafe(32)
    d.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (digest(token), user_id, now() + SESSION_TTL),
    )
    d.commit()
    return jsonify({"token": token})


@app.route("/api/profile", methods=["GET", "POST"])
def profile():
    user = current_user()
    if user is None:
        return err("Pehle login karein.", 401)

    if request.method == "GET":
        return jsonify({"mobile": user["mobile"], "email": user["email"], "lang": user["lang"]})

    body = request.get_json(silent=True) or {}
    d = db()
    if body.get("mobile"):
        kind, value = normalize_contact(body["mobile"])
        if kind != "mobile":
            return err("Sahi 10 digit ka mobile number likhein.")
        clash = d.execute("SELECT id FROM users WHERE mobile = ? AND id != ?", (value, user["id"])).fetchone()
        if clash:
            return err("Ye mobile number kisi aur account par hai.", 409)
        d.execute("UPDATE users SET mobile = ? WHERE id = ?", (value, user["id"]))
    if body.get("lang") in LANGS:
        d.execute("UPDATE users SET lang = ? WHERE id = ?", (body["lang"], user["id"]))
    d.commit()
    return jsonify({"ok": True})


@app.get("/api/alerts")
def list_alerts():
    user = current_user()
    if user is None:
        return err("Pehle login karein.", 401)
    rows = db().execute(
        "SELECT id, crop, mandi, direction, price, status, triggered_at, triggered_price, triggered_mandi "
        "FROM alerts WHERE user_id = ? ORDER BY id DESC",
        (user["id"],),
    ).fetchall()
    return jsonify({"alerts": [dict(r) for r in rows]})


@app.post("/api/alerts")
def create_alert():
    user = current_user()
    if user is None:
        return err("Pehle login karein.", 401)
    if not user["mobile"]:
        return err("Pehle profile mein mobile number daalein, alert SMS se jayega.")

    body = request.get_json(silent=True) or {}
    crop = body.get("crop")
    direction = body.get("direction")
    try:
        price = float(body.get("price"))
    except (TypeError, ValueError):
        price = 0
    if crop not in CROP_KEYS:
        return err("Fasal chuniye.")
    if direction not in ("above", "below"):
        return err("Limit upar ya neeche, dono mein se chuniye.")
    if price <= 0:
        return err("Sahi limit price likhein.")

    d = db()
    active = d.execute(
        "SELECT COUNT(*) FROM alerts WHERE user_id = ? AND status = 'active'", (user["id"],)
    ).fetchone()[0]
    if active >= MAX_ACTIVE_ALERTS:
        return err(f"Ek saath {MAX_ACTIVE_ALERTS} se zyada active alert nahi ho sakte.")

    mandi = (body.get("mandi") or "").strip() or None
    d.execute(
        "INSERT INTO alerts (user_id, crop, mandi, direction, price, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user["id"], crop, mandi, direction, price, now()),
    )
    d.commit()
    return jsonify({"ok": True})


@app.delete("/api/alerts/<int:alert_id>")
def delete_alert(alert_id):
    user = current_user()
    if user is None:
        return err("Pehle login karein.", 401)
    d = db()
    d.execute("DELETE FROM alerts WHERE id = ? AND user_id = ?", (alert_id, user["id"]))
    d.commit()
    return jsonify({"ok": True})


@app.post("/api/check")
def check_alerts():
    """Run once after the daily price update. Protected by CRON_SECRET."""
    if not CRON_SECRET or request.headers.get("X-Cron-Secret") != CRON_SECRET:
        return err("Not allowed.", 401)

    # The daily workflow posts the fresh prices.json as the body. Fall back to the local file.
    data = request.get_json(silent=True)
    if not data or "items" not in data:
        data = json.loads(PRICES_PATH.read_text(encoding="utf-8"))
    items = data.get("items", [])
    price_date = str(data.get("updated_at", ""))[:10]

    d = db()
    rows = d.execute(
        "SELECT a.*, u.mobile AS mobile, u.lang AS lang FROM alerts a "
        "JOIN users u ON u.id = a.user_id WHERE a.status = 'active'"
    ).fetchall()

    sent, failed = 0, 0
    for a in rows:
        hit = None
        for item in items:
            if item.get("crop") != a["crop"]:
                continue
            if a["mandi"] and item.get("mandi") != a["mandi"]:
                continue
            modal = float(item.get("modal") or 0)
            ok = modal >= a["price"] if a["direction"] == "above" else modal <= a["price"]
            if ok:
                hit = item
                break
        if hit is None:
            continue

        text = build_message(
            lang=a["lang"] or "hi",
            crop=a["crop"],
            mandi=hit.get("mandi") or "",
            price=float(hit["modal"]),
            direction=a["direction"],
            limit=a["price"],
            date=price_date,
        )
        try:
            sms.send(a["mobile"], text)
        except Exception as exc:
            app.logger.error("SMS failed for alert %s: %s", a["id"], exc)
            failed += 1
            continue

        # One-time alert: once sent, it is done.
        d.execute(
            "UPDATE alerts SET status = 'sent', triggered_at = ?, triggered_price = ?, triggered_mandi = ? "
            "WHERE id = ?",
            (now(), float(hit["modal"]), hit.get("mandi"), a["id"]),
        )
        sent += 1

    d.commit()
    return jsonify({"checked": len(rows), "sent": sent, "failed": failed})


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", "5000")))
