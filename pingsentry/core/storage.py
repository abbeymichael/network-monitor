"""
Persistence layer for PingSentry.

- Server list, app settings, and log history -> plain JSON (human editable).
- SMS provider credentials -> encrypted with a machine-local key (Fernet)
  so API tokens are not sitting in plaintext on disk.

All file I/O funnels through this module so the rest of the app never
touches paths directly.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import List, Dict, Any

from cryptography.fernet import Fernet, InvalidToken
from platformdirs import user_data_dir

from .models import (
    Server, SmsProviderConfig, AppSettings, LogEntry,
    NotificationRecord, StatusEvent,
)

APP_NAME = "PingSentry"
APP_AUTHOR = "PingSentry"

_lock = threading.Lock()


def data_dir() -> Path:
    d = Path(user_data_dir(APP_NAME, APP_AUTHOR))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _servers_path() -> Path:
    return data_dir() / "servers.json"


def _settings_path() -> Path:
    return data_dir() / "settings.json"


def _sms_secret_path() -> Path:
    return data_dir() / "sms_config.enc"


def _key_path() -> Path:
    return data_dir() / ".keyfile"


def _log_path() -> Path:
    return data_dir() / "history.log.jsonl"


def _notifications_path() -> Path:
    return data_dir() / "notifications.jsonl"


def _events_path() -> Path:
    return data_dir() / "status_events.jsonl"


# --------------------------------------------------------------------------
# Encryption key management
# --------------------------------------------------------------------------

def _get_or_create_key() -> bytes:
    kp = _key_path()
    if kp.exists():
        return kp.read_bytes()
    key = Fernet.generate_key()
    kp.write_bytes(key)
    try:
        os.chmod(kp, 0o600)
    except OSError:
        pass
    return key


def _fernet() -> Fernet:
    return Fernet(_get_or_create_key())


# --------------------------------------------------------------------------
# Servers
# --------------------------------------------------------------------------

def load_servers() -> List[Server]:
    p = _servers_path()
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return [Server.from_dict(item) for item in raw]
    except (json.JSONDecodeError, OSError):
        return []


def save_servers(servers: List[Server]) -> None:
    with _lock:
        p = _servers_path()
        tmp = p.with_suffix(".tmp")
        data = [s.to_dict() for s in servers]
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(p)


# --------------------------------------------------------------------------
# App settings
# --------------------------------------------------------------------------

def load_settings() -> AppSettings:
    p = _settings_path()
    if not p.exists():
        return AppSettings()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return AppSettings.from_dict(raw)
    except (json.JSONDecodeError, OSError):
        return AppSettings()


def save_settings(settings: AppSettings) -> None:
    with _lock:
        p = _settings_path()
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(settings.to_dict(), indent=2), encoding="utf-8")
        tmp.replace(p)


# --------------------------------------------------------------------------
# SMS provider config (encrypted)
# --------------------------------------------------------------------------

def load_sms_config() -> SmsProviderConfig:
    p = _sms_secret_path()
    if not p.exists():
        return SmsProviderConfig()
    try:
        token = p.read_bytes()
        plain = _fernet().decrypt(token)
        raw = json.loads(plain.decode("utf-8"))
        return SmsProviderConfig.from_dict(raw)
    except (InvalidToken, json.JSONDecodeError, OSError):
        return SmsProviderConfig()


def save_sms_config(cfg: SmsProviderConfig) -> None:
    with _lock:
        p = _sms_secret_path()
        tmp = p.with_suffix(".tmp")
        raw = json.dumps(cfg.to_dict()).encode("utf-8")
        token = _fernet().encrypt(raw)
        tmp.write_bytes(token)
        tmp.replace(p)
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass


# --------------------------------------------------------------------------
# History / log (append-only jsonl, capped)
# --------------------------------------------------------------------------

MAX_LOG_LINES = 5000


def append_log(entry: LogEntry) -> None:
    with _lock:
        p = _log_path()
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry.__dict__) + "\n")
        # Trim occasionally to avoid unbounded growth
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
            if len(lines) > MAX_LOG_LINES:
                trimmed = lines[-MAX_LOG_LINES:]
                p.write_text("\n".join(trimmed) + "\n", encoding="utf-8")
        except OSError:
            pass


def load_recent_logs(limit: int = 300) -> List[Dict[str, Any]]:
    p = _log_path()
    if not p.exists():
        return []
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def clear_logs() -> None:
    with _lock:
        p = _log_path()
        if p.exists():
            p.unlink()


# --------------------------------------------------------------------------
# Notifications (append-only jsonl, capped) — powers the bell + Notifications page
# --------------------------------------------------------------------------

MAX_NOTIFICATIONS = 2000


def append_notification(rec: NotificationRecord) -> None:
    with _lock:
        p = _notifications_path()
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec.to_dict()) + "\n")
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
            if len(lines) > MAX_NOTIFICATIONS:
                trimmed = lines[-MAX_NOTIFICATIONS:]
                p.write_text("\n".join(trimmed) + "\n", encoding="utf-8")
        except OSError:
            pass


def load_notifications(limit: int = 500) -> List[NotificationRecord]:
    p = _notifications_path()
    if not p.exists():
        return []
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: List[NotificationRecord] = []
    for line in lines[-limit:]:
        try:
            out.append(NotificationRecord.from_dict(json.loads(line)))
        except json.JSONDecodeError:
            continue
    return out


def mark_notifications_read() -> None:
    """Flag every stored notification as read (called when the bell is opened)."""
    with _lock:
        p = _notifications_path()
        if not p.exists():
            return
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        new_lines = []
        for line in lines:
            try:
                d = json.loads(line)
                d["read"] = True
                new_lines.append(json.dumps(d))
            except json.JSONDecodeError:
                continue
        p.write_text("\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8")


def clear_notifications() -> None:
    with _lock:
        p = _notifications_path()
        if p.exists():
            p.unlink()


# --------------------------------------------------------------------------
# Status events (append-only jsonl, capped) — per-server up/down timeline
# --------------------------------------------------------------------------

MAX_EVENTS = 5000


def append_status_event(ev: StatusEvent) -> None:
    with _lock:
        p = _events_path()
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev.to_dict()) + "\n")
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
            if len(lines) > MAX_EVENTS:
                trimmed = lines[-MAX_EVENTS:]
                p.write_text("\n".join(trimmed) + "\n", encoding="utf-8")
        except OSError:
            pass


def load_status_events(server_id: str = "", limit: int = 500) -> List[StatusEvent]:
    p = _events_path()
    if not p.exists():
        return []
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: List[StatusEvent] = []
    for line in lines:
        try:
            ev = StatusEvent.from_dict(json.loads(line))
        except json.JSONDecodeError:
            continue
        if server_id and ev.server_id != server_id:
            continue
        out.append(ev)
    return out[-limit:]


def clear_status_events() -> None:
    with _lock:
        p = _events_path()
        if p.exists():
            p.unlink()
