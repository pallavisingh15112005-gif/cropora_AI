# Cropora AI alert backend

Farmers log in with a mobile OTP or email code, set a one-time price alert, and get an SMS in Hindi, English, or both when the price crosses their limit.

## Run locally (test)
```
cd backend
pip install -r requirements.txt
DEV_OTP_ECHO=1 CRON_SECRET=test-secret python app.py
```
Without `SMS_API_URL` and `SMTP_HOST`, OTPs and alerts are only printed to the terminal.

## Environment variables (set on the server, never in code)
| Name | Purpose |
|---|---|
| `CRON_SECRET` | Long random string. Same value goes in the GitHub secret `CRON_SECRET`. |
| `ALLOWED_ORIGIN` | Your site, e.g. `https://pallavisingh15112005-gif.github.io` |
| `SMS_API_URL`, `SMS_API_KEY`, `SMS_SENDER_ID`, `DLT_TEMPLATE_ID` | SMS provider details (India needs DLT registration) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `MAIL_FROM` | Email for login codes |
| `DB_PATH` | Path to the SQLite file (use a persistent disk on the host) |

## Deploy
1. Host the `backend` folder on a Python host (Render, Railway, etc.). Start command: `gunicorn app:app`.
2. Set the environment variables above.
3. In GitHub repo settings → Secrets, add `BACKEND_URL` (your backend address) and `CRON_SECRET`.
4. In `alerts.html`, set `API_BASE` to the backend address, then publish the page.

## Before going live
- SMS messages must match DLT-approved templates. Keep the text in `messages.py` identical to the registered template.
- Hindi SMS uses Unicode, so each message costs more and fits fewer characters. "both" costs the most.
- Add rate limiting on `/api/otp/request` before opening it to the public.
