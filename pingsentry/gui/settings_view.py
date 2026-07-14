"""Settings tab: SMS gateway configuration + general app preferences."""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from ..core.models import SmsProviderConfig, AppSettings
from ..core import sms_providers
from . import theme
from .widgets import PrimaryButton, GhostButton, SectionLabel


PROVIDER_KEYS = ["twilio", "vonage", "textbelt", "generic_webhook", "none"]
PROVIDER_DISPLAY = [sms_providers.PROVIDER_LABELS[k] for k in PROVIDER_KEYS]


class SettingsView(ctk.CTkFrame):
    """Wraps a CTkScrollableFrame in a plain CTkFrame.

    NOTE: subclassing CTkScrollableFrame directly is unreliable for
    tab-switching via grid/tkraise in this customtkinter version (the
    widget's true grid-managed element is an internal `_parent_frame`,
    not `self`), so we compose instead of inherit.
    """

    def __init__(
        self,
        master,
        sms_config: SmsProviderConfig,
        app_settings: AppSettings,
        on_save_sms: Callable[[SmsProviderConfig], None],
        on_save_app: Callable[[AppSettings], None],
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.sms_config = sms_config
        self.app_settings = app_settings
        self.on_save_sms = on_save_sms
        self.on_save_app = on_save_app

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True)

        self._build_sms_section()
        self._build_app_section()

    # ------------------------------------------------------------------
    def _card(self, title: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(self.scroll, fg_color=theme.BG_CARD, corner_radius=14)
        card.pack(fill="x", pady=(0, 18), padx=2)
        ctk.CTkLabel(card, text=title, font=theme.title_font(16, "bold")).pack(
            anchor="w", padx=20, pady=(18, 14)
        )
        return card

    # ------------------------------------------------------------------
    def _build_sms_section(self):
        card = self._card("📱  SMS Gateway")

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=20, pady=(0, 8))

        SectionLabel(body, text="Provider").pack(anchor="w", pady=(0, 4))
        current_label = sms_providers.PROVIDER_LABELS.get(self.sms_config.provider, PROVIDER_DISPLAY[0])
        self.provider_menu = ctk.CTkOptionMenu(
            body, values=PROVIDER_DISPLAY, command=self._on_provider_change,
            fg_color=theme.BG_PANEL, button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
        )
        self.provider_menu.set(current_label)
        self.provider_menu.pack(fill="x", pady=(0, 14))

        # Provider-specific credential frames ------------------------------
        self.cred_container = ctk.CTkFrame(body, fg_color="transparent")
        self.cred_container.pack(fill="x")
        self._build_credential_frames()
        self._show_credential_frame(self.sms_config.provider)

        divider = ctk.CTkFrame(body, height=1, fg_color=theme.BORDER)
        divider.pack(fill="x", pady=14)

        # Common fields: from number + recipients ---------------------------
        SectionLabel(body, text="Sender ID / From Number (if applicable)").pack(anchor="w", pady=(0, 4))
        self.from_entry = ctk.CTkEntry(body, placeholder_text="e.g. +15551234567")
        self.from_entry.insert(0, self.sms_config.from_number)
        self.from_entry.pack(fill="x", pady=(0, 14))

        SectionLabel(body, text="Recipient Phone Numbers (comma separated)").pack(anchor="w", pady=(0, 4))
        self.to_entry = ctk.CTkEntry(body, placeholder_text="+15551112222, +15553334444")
        self.to_entry.insert(0, ", ".join(self.sms_config.to_numbers))
        self.to_entry.pack(fill="x", pady=(0, 14))

        self.sms_status_label = ctk.CTkLabel(body, text="", font=theme.font(12), text_color=theme.MUTED, anchor="w", justify="left")
        self.sms_status_label.pack(fill="x", pady=(0, 10))

        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 18))
        PrimaryButton(btn_row, text="Save SMS Settings", command=self._save_sms).pack(side="left")
        GhostButton(btn_row, text="Send Test SMS", command=self._send_test).pack(side="left", padx=10)

    def _build_credential_frames(self):
        self.frames = {}

        # Twilio
        f = ctk.CTkFrame(self.cred_container, fg_color="transparent")
        SectionLabel(f, text="Twilio Account SID").pack(anchor="w", pady=(0, 4))
        self.twilio_sid_entry = ctk.CTkEntry(f, placeholder_text="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        self.twilio_sid_entry.insert(0, self.sms_config.twilio_account_sid)
        self.twilio_sid_entry.pack(fill="x", pady=(0, 10))
        SectionLabel(f, text="Twilio Auth Token").pack(anchor="w", pady=(0, 4))
        self.twilio_token_entry = ctk.CTkEntry(f, placeholder_text="auth token", show="•")
        self.twilio_token_entry.insert(0, self.sms_config.twilio_auth_token)
        self.twilio_token_entry.pack(fill="x", pady=(0, 4))
        self.frames["twilio"] = f

        # Vonage
        f = ctk.CTkFrame(self.cred_container, fg_color="transparent")
        SectionLabel(f, text="Vonage API Key").pack(anchor="w", pady=(0, 4))
        self.vonage_key_entry = ctk.CTkEntry(f, placeholder_text="API key")
        self.vonage_key_entry.insert(0, self.sms_config.vonage_api_key)
        self.vonage_key_entry.pack(fill="x", pady=(0, 10))
        SectionLabel(f, text="Vonage API Secret").pack(anchor="w", pady=(0, 4))
        self.vonage_secret_entry = ctk.CTkEntry(f, placeholder_text="API secret", show="•")
        self.vonage_secret_entry.insert(0, self.sms_config.vonage_api_secret)
        self.vonage_secret_entry.pack(fill="x", pady=(0, 4))
        self.frames["vonage"] = f

        # Textbelt
        f = ctk.CTkFrame(self.cred_container, fg_color="transparent")
        SectionLabel(f, text="Textbelt API Key").pack(anchor="w", pady=(0, 4))
        self.textbelt_key_entry = ctk.CTkEntry(f, placeholder_text="API key")
        self.textbelt_key_entry.insert(0, self.sms_config.textbelt_api_key)
        self.textbelt_key_entry.pack(fill="x", pady=(0, 4))
        self.frames["textbelt"] = f

        # Generic webhook
        f = ctk.CTkFrame(self.cred_container, fg_color="transparent")
        SectionLabel(f, text="Webhook URL").pack(anchor="w", pady=(0, 4))
        self.webhook_url_entry = ctk.CTkEntry(f, placeholder_text="https://your-sms-gateway.com/api/send")
        self.webhook_url_entry.insert(0, self.sms_config.webhook_url)
        self.webhook_url_entry.pack(fill="x", pady=(0, 10))
        SectionLabel(f, text="HTTP Method").pack(anchor="w", pady=(0, 4))
        self.webhook_method_menu = ctk.CTkOptionMenu(f, values=["POST", "GET", "PUT"],
                                                        fg_color=theme.BG_PANEL, button_color=theme.ACCENT,
                                                        button_hover_color=theme.ACCENT_HOVER)
        self.webhook_method_menu.set(self.sms_config.webhook_method or "POST")
        self.webhook_method_menu.pack(fill="x", pady=(0, 10))
        SectionLabel(f, text="Body Template (use {to} and {message} placeholders)").pack(anchor="w", pady=(0, 4))
        self.webhook_body_entry = ctk.CTkTextbox(f, height=70, fg_color=theme.BG_PANEL)
        self.webhook_body_entry.insert("1.0", self.sms_config.webhook_body_template)
        self.webhook_body_entry.pack(fill="x", pady=(0, 4))
        self.frames["generic_webhook"] = f

        # None
        f = ctk.CTkFrame(self.cred_container, fg_color="transparent")
        ctk.CTkLabel(f, text="SMS alerts are disabled.", text_color=theme.MUTED, font=theme.font(12)).pack(anchor="w")
        self.frames["none"] = f

    def _show_credential_frame(self, provider_key: str):
        for key, frame in self.frames.items():
            frame.pack_forget()
        target = self.frames.get(provider_key, self.frames["none"])
        target.pack(fill="x")

    def _on_provider_change(self, display_value: str):
        key = self._display_to_key(display_value)
        self._show_credential_frame(key)

    @staticmethod
    def _display_to_key(display_value: str) -> str:
        for k, v in sms_providers.PROVIDER_LABELS.items():
            if v == display_value:
                return k
        return "none"

    def _collect_sms_config(self) -> SmsProviderConfig:
        provider_key = self._display_to_key(self.provider_menu.get())
        to_numbers = [n.strip() for n in self.to_entry.get().split(",") if n.strip()]
        cfg = SmsProviderConfig(
            provider=provider_key,
            from_number=self.from_entry.get().strip(),
            to_numbers=to_numbers,
            twilio_account_sid=self.twilio_sid_entry.get().strip(),
            twilio_auth_token=self.twilio_token_entry.get().strip(),
            vonage_api_key=self.vonage_key_entry.get().strip(),
            vonage_api_secret=self.vonage_secret_entry.get().strip(),
            textbelt_api_key=self.textbelt_key_entry.get().strip(),
            webhook_url=self.webhook_url_entry.get().strip(),
            webhook_method=self.webhook_method_menu.get(),
            webhook_headers=self.sms_config.webhook_headers,
            webhook_body_template=self.webhook_body_entry.get("1.0", "end").strip(),
        )
        return cfg

    def _save_sms(self):
        cfg = self._collect_sms_config()
        self.sms_config = cfg
        self.on_save_sms(cfg)
        self.sms_status_label.configure(text="✓ SMS settings saved.", text_color=theme.SUCCESS)

    def _send_test(self):
        cfg = self._collect_sms_config()
        self.sms_status_label.configure(text="Sending test SMS...", text_color=theme.MUTED)
        self.update_idletasks()
        ok, info = sms_providers.test_send(cfg)
        if ok:
            self.sms_status_label.configure(text=f"✓ Test SMS sent successfully. ({info})", text_color=theme.SUCCESS)
        else:
            self.sms_status_label.configure(text=f"✕ Test SMS failed: {info}", text_color=theme.DANGER)

    # ------------------------------------------------------------------
    def _build_app_section(self):
        card = self._card("⚙️  App Preferences")
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=20, pady=(0, 8))

        self.start_min_switch = self._switch_row(body, "Start minimized to tray", self.app_settings.start_minimized)
        self.tray_switch = self._switch_row(body, "Minimize to tray on close", self.app_settings.minimize_to_tray)
        self.autostart_switch = self._switch_row(body, "Start monitoring automatically on launch", self.app_settings.launch_monitoring_on_start)
        self.sound_switch = self._switch_row(body, "Play sound on alert", self.app_settings.sound_alerts)

        divider = ctk.CTkFrame(body, height=1, fg_color=theme.BORDER)
        divider.pack(fill="x", pady=14)

        self.quiet_switch = self._switch_row(body, "Enable quiet hours (suppress DOWN SMS, still logged)", self.app_settings.quiet_hours_enabled)

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=(4, 14))
        row.grid_columnconfigure((0, 1), weight=1)
        col1 = ctk.CTkFrame(row, fg_color="transparent")
        col1.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        SectionLabel(col1, text="Quiet Hours Start (HH:MM)").pack(anchor="w", pady=(0, 4))
        self.quiet_start_entry = ctk.CTkEntry(col1, placeholder_text="22:00")
        self.quiet_start_entry.insert(0, self.app_settings.quiet_hours_start)
        self.quiet_start_entry.pack(fill="x")
        col2 = ctk.CTkFrame(row, fg_color="transparent")
        col2.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        SectionLabel(col2, text="Quiet Hours End (HH:MM)").pack(anchor="w", pady=(0, 4))
        self.quiet_end_entry = ctk.CTkEntry(col2, placeholder_text="07:00")
        self.quiet_end_entry.insert(0, self.app_settings.quiet_hours_end)
        self.quiet_end_entry.pack(fill="x")

        self.app_status_label = ctk.CTkLabel(body, text="", font=theme.font(12), text_color=theme.MUTED, anchor="w")
        self.app_status_label.pack(fill="x", pady=(0, 10))

        PrimaryButton(body, text="Save Preferences", command=self._save_app).pack(anchor="w", pady=(0, 18))

    def _switch_row(self, parent, text, initial) -> ctk.CTkSwitch:
        sw = ctk.CTkSwitch(parent, text=text, progress_color=theme.ACCENT, font=theme.font(13))
        if initial:
            sw.select()
        sw.pack(anchor="w", pady=6)
        return sw

    def _save_app(self):
        self.app_settings.start_minimized = bool(self.start_min_switch.get())
        self.app_settings.minimize_to_tray = bool(self.tray_switch.get())
        self.app_settings.launch_monitoring_on_start = bool(self.autostart_switch.get())
        self.app_settings.sound_alerts = bool(self.sound_switch.get())
        self.app_settings.quiet_hours_enabled = bool(self.quiet_switch.get())
        self.app_settings.quiet_hours_start = self.quiet_start_entry.get().strip() or "22:00"
        self.app_settings.quiet_hours_end = self.quiet_end_entry.get().strip() or "07:00"
        self.on_save_app(self.app_settings)
        self.app_status_label.configure(text="✓ Preferences saved.", text_color=theme.SUCCESS)
