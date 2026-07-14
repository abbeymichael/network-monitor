"""
SMS sending abstraction.

Supports several popular gateways plus a fully generic HTTP-webhook
option so the app can talk to essentially *any* SMS API that accepts
a JSON/HTTP request.

Each provider function returns (success: bool, info: str).
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

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


def _send_txtconnect(cfg: SmsProviderConfig, to: str, message: str) -> Tuple[bool, str]:
    """TxtConnect (https://txtconnect.net) - Bearer-token JSON API.

    Mirrors the official Laravel sample:
        Http::withBearerToken($secret)
            ->withHeaders(['Content-Type' => 'application/json', 'Cache-Control' => 'no-cache'])
            ->post($endpoint, ['from' => ..., 'sms' => ..., 'to' => ..., 'unicode' => 0|1]);
    """
    if not cfg.txtconnect_api_secret:
        return False, "TxtConnect API secret not configured."
    endpoint = cfg.txtconnect_endpoint or "https://api.txtconnect.net/dev/api/sms/send"
    payload = {
        "from": cfg.from_number or "PingSentry",
        "sms": message,
        "to": to,
        "unicode": 1 if cfg.txtconnect_unicode else 0,
    }
    headers = {
        "Authorization": f"Bearer {cfg.txtconnect_api_secret}",
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
    }
    try:
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=DEFAULT_TIMEOUT)
        try:
            body = resp.json()
        except ValueError:
            body = None
        if 200 <= resp.status_code < 300:
            # TxtConnect responses typically include a status/success indicator;
            # treat any 2xx as success unless the body explicitly reports failure.
            if isinstance(body, dict) and str(body.get("status", "")).lower() in ("error", "failed", "false"):
                return False, str(body.get("message") or body.get("error") or body)
            return True, "sent"
        detail = _short(json.dumps(body)) if body is not None else _short(resp.text)
        return False, f"HTTP {resp.status_code}: {detail}"
    except requests.RequestException as e:
        return False, str(e)


def _send_custom(cfg: SmsProviderConfig, to: str, message: str) -> Tuple[bool, str]:
    """Fully user-configurable HTTP SMS gateway.

    Supports:
      - Any HTTP method (GET/POST/PUT/PATCH)
      - JSON or form-encoded body, built from a user template with
        {to} / {message} / {from} placeholders
      - Extra static headers and query params (placeholders substituted too)
      - Authentication: none, Bearer token, HTTP Basic, API key in a
        custom header, or API key in a query parameter
      - Success detection: either "any 2xx status code" or a specific
        field in the JSON response body matching an expected value
        (dotted path, e.g. "data.status")
    """
    if not cfg.webhook_url:
        return False, "Custom provider URL not configured."

    def _sub(text: str) -> str:
        return (text or "").replace("{to}", to).replace("{from}", cfg.from_number or "")

    def _sub_body(text: str) -> str:
        return _sub(text).replace("{message}", _json_escape(message) if _looks_like_json(text) else message)

    method = (cfg.webhook_method or "POST").upper()
    headers = {_sub(k): _sub(v) for k, v in (cfg.webhook_headers or {}).items()}
    params = {_sub(k): _sub(v) for k, v in (cfg.webhook_query_params or {}).items()}

    # -- Authentication -----------------------------------------------------
    auth_type = (cfg.webhook_auth_type or "none").lower()
    basic_auth = None
    if auth_type == "bearer" and cfg.webhook_auth_token:
        headers[cfg.webhook_auth_header_name or "Authorization"] = f"Bearer {cfg.webhook_auth_token}"
    elif auth_type == "api_key_header" and cfg.webhook_auth_token:
        headers[cfg.webhook_auth_header_name or "X-API-Key"] = cfg.webhook_auth_token
    elif auth_type == "api_key_query" and cfg.webhook_auth_token:
        params[cfg.webhook_auth_query_name or "api_key"] = cfg.webhook_auth_token
    elif auth_type == "basic" and cfg.webhook_basic_username:
        basic_auth = (cfg.webhook_basic_username, cfg.webhook_basic_password)

    # -- Body -----------------------------------------------------------
    kwargs: Dict[str, Any] = {}
    if method in ("POST", "PUT", "PATCH"):
        body_str = _sub_body(cfg.webhook_body_template or "")
        content_type = (cfg.webhook_content_type or "auto").lower()
        if content_type == "json" or (content_type == "auto" and _looks_like_json(body_str)):
            try:
                kwargs["json"] = json.loads(body_str)
                headers.setdefault("Content-Type", "application/json")
            except (json.JSONDecodeError, TypeError):
                kwargs["data"] = body_str
        else:
            # form-encoded: parse "key=value&key2=value2" style templates,
            # falling back to raw string body if it doesn't parse cleanly.
            kwargs["data"] = _parse_form_template(body_str)
    elif params:
        pass  # GET: fields go through query params only

    try:
        resp = requests.request(
            method, cfg.webhook_url, headers=headers, params=params or None,
            auth=basic_auth, timeout=DEFAULT_TIMEOUT, **kwargs,
        )
    except requests.RequestException as e:
        return False, str(e)

    return _check_custom_success(cfg, resp)


def _check_custom_success(cfg: SmsProviderConfig, resp) -> Tuple[bool, str]:
    check = (cfg.webhook_success_check or "status_code").lower()
    if check == "json_field" and cfg.webhook_success_json_path:
        try:
            body = resp.json()
        except ValueError:
            return False, f"Response is not valid JSON (HTTP {resp.status_code}): {_short(resp.text)}"
        actual = _dig(body, cfg.webhook_success_json_path)
        expected = cfg.webhook_success_json_value
        if str(actual) == str(expected):
            return True, "sent"
        return False, f"Field '{cfg.webhook_success_json_path}' = {actual!r}, expected {expected!r}"

    if 200 <= resp.status_code < 300:
        return True, "sent"
    return False, f"HTTP {resp.status_code}: {_short(resp.text)}"


def _dig(obj: Any, dotted_path: str) -> Any:
    cur = obj
    for part in dotted_path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return cur


def _looks_like_json(text: str) -> bool:
    text = (text or "").strip()
    return text.startswith("{") or text.startswith("[")


def _parse_form_template(body_str: str) -> Dict[str, str]:
    """Best-effort parse of a 'key=value&key2=value2' template into a dict
    for requests' form-encoding. Falls back to a single raw field if the
    template doesn't look like a query string."""
    body_str = (body_str or "").strip()
    if "=" not in body_str:
        return {"body": body_str}
    out = {}
    for pair in body_str.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            out[k.strip()] = v.strip()
    return out or {"body": body_str}


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
    "txtconnect": _send_txtconnect,
    "custom": _send_custom,
}

PROVIDER_LABELS = {
    "twilio": "Twilio",
    "vonage": "Vonage (Nexmo)",
    "textbelt": "Textbelt",
    "txtconnect": "TxtConnect",
    "custom": "Custom Provider (fully configurable)",
    "none": "None (disabled)",
}
