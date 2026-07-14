# PingSentry — Desktop Uptime Monitor with SMS Alerts

A slick, configurable Python desktop app that monitors your servers/domains
and texts you when something goes down (and again when it recovers).

## Features
- Add any number of servers by **IP or domain**.
- Per-server check method — pick whichever fits the target:
  - **ICMP Ping** — classic ping, great for servers/routers/devices.
  - **TCP Port** — raw connect to a port (22, 80, 443, 3306, ...); use this
    when a firewall blocks ICMP but the service itself is reachable.
  - **HTTP / HTTPS** — request a URL and validate the status code (and
    optionally the response body); best for websites and APIs, since "the
    port is open" isn't the same as "the app is actually healthy".
  - **DNS Lookup** — resolve an A/AAAA/CNAME/MX/TXT/NS record (optionally
    against a custom resolver, with an optional expected-value check); useful
    for monitoring domain/DNS health independently of the service.
- Configurable check interval, timeout, and "failures before alert" threshold
  per server.
- SMS escalation: cap on repeat "still down" alerts per outage, minutes
  between repeats, and a daily SMS cap per server — avoids alert spam.
- Recovery SMS when a server comes back up.
- **Hard cap of 5 SMS per outage** (plus the per-server/day cap) so a long
  outage never floods you with texts.
- **Live heartbeat animation** on every target — a breathing pulse that
  flashes an expanding ring each time a check actually lands, so you can
  *see* monitoring is happening.
- **PC sound alerts**: plays `off.wav` when a target goes down and `on.wav`
  when it recovers (toggle in Settings). All ping checks run **silently** —
  no console/terminal window ever flashes on screen (Windows).
- **In-app notifications**: slide-in toast pop-ups plus a **notification bell**
  (with unread badge) in the top bar. A dedicated **Notifications page**
  records every SMS — sent, failed (with the exact error), suppressed, and
  recovery/test messages — filterable by status.
- **Per-target detail page**: uptime %, current-state duration, lifetime
  up/down totals, SMS-sent count, a latency sparkline, and a full up/down
  timeline with per-incident durations and reasons.
- Optional quiet hours (suppress SMS overnight, still logs the event).
- SMS providers: **Twilio**, **Vonage (Nexmo)**, **Textbelt**, **TxtConnect**,
  or a fully **Custom Provider** — configure your own HTTP method, JSON/form
  body template, headers, query params, authentication (Bearer / Basic /
  API key in header or query param), and success detection to connect to
  virtually any SMS gateway.
- Encrypted local storage of SMS API credentials (Fernet, machine-local key).
- Dark, modern UI (customtkinter) with live dashboard, activity log, and
  settings screens. **Minimizes to the system tray** and keeps monitoring in
  the background — while in the tray, alerts are delivered as **native OS
  desktop notifications** (Action Center toast on Windows, Notification Center
  on macOS, `notify-send` on Linux) plus a tray-icon balloon, and the up/down
  **sounds still play**. The notification-bell unread count keeps ticking so
  nothing is missed when you re-open the window.

## Install & Run
```bash
pip install -r requirements.txt
python3 main.py
```

## Notes
- `ping` must be present on the system (standard on Linux/macOS/Windows).
- TCP port and HTTP/HTTPS checks require only outbound network access, no
  admin rights.
- DNS lookups use the `dnspython` package when available (installed via
  `requirements.txt`); if it's missing, a limited built-in fallback still
  handles A/AAAA lookups via the system resolver.
- Data is stored per-OS user data dir (servers, settings, encrypted SMS
  credentials, activity log).

## Building an installable / standalone executable

The repo ships a ready-to-use **PyInstaller spec** (`PingSentry.spec`) and
one-command build scripts. The spec bundles the notification sounds
(`on.wav` / `off.wav`) as data files so they ship inside the frozen app —
resolved from `sys._MEIPASS` at runtime — and builds a **windowed** binary
(no console window; ping/subprocess checks additionally use
`CREATE_NO_WINDOW` on Windows so no terminal ever pops up).

### One-command build

**Windows** (Command Prompt / PowerShell):
```bat
build.bat
```
This installs dependencies, produces `dist\PingSentry.exe`, and — if
[Inno Setup](https://jrsoftware.org/isdl.php) (`iscc`) is installed — also
compiles the full installer `dist\PingSentry-Setup.exe`.

**macOS / Linux:**
```bash
./build.sh
```
Produces `dist/PingSentry` (Linux executable) or `dist/PingSentry.app`
(macOS bundle). On macOS you can then wrap it into a DMG:
```bash
hdiutil create -volname PingSentry -srcfolder dist/PingSentry.app \
  -ov -format UDZO dist/PingSentry.dmg
```

### Building the Windows installer

`installer.iss` is an [Inno Setup](https://jrsoftware.org/isdl.php) script
that turns `dist\PingSentry.exe` into a proper installer
(`dist\PingSentry-Setup.exe`). It:

- installs into *Program Files* (per-user, no admin required),
- creates Start-menu and optional desktop shortcuts, and
- can register PingSentry to **launch at Windows startup** so monitoring
  resumes automatically after a reboot.

```bat
REM 1) build the exe, 2) compile the installer
build.bat
iscc installer.iss     REM (build.bat runs this automatically if iscc is on PATH)
```

### Manual PyInstaller invocation (equivalent to the spec)
If you prefer not to use the spec/scripts:

```powershell
# Windows (note the ';' data separator)
pyinstaller --noconfirm --windowed --name PingSentry `
  --add-data "pingsentry/assets/on.wav;pingsentry/assets" `
  --add-data "pingsentry/assets/off.wav;pingsentry/assets" main.py
```
```bash
# macOS / Linux (note the ':' data separator)
pyinstaller --noconfirm --windowed --name PingSentry \
  --add-data "pingsentry/assets/on.wav:pingsentry/assets" \
  --add-data "pingsentry/assets/off.wav:pingsentry/assets" main.py
```
