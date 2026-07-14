"""Modal dialog for adding / editing a monitored server."""
from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from ..core.models import Server, CheckMethod
from . import theme
from .widgets import PrimaryButton, GhostButton, SectionLabel


class ServerDialog(ctk.CTkToplevel):
    def __init__(self, master, server: Optional[Server], on_save: Callable[[Server], None]):
        super().__init__(master)
        self.on_save = on_save
        self.is_new = server is None
        self.server = server or Server()

        self.title("Add Server" if self.is_new else "Edit Server")
        self.geometry("480x700")
        self.minsize(460, 640)
        self.configure(fg_color=theme.BG_DARK)
        self.resizable(False, True)

        self.grab_set()
        self.transient(master)

        self._build_ui()
        self.after(50, self._center_on_parent)

    def _center_on_parent(self):
        try:
            self.update_idletasks()
            px = self.master.winfo_rootx()
            py = self.master.winfo_rooty()
            pw = self.master.winfo_width()
            ph = self.master.winfo_height()
            w = self.winfo_width()
            h = self.winfo_height()
            x = px + (pw - w) // 2
            y = py + (ph - h) // 2
            self.geometry(f"+{max(x,0)}+{max(y,0)}")
        except Exception:
            pass

    def _build_ui(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=(20, 8))

        s = self.server

        # --- Basics -------------------------------------------------------
        SectionLabel(scroll, text="Server Name").pack(anchor="w", pady=(0, 4))
        self.name_entry = ctk.CTkEntry(scroll, placeholder_text="e.g. Production API")
        self.name_entry.insert(0, s.name)
        self.name_entry.pack(fill="x", pady=(0, 14))

        SectionLabel(scroll, text="IP Address or Domain").pack(anchor="w", pady=(0, 4))
        self.address_entry = ctk.CTkEntry(scroll, placeholder_text="e.g. 203.0.113.10 or example.com")
        self.address_entry.insert(0, s.address)
        self.address_entry.pack(fill="x", pady=(0, 14))

        # --- Check method ---------------------------------------------------
        SectionLabel(scroll, text="Check Method").pack(anchor="w", pady=(0, 4))
        method_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        method_frame.pack(fill="x", pady=(0, 6))
        method_frame.grid_columnconfigure((0, 1), weight=1)
        self.method_var = ctk.StringVar(value=(s.check_method.value if isinstance(s.check_method, CheckMethod) else s.check_method))
        self.ping_radio = ctk.CTkRadioButton(
            method_frame, text="ICMP Ping", variable=self.method_var, value="ping",
            command=self._on_method_change,
        )
        self.tcp_radio = ctk.CTkRadioButton(
            method_frame, text="TCP Port", variable=self.method_var, value="tcp_port",
            command=self._on_method_change,
        )
        self.http_radio = ctk.CTkRadioButton(
            method_frame, text="HTTP / HTTPS", variable=self.method_var, value="http",
            command=self._on_method_change,
        )
        self.dns_radio = ctk.CTkRadioButton(
            method_frame, text="DNS Lookup", variable=self.method_var, value="dns",
            command=self._on_method_change,
        )
        self.ping_radio.grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.tcp_radio.grid(row=0, column=1, sticky="w", pady=(0, 8))
        self.http_radio.grid(row=1, column=0, sticky="w")
        self.dns_radio.grid(row=1, column=1, sticky="w")

        self.method_hint = ctk.CTkLabel(
            scroll, text="", font=theme.font(11), text_color=theme.MUTED, justify="left", anchor="w",
        )
        self.method_hint.pack(anchor="w", pady=(6, 10))

        # -- TCP Port fields --------------------------------------------------
        self.port_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        SectionLabel(self.port_frame, text="TCP Port").pack(anchor="w", pady=(0, 4))
        self.port_entry = ctk.CTkEntry(self.port_frame, placeholder_text="443")
        self.port_entry.insert(0, str(s.port))
        self.port_entry.pack(fill="x", pady=(0, 14))

        # -- HTTP/HTTPS fields -------------------------------------------------
        self.http_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        SectionLabel(self.http_frame, text="URL (leave blank to use the address above with https://)").pack(anchor="w", pady=(0, 4))
        self.http_url_entry = ctk.CTkEntry(self.http_frame, placeholder_text="https://example.com/health")
        self.http_url_entry.insert(0, s.http_url)
        self.http_url_entry.pack(fill="x", pady=(0, 10))

        http_row = ctk.CTkFrame(self.http_frame, fg_color="transparent")
        http_row.pack(fill="x", pady=(0, 10))
        http_row.grid_columnconfigure((0, 1, 2), weight=1)
        hc1 = ctk.CTkFrame(http_row, fg_color="transparent")
        hc1.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        SectionLabel(hc1, text="Method").pack(anchor="w", pady=(0, 4))
        self.http_method_menu = ctk.CTkOptionMenu(
            hc1, values=["GET", "HEAD", "POST"],
            fg_color=theme.BG_PANEL, button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
        )
        self.http_method_menu.set(s.http_method or "GET")
        self.http_method_menu.pack(fill="x")
        hc2 = ctk.CTkFrame(http_row, fg_color="transparent")
        hc2.grid(row=0, column=1, sticky="ew", padx=6)
        SectionLabel(hc2, text="Min Status").pack(anchor="w", pady=(0, 4))
        self.http_status_min_entry = ctk.CTkEntry(hc2, placeholder_text="200")
        self.http_status_min_entry.insert(0, str(s.http_expected_status_min))
        self.http_status_min_entry.pack(fill="x")
        hc3 = ctk.CTkFrame(http_row, fg_color="transparent")
        hc3.grid(row=0, column=2, sticky="ew", padx=(6, 0))
        SectionLabel(hc3, text="Max Status").pack(anchor="w", pady=(0, 4))
        self.http_status_max_entry = ctk.CTkEntry(hc3, placeholder_text="399")
        self.http_status_max_entry.insert(0, str(s.http_expected_status_max))
        self.http_status_max_entry.pack(fill="x")

        SectionLabel(self.http_frame, text="Response Must Contain (optional)").pack(anchor="w", pady=(0, 4))
        self.http_body_contains_entry = ctk.CTkEntry(self.http_frame, placeholder_text="e.g. \"status\":\"ok\"")
        self.http_body_contains_entry.insert(0, s.http_body_contains)
        self.http_body_contains_entry.pack(fill="x", pady=(0, 10))

        self.http_tls_switch = ctk.CTkSwitch(self.http_frame, text="Verify TLS/SSL certificate", progress_color=theme.ACCENT)
        if s.http_verify_tls:
            self.http_tls_switch.select()
        self.http_tls_switch.pack(anchor="w", pady=(0, 14))

        # -- DNS lookup fields -------------------------------------------------
        self.dns_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        dns_row = ctk.CTkFrame(self.dns_frame, fg_color="transparent")
        dns_row.pack(fill="x", pady=(0, 10))
        dns_row.grid_columnconfigure((0, 1), weight=1)
        dc1 = ctk.CTkFrame(dns_row, fg_color="transparent")
        dc1.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        SectionLabel(dc1, text="Record Type").pack(anchor="w", pady=(0, 4))
        self.dns_type_menu = ctk.CTkOptionMenu(
            dc1, values=["A", "AAAA", "CNAME", "MX", "TXT", "NS"],
            fg_color=theme.BG_PANEL, button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
        )
        self.dns_type_menu.set((s.dns_record_type or "A").upper())
        self.dns_type_menu.pack(fill="x")
        dc2 = ctk.CTkFrame(dns_row, fg_color="transparent")
        dc2.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        SectionLabel(dc2, text="Custom DNS Resolver (optional)").pack(anchor="w", pady=(0, 4))
        self.dns_resolver_entry = ctk.CTkEntry(dc2, placeholder_text="e.g. 8.8.8.8")
        self.dns_resolver_entry.insert(0, s.dns_resolver)
        self.dns_resolver_entry.pack(fill="x")

        SectionLabel(self.dns_frame, text="Resolved Value Must Contain (optional)").pack(anchor="w", pady=(0, 4))
        self.dns_expected_entry = ctk.CTkEntry(self.dns_frame, placeholder_text="e.g. 93.184.216.34")
        self.dns_expected_entry.insert(0, s.dns_expected_value)
        self.dns_expected_entry.pack(fill="x", pady=(0, 14))

        # --- Timing -----------------------------------------------------------
        row = ctk.CTkFrame(scroll, fg_color="transparent")
        row.pack(fill="x", pady=(0, 14))
        row.grid_columnconfigure((0, 1), weight=1)

        col1 = ctk.CTkFrame(row, fg_color="transparent")
        col1.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        SectionLabel(col1, text="Check Interval (sec)").pack(anchor="w", pady=(0, 4))
        self.interval_entry = ctk.CTkEntry(col1, placeholder_text="60")
        self.interval_entry.insert(0, str(s.interval_seconds))
        self.interval_entry.pack(fill="x")

        col2 = ctk.CTkFrame(row, fg_color="transparent")
        col2.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        SectionLabel(col2, text="Timeout (sec)").pack(anchor="w", pady=(0, 4))
        self.timeout_entry = ctk.CTkEntry(col2, placeholder_text="5")
        self.timeout_entry.insert(0, str(s.timeout_seconds))
        self.timeout_entry.pack(fill="x")

        SectionLabel(scroll, text="Consecutive Failures Before Marking Down").pack(anchor="w", pady=(0, 4))
        self.fail_threshold_entry = ctk.CTkEntry(scroll, placeholder_text="2")
        self.fail_threshold_entry.insert(0, str(s.failures_before_alert))
        self.fail_threshold_entry.pack(fill="x", pady=(0, 14))

        # --- Alert escalation ---------------------------------------------------
        divider = ctk.CTkFrame(scroll, height=1, fg_color=theme.BORDER)
        divider.pack(fill="x", pady=(4, 14))

        SectionLabel(scroll, text="SMS Alert Behaviour").pack(anchor="w", pady=(0, 8))

        row2 = ctk.CTkFrame(scroll, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 14))
        row2.grid_columnconfigure((0, 1), weight=1)

        col3 = ctk.CTkFrame(row2, fg_color="transparent")
        col3.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        SectionLabel(col3, text="Max Repeat Alerts / Outage").pack(anchor="w", pady=(0, 4))
        self.max_alerts_entry = ctk.CTkEntry(col3, placeholder_text="5")
        self.max_alerts_entry.insert(0, str(s.max_alerts_per_incident))
        self.max_alerts_entry.pack(fill="x")

        col4 = ctk.CTkFrame(row2, fg_color="transparent")
        col4.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        SectionLabel(col4, text="Minutes Between Repeats").pack(anchor="w", pady=(0, 4))
        self.resend_interval_entry = ctk.CTkEntry(col4, placeholder_text="30")
        self.resend_interval_entry.insert(0, str(s.resend_interval_minutes))
        self.resend_interval_entry.pack(fill="x")

        SectionLabel(scroll, text="Max SMS Alerts Per Day (this server)").pack(anchor="w", pady=(0, 4))
        self.daily_cap_entry = ctk.CTkEntry(scroll, placeholder_text="2")
        self.daily_cap_entry.insert(0, str(s.daily_alert_cap))
        self.daily_cap_entry.pack(fill="x", pady=(0, 14))

        self.recovery_switch = ctk.CTkSwitch(scroll, text="Notify me when it recovers", progress_color=theme.ACCENT)
        if s.notify_on_recovery:
            self.recovery_switch.select()
        self.recovery_switch.pack(anchor="w", pady=(0, 14))

        SectionLabel(scroll, text="Notes (optional)").pack(anchor="w", pady=(0, 4))
        self.notes_entry = ctk.CTkEntry(scroll, placeholder_text="Optional notes...")
        self.notes_entry.insert(0, s.notes)
        self.notes_entry.pack(fill="x", pady=(0, 6))

        self.error_label = ctk.CTkLabel(scroll, text="", text_color=theme.DANGER, font=theme.font(12))
        self.error_label.pack(anchor="w", pady=(6, 0))

        self._on_method_change()

        # --- Footer buttons ---------------------------------------------------
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(4, 20))
        GhostButton(footer, text="Cancel", command=self.destroy).pack(side="right", padx=(8, 0))
        PrimaryButton(footer, text="Save Server", command=self._save).pack(side="right")

    _METHOD_HINTS = {
        "ping": "Sends an ICMP echo (ping) request to the address. Good for servers, "
                "routers and any host that responds to ping.",
        "tcp_port": "Attempts a raw TCP connection to the given port (e.g. 22 SSH, "
                    "80/443 web, 3306 MySQL). Good when ICMP is blocked by a firewall.",
        "http": "Sends an HTTP/HTTPS request to the URL and checks the response "
                "status code (and optionally the response body). Best for websites and APIs.",
        "dns": "Resolves a DNS record for the address and optionally checks the "
               "resolved value. Useful for verifying DNS propagation / records.",
    }

    def _on_method_change(self):
        method = self.method_var.get()
        self.method_hint.configure(text=self._METHOD_HINTS.get(method, ""))

        if method == "tcp_port":
            self.port_frame.pack(fill="x", after=self.method_hint)
        else:
            self.port_frame.pack_forget()

        if method == "http":
            self.http_frame.pack(fill="x", after=self.method_hint)
        else:
            self.http_frame.pack_forget()

        if method == "dns":
            self.dns_frame.pack(fill="x", after=self.method_hint)
        else:
            self.dns_frame.pack_forget()

    def _save(self):
        name = self.name_entry.get().strip() or "Unnamed Server"
        address = self.address_entry.get().strip()
        method = self.method_var.get()
        http_url = self.http_url_entry.get().strip()

        # Address is required for Ping / TCP Port / DNS. For HTTP checks, either
        # the address or the dedicated URL field must be filled in.
        if method == "http":
            if not address and not http_url:
                self.error_label.configure(text="Please enter a URL (or an address above).")
                return
        elif not address:
            self.error_label.configure(text="Please enter an IP address or domain.")
            return

        try:
            port = int(self.port_entry.get().strip() or 443)
            interval = max(5, int(self.interval_entry.get().strip() or 60))
            timeout = max(1, int(self.timeout_entry.get().strip() or 5))
            fail_threshold = max(1, int(self.fail_threshold_entry.get().strip() or 2))
            max_alerts = max(1, int(self.max_alerts_entry.get().strip() or 5))
            resend_interval = max(1, int(self.resend_interval_entry.get().strip() or 30))
            daily_cap = max(0, int(self.daily_cap_entry.get().strip() or 2))
            http_status_min = int(self.http_status_min_entry.get().strip() or 200)
            http_status_max = int(self.http_status_max_entry.get().strip() or 399)
        except ValueError:
            self.error_label.configure(text="Please enter valid numbers for the numeric fields.")
            return

        s = self.server
        s.name = name
        s.address = address
        s.check_method = CheckMethod(method)
        s.port = port
        s.interval_seconds = interval
        s.timeout_seconds = timeout
        s.failures_before_alert = fail_threshold
        s.max_alerts_per_incident = max_alerts
        s.resend_interval_minutes = resend_interval
        s.daily_alert_cap = daily_cap
        s.notify_on_recovery = bool(self.recovery_switch.get())
        s.notes = self.notes_entry.get().strip()

        # HTTP/HTTPS check fields
        s.http_url = http_url
        s.http_method = self.http_method_menu.get() or "GET"
        s.http_expected_status_min = http_status_min
        s.http_expected_status_max = http_status_max
        s.http_body_contains = self.http_body_contains_entry.get().strip()
        s.http_verify_tls = bool(self.http_tls_switch.get())

        # DNS lookup check fields
        s.dns_record_type = (self.dns_type_menu.get() or "A").upper()
        s.dns_resolver = self.dns_resolver_entry.get().strip()
        s.dns_expected_value = self.dns_expected_entry.get().strip()

        self.on_save(s)
        self.destroy()
