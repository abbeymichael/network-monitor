"""
SMS sending abstraction.

Supports several popular gateways plus a fully generic HTTP-webhook
option so the app can talk to essentially *any* SMS API that accepts
a JSON/HTTP request.

Each provider function returns (success: bool, info: str).
"""
from __future__ import annotations

import json
from typing import List, Tuple

import requests

from .models import SmsProviderConfig

DEFAULT_TIMEOUT = 12


def send_sms(cfg: SmsProviderConfig, message: str) -> Tuple[bool, str]:
    """Send `message` to every configured recipient using the active provider.

    Returns overall success (True only if *all* recipients succeeded) and a
    human readable info/error string summarising the outcome.
    """
    if not cfg.to_numbers:
        return False, "No recipient phone numbers configured."

    provider = (cfg.provider or "none").lower()
    if provider == "none":
        return False, "No SMS provider configured."

    sender = _PROVIDERS.get(provider)
    if sender is None:
        return False, f"Unknown SMS provider '{provider}'."

    results = []
    all_ok = True
    for to in cfg.to_numbers:
        ok, info = sender(cfg, to, message)
        results.append(f"{to}: {'OK' if ok else 'FAIL - ' + info}")
        all_ok = all_ok and ok
    return all_ok, "; ".join(results)


def test_send(cfg: SmsProviderConfig) -> Tuple[bool, str]:
    """Convenience for the 'Send Test SMS' button in settings."""
    return send_sms(cfg, "PingSentry test message: your SMS configuration is working correctly.")


# --------------------------------------------------------------------------
# Individual providers
# --------------------------------------------------------------------------

def _send_twilio(cfg: SmsProviderConfig, to: str, message: str) -> Tuple[bool, str]:
    if not (cfg.twilio_account_sid and cfg.twilio_auth_token and cfg.from_number):
        return False, "Twilio credentials incomplete (SID / token / from number)."
    url = f"https://api.twilio.com/2010-04-01/Accounts/{cfg.twilio_account_sid}/Messages.json"
    try:
        resp = requests.post(
            url,
            data={"To": to, "From": cfg.from_number, "Body": message},
            auth=(cfg.twilio_account_sid, cfg.twilio_auth_token),
            timeout=DEFAULT_TIMEOUT,
        )
        if resp.status_code in (200, 201):
            return True, "sent"
        return False, f"HTTP {resp.status_code}: {_short(resp.text)}"
    except requests.RequestException as e:
        return False, str(e)


def _send_vonage(cfg: SmsProviderConfig, to: str, message: str) -> Tuple[bool, str]:
    if not (cfg.vonage_api_key and cfg.vonage_api_secret and cfg.from_number):
        return False, "Vonage credentials incomplete (API key / secret / from number)."
    url = "https://rest.nexmo.com/sms/json"
    payload = {
        "api_key": cfg.vonage_api_key,
        "api_secret": cfg.vonage_api_secret,
        "to": to.lstrip("+"),
        "from": cfg.from_number,
        "text": message,
    }
    try:
        resp = requests.post(url, data=payload, timeout=DEFAULT_TIMEOUT)
        if resp.status_code == 200:
            body = resp.json()
            msgs = body.get("messages", [])
            if msgs and msgs[0].get("status") == "0":
                return True, "sent"
            err = msgs[0].get("error-text") if msgs else body
            return False, str(err)
        return False, f"HTTP {resp.status_code}: {_short(resp.text)}"
    except requests.RequestException as e:
        return False, str(e)
    except (ValueError, KeyError, IndexError) as e:
        return False, f"unexpected response: {e}"


def _send_textbelt(cfg: SmsProviderConfig, to: str, message: str) -> Tuple[bool, str]:
    if not cfg.textbelt_api_key:
        return False, "Textbelt API key not configured."
    url = "https://textbelt.com/text"
    try:
        resp = requests.post(
            url,
            data={"phone": to, "message": message, "key": cfg.textbelt_api_key},
            timeout=DEFAULT_TIMEOUT,
        )
        body = resp.json()
        if body.get("success"):
            return True, "sent"
        return False, str(body.get("error", "unknown error"))
    except requests.RequestException as e:
        return False, str(e)
    except ValueError as e:
        return False, f"unexpected response: {e}"


def _send_generic_webhook(cfg: SmsProviderConfig, to: str, message: str) -> Tuple[bool, str]:
    if not cfg.webhook_url:
        return False, "Webhook URL not configured."
    body_str = cfg.webhook_body_template.replace("{to}", to).replace("{message}", _json_escape(message))
    headers = dict(cfg.webhook_headers or {})
    headers.setdefault("Content-Type", "application/json")

    try:
        payload_json = json.loads(body_str)
        kwargs = {"json": payload_json}
    except (json.JSONDecodeError, TypeError):
        kwargs = {"data": body_str}

    method = (cfg.webhook_method or "POST").upper()
    try:
        resp = requests.request(method, cfg.webhook_url, headers=headers, timeout=DEFAULT_TIMEOUT, **kwargs)
        if 200 <= resp.status_code < 300:
            return True, "sent"
        return False, f"HTTP {resp.status_code}: {_short(resp.text)}"
    except requests.RequestException as e:
        return False, str(e)


def _short(text: str, limit: int = 180) -> str:
    text = (text or "").strip().replace("\n", " ")
    return text[:limit] + ("..." if len(text) > limit else "")


def _json_escape(text: str) -> str:
    # escape for embedding raw into a JSON string body template
    return json.dumps(text)[1:-1]


_PROVIDERS = {
    "twilio": _send_twilio,
    "vonage": _send_vonage,
    "textbelt": _send_textbelt,
    "generic_webhook": _send_generic_webhook,
}

PROVIDER_LABELS = {
    "twilio": "Twilio",
    "vonage": "Vonage (Nexmo)",
    "textbelt": "Textbelt",
    "generic_webhook": "Generic HTTP Webhook",
    "none": "None (disabled)",
}
