"""SMS sender.

Choose a provider with SMS_PROVIDER:
  fast2sms  -> Fast2SMS DLT route (POST https://www.fast2sms.com/dev/bulkV2)
  (unset)   -> generic JSON POST to SMS_API_URL (only for a custom provider)

Fast2SMS settings (set on the server, never in code):
  FAST2SMS_API_KEY           API key from the Fast2SMS dashboard
  FAST2SMS_SENDER_ID         DLT-approved 3 to 6 letter sender ID
  FAST2SMS_OTP_TEMPLATE_ID   DLT message ID of the approved OTP template

India rule: SMS needs a DLT-approved template. The OTP text sent must match the
registered template, with the code in the {#var#} slot. Register this template:
  "Cropora AI login code: {#var#}. Valid for 5 minutes. Do not share."

If nothing is configured, messages are only printed to the log (local testing).
"""
import json
import os
import urllib.request

PROVIDER = os.environ.get("SMS_PROVIDER", "").strip().lower()

FAST2SMS_URL = "https://www.fast2sms.com/dev/bulkV2"
FAST2SMS_API_KEY = os.environ.get("FAST2SMS_API_KEY", "")
FAST2SMS_SENDER_ID = os.environ.get("FAST2SMS_SENDER_ID", "")
FAST2SMS_OTP_TEMPLATE_ID = os.environ.get("FAST2SMS_OTP_TEMPLATE_ID", "")

GENERIC_URL = os.environ.get("SMS_API_URL", "")
GENERIC_KEY = os.environ.get("SMS_API_KEY", "")


def _post_json(url: str, payload: dict, headers: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = resp.read().decode("utf-8") or "{}"
        try:
            return json.loads(body)
        except ValueError:
            return {"raw": body}


def _fast2sms_dlt(mobile10: str, template_id: str, variables: str) -> None:
    if not (FAST2SMS_API_KEY and FAST2SMS_SENDER_ID and template_id):
        raise RuntimeError("Fast2SMS is not fully configured (API key, sender ID, template ID).")
    result = _post_json(
        FAST2SMS_URL,
        {
            "sender_id": FAST2SMS_SENDER_ID,
            "message": template_id,
            "variables_values": variables,
            "route": "dlt",
            "numbers": mobile10,
        },
        {"authorization": FAST2SMS_API_KEY},
    )
    # Fast2SMS reports success with "return": true. Anything else is a failure.
    if result.get("return") is not True:
        raise RuntimeError(f"Fast2SMS rejected the message: {result}")


def send_otp(mobile10: str, code: str) -> None:
    """Send a login code. Uses the DLT OTP template when Fast2SMS is the provider."""
    if PROVIDER == "fast2sms":
        if not FAST2SMS_OTP_TEMPLATE_ID:
            raise RuntimeError("FAST2SMS_OTP_TEMPLATE_ID is not set.")
        _fast2sms_dlt(mobile10, FAST2SMS_OTP_TEMPLATE_ID, code)
        return
    send(mobile10, f"Cropora AI login code: {code}. Valid for 5 minutes. Do not share.")


def send(mobile10: str, text: str) -> None:
    """Send free text through a custom provider (SMS_API_URL). Not used for Fast2SMS."""
    if PROVIDER == "fast2sms":
        # Price alerts need their own DLT templates (Hindi, English) before they can be sent.
        # Refuse loudly, so an alert is never marked as sent when nothing went out.
        raise RuntimeError("Alert SMS on Fast2SMS needs DLT alert templates. Not configured yet.")
    if not GENERIC_URL:
        print(f"[SMS not configured] to={mobile10}: {text}")
        return
    _post_json(
        GENERIC_URL,
        {"to": f"91{mobile10}", "message": text},
        {"Authorization": f"Bearer {GENERIC_KEY}"},
    )
