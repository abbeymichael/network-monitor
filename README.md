# PingSentry — Desktop Uptime Monitor with SMS Alerts

A slick, configurable Python desktop app that monitors your servers/domains
and texts you when something goes down (and again when it recovers).

## Features
- Add any number of servers by **IP or domain**.
- Per-server check method: **ICMP Ping** or **TCP Port Check** (use TCP when
  a provider/firewall blocks ICMP but the service is actually healthy).
- Configurable check interval, timeout, and "failures before alert" threshold
  per server.
- SMS escalation: cap on repeat "still down" alerts per outage, minutes
  between repeats, and a daily SMS cap per server — avoids alert spam.
- Recovery SMS when a server comes back up.
- Optional quiet hours (suppress SMS overnight, still logs the event).
- SMS providers: **Twilio**, **Vonage (Nexmo)**, **Textbelt**, **TxtConnect**,
  or a fully **Custom Provider** — configure your own HTTP method, JSON/form
  body template, headers, query params, authentication (Bearer / Basic /
  API key in header or query param), and success detection to connect to
  virtually any SMS gateway.
- Encrypted local storage of SMS API credentials (Fernet, machine-local key).
- Dark, modern UI (customtkinter) with live dashboard, activity log, and
  settings screens. Minimizes to system tray.

## Install & Run
```bash
pip install -r requirements.txt
python3 main.py
```

## Notes
- `ping` must be present on the system (standard on Linux/macOS/Windows).
- TCP port checks require only outbound network access, no admin rights.
- Data is stored per-OS user data dir (servers, settings, encrypted SMS
  credentials, activity log).

## Packaging as a standalone executable
```bash
pyinstaller --noconfirm --windowed --name PingSentry main.py
```
