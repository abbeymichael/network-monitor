"""
Cross-platform, best-effort sound & desktop-notification helper.

Two responsibilities:

  * play_status_sound(is_up) — plays the bundled ``on.wav`` / ``off.wav``
    on the local PC when a monitored target recovers / goes down. All
    playback happens on a background thread so it never blocks monitoring,
    and every backend is wrapped in defensive try/except so a machine
    without audio simply stays silent instead of crashing.

  * notify_desktop(title, message) — fires a native OS toast/notification
    where a lightweight, dependency-free path exists (Windows / macOS).

Sound backends attempted, in order of preference:
  - Windows:  winsound.PlaySound (built-in, async)
  - macOS:    afplay
  - Linux:    paplay / aplay / ffplay / (simpleaudio if installed)
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

_IS_WINDOWS = platform.system().lower() == "windows"
_IS_MAC = platform.system().lower() == "darwin"


def _asset_dir() -> Path:
    """Locate the bundled assets folder, working both from source and when
    frozen by PyInstaller (which unpacks data files into ``sys._MEIPASS``)."""
    # PyInstaller one-file: data files live under _MEIPASS
    meipass = getattr(sys, "_MEIPASS", None)
    candidates = []
    if meipass:
        candidates.append(Path(meipass) / "pingsentry" / "assets")
        candidates.append(Path(meipass) / "assets")
    here = Path(__file__).resolve().parent.parent  # -> pingsentry/
    candidates.append(here / "assets")
    candidates.append(here.parent)  # repo root (dev fallback: on.wav/off.wav there)
    for c in candidates:
        if c.exists():
            return c
    return here / "assets"


def _sound_path(is_up: bool) -> Optional[Path]:
    name = "on.wav" if is_up else "off.wav"
    d = _asset_dir()
    p = d / name
    if p.exists():
        return p
    # last-ditch: repo root
    alt = Path(__file__).resolve().parent.parent.parent / name
    return alt if alt.exists() else None


def _no_window_kwargs() -> dict:
    if not _IS_WINDOWS:
        return {}
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    return {"creationflags": creationflags}


def _play_file_blocking(path: Path) -> None:
    """Play a wav file synchronously (called on a worker thread)."""
    try:
        if _IS_WINDOWS:
            import winsound  # type: ignore
            winsound.PlaySound(str(path), winsound.SND_FILENAME)
            return
        if _IS_MAC:
            afplay = shutil.which("afplay")
            if afplay:
                subprocess.run([afplay, str(path)], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
                return
        # Linux / generic: try common CLI players first (no extra deps).
        for player in ("paplay", "aplay", "ffplay"):
            exe = shutil.which(player)
            if not exe:
                continue
            cmd = [exe, str(path)]
            if player == "ffplay":
                cmd = [exe, "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           **_no_window_kwargs())
            return
        # Optional pure-python backend if the user installed it.
        try:
            import simpleaudio  # type: ignore
            wave_obj = simpleaudio.WaveObject.from_wave_file(str(path))
            wave_obj.play().wait_done()
            return
        except Exception:
            pass
    except Exception:
        # Audio must never be able to take the app down.
        pass


def play_status_sound(is_up: bool) -> None:
    """Fire-and-forget playback of the up/down notification sound."""
    path = _sound_path(is_up)
    if not path:
        return
    threading.Thread(
        target=_play_file_blocking, args=(path,), daemon=True,
        name="PingSentry-Sound",
    ).start()


def notify_desktop(title: str, message: str) -> None:
    """Best-effort native OS notification (silent no-op if unsupported)."""
    def _worker():
        try:
            if _IS_MAC:
                osa = shutil.which("osascript")
                if osa:
                    safe_t = title.replace('"', "'")
                    safe_m = message.replace('"', "'")
                    subprocess.run(
                        [osa, "-e", f'display notification "{safe_m}" with title "{safe_t}"'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    return
            if os.name == "posix" and not _IS_MAC:
                notify = shutil.which("notify-send")
                if notify:
                    subprocess.run([notify, title, message],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return
            # Windows toast via PowerShell BurntToast is not guaranteed; the
            # in-app toast + tray already cover Windows, so we stay silent here.
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True, name="PingSentry-Notify").start()
