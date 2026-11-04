"""SMS sender. Connect this to your SMS provider (MSG91, Fast2SMS, etc.).

Set these environment variables on the server:
  SMS_API_URL      the provider's send endpoint
  SMS_API_KEY      the provider's API key
  SMS_SENDER_ID    your approved 6-character sender ID
  DLT_TEMPLATE_ID  the DLT template ID for these messages (India requires it)

If SMS_API_URL is not set, the message is only printed to the log. This is for local testing.
The request body below is a generic shape. Map it to your provider's exact format.
"""
import json
import os
import urllib.request

SMS_API_URL = os.environ.get("SMS_API_URL", "")
SMS_API_KEY = os.environ.get("SMS_API_KEY", "")
SMS_SENDER_ID = os.environ.get("SMS_SENDER_ID", "")
DLT_TEMPLATE_ID = os.environ.get("DLT_TEMPLATE_ID", "")


def send(mobile10: str, text: str) -> None:
    if not SMS_API_URL:
        print(f"[SMS not configured] to={mobile10}: {text}")
        return

    payload = json.dumps({
        "to": f"91{mobile10}",
        "sender": SMS_SENDER_ID,
        "message": text,
        "dlt_template_id": DLT_TEMPLATE_ID,
    }).encode("utf-8")
    req = urllib.request.Request(
        SMS_API_URL,
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {SMS_API_KEY}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        if resp.status >= 300:
            raise RuntimeError(f"SMS provider returned {resp.status}")
