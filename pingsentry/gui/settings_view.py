"""Settings tab: SMS gateway configuration + general app preferences."""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from ..core.models import SmsProviderConfig, AppSettings
from ..core import sms_providers
from . import theme
from .widgets import PrimaryButton, GhostButton, SectionLabel


PROVIDER_KEYS = ["twilio", "vonage", "textbelt", "txtconnect", "custom", "none"]
PROVIDER_DISPLAY = [sms_providers.PROVIDER_LABELS[k] for k in PROVIDER_KEYS]

AUTH_TYPE_KEYS = ["none", "bearer", "basic", "api_key_header", "api_key_query"]
AUTH_TYPE_DISPLAY = {
    "none": "No Authentication",
    "bearer": "Bearer Token",
    "basic": "Basic Auth (username/password)",
    "api_key_header": "API Key in Header",
    "api_key_query": "API Key in Query Parameter",
}

CONTENT_TYPE_KEYS = ["auto", "json", "form"]
CONTENT_TYPE_DISPLAY = {
    "auto": "Auto-detect (from body template)",
    "json": "JSON",
    "form": "Form (x-www-form-urlencoded)",
}

SUCCESS_CHECK_KEYS = ["status_code", "json_field"]
SUCCESS_CHECK_DISPLAY = {
    "status_code": "Any 2xx HTTP status code",
    "json_field": "Specific field in JSON response",
}


def _display_to_key_in(display_value: str, mapping: dict) -> str:
    for k, v in mapping.items():
        if v == display_value:
            return k
    return next(iter(mapping))


def _dict_to_lines(d: dict) -> str:
    return "\n".join(f"{k}: {v}" for k, v in (d or {}).items())


def _lines_to_dict(text: str, sep: str = ":") -> dict:
    out = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or sep not in line:
            continue
        k, v = line.split(sep, 1)
        k = k.strip()
        v = v.strip()
        if k:
            out[k] = v
    return out


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
        card = self._card("\u260e  SMS Gateway")

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

        # TxtConnect
        f = ctk.CTkFrame(self.cred_container, fg_color="transparent")
        SectionLabel(f, text="TxtConnect API Secret (Bearer Token)").pack(anchor="w", pady=(0, 4))
        self.txtconnect_secret_entry = ctk.CTkEntry(f, placeholder_text="your API secret", show="•")
        self.txtconnect_secret_entry.insert(0, self.sms_config.txtconnect_api_secret)
        self.txtconnect_secret_entry.pack(fill="x", pady=(0, 10))
        SectionLabel(f, text="API Endpoint").pack(anchor="w", pady=(0, 4))
        self.txtconnect_endpoint_entry = ctk.CTkEntry(f, placeholder_text="https://api.txtconnect.net/dev/api/sms/send")
        self.txtconnect_endpoint_entry.insert(0, self.sms_config.txtconnect_endpoint)
        self.txtconnect_endpoint_entry.pack(fill="x", pady=(0, 10))
        self.txtconnect_unicode_switch = ctk.CTkSwitch(
            f, text="Send as unicode SMS", progress_color=theme.ACCENT, font=theme.font(13)
        )
        if self.sms_config.txtconnect_unicode:
            self.txtconnect_unicode_switch.select()
        self.txtconnect_unicode_switch.pack(anchor="w", pady=(0, 4))
        hint = ctk.CTkLabel(
            f, text="Uses the 'Sender ID / From Number' field below as the sender name.",
            font=theme.font(11), text_color=theme.MUTED, anchor="w",
        )
        hint.pack(anchor="w", pady=(4, 4))
        self.frames["txtconnect"] = f

        # Custom provider - fully configurable HTTP SMS gateway
        f = ctk.CTkFrame(self.cred_container, fg_color="transparent")
        self._build_custom_provider_frame(f)
        self.frames["custom"] = f

        # None
        f = ctk.CTkFrame(self.cred_container, fg_color="transparent")
        ctk.CTkLabel(f, text="SMS alerts are disabled.", text_color=theme.MUTED, font=theme.font(12)).pack(anchor="w")
        self.frames["none"] = f

    def _build_custom_provider_frame(self, f):
        cfg = self.sms_config

        ctk.CTkLabel(
            f, text="Connect to any custom HTTP SMS gateway by configuring the request below.",
            font=theme.font(11), text_color=theme.MUTED, anchor="w", justify="left",
        ).pack(anchor="w", pady=(0, 10))

        SectionLabel(f, text="Request URL").pack(anchor="w", pady=(0, 4))
        self.custom_url_entry = ctk.CTkEntry(f, placeholder_text="https://your-sms-gateway.com/api/send")
        self.custom_url_entry.insert(0, cfg.webhook_url)
        self.custom_url_entry.pack(fill="x", pady=(0, 10))

        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill="x", pady=(0, 10))
        row.grid_columnconfigure((0, 1), weight=1)
        col1 = ctk.CTkFrame(row, fg_color="transparent")
        col1.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        SectionLabel(col1, text="HTTP Method").pack(anchor="w", pady=(0, 4))
        self.custom_method_menu = ctk.CTkOptionMenu(
            col1, values=["POST", "GET", "PUT", "PATCH"],
            fg_color=theme.BG_PANEL, button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
        )
        self.custom_method_menu.set(cfg.webhook_method or "POST")
        self.custom_method_menu.pack(fill="x")
        col2 = ctk.CTkFrame(row, fg_color="transparent")
        col2.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        SectionLabel(col2, text="Body Content-Type").pack(anchor="w", pady=(0, 4))
        self.custom_content_type_menu = ctk.CTkOptionMenu(
            col2, values=[CONTENT_TYPE_DISPLAY[k] for k in CONTENT_TYPE_KEYS],
            fg_color=theme.BG_PANEL, button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
        )
        self.custom_content_type_menu.set(CONTENT_TYPE_DISPLAY.get(cfg.webhook_content_type, CONTENT_TYPE_DISPLAY["auto"]))
        self.custom_content_type_menu.pack(fill="x")

        SectionLabel(f, text="Body Template (use {to}, {message}, {from} placeholders)").pack(anchor="w", pady=(0, 4))
        self.custom_body_entry = ctk.CTkTextbox(f, height=64, fg_color=theme.BG_PANEL)
        self.custom_body_entry.insert("1.0", cfg.webhook_body_template)
        self.custom_body_entry.pack(fill="x", pady=(0, 10))

        SectionLabel(f, text="Extra Headers (one per line: Name: Value)").pack(anchor="w", pady=(0, 4))
        self.custom_headers_entry = ctk.CTkTextbox(f, height=54, fg_color=theme.BG_PANEL)
        self.custom_headers_entry.insert("1.0", _dict_to_lines(cfg.webhook_headers))
        self.custom_headers_entry.pack(fill="x", pady=(0, 10))

        SectionLabel(f, text="Extra Query Parameters (one per line: name=value)").pack(anchor="w", pady=(0, 4))
        self.custom_params_entry = ctk.CTkTextbox(f, height=54, fg_color=theme.BG_PANEL)
        self.custom_params_entry.insert("1.0", _dict_to_lines(cfg.webhook_query_params))
        self.custom_params_entry.pack(fill="x", pady=(0, 10))

        divider = ctk.CTkFrame(f, height=1, fg_color=theme.BORDER)
        divider.pack(fill="x", pady=10)

        SectionLabel(f, text="Authentication").pack(anchor="w", pady=(0, 4))
        self.custom_auth_menu = ctk.CTkOptionMenu(
            f, values=[AUTH_TYPE_DISPLAY[k] for k in AUTH_TYPE_KEYS], command=self._on_custom_auth_change,
            fg_color=theme.BG_PANEL, button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
        )
        self.custom_auth_menu.set(AUTH_TYPE_DISPLAY.get(cfg.webhook_auth_type, AUTH_TYPE_DISPLAY["none"]))
        self.custom_auth_menu.pack(fill="x", pady=(0, 10))

        self.custom_auth_frames = {}

        # bearer / api_key_header share the "token + header name" shape
        for key, token_label, header_default in (
            ("bearer", "Bearer Token", "Authorization"),
            ("api_key_header", "API Key Value", "X-API-Key"),
        ):
            af = ctk.CTkFrame(f, fg_color="transparent")
            SectionLabel(af, text=token_label).pack(anchor="w", pady=(0, 4))
            token_entry = ctk.CTkEntry(af, placeholder_text=token_label, show="•")
            token_entry.insert(0, cfg.webhook_auth_token)
            token_entry.pack(fill="x", pady=(0, 8))
            SectionLabel(af, text="Header Name").pack(anchor="w", pady=(0, 4))
            header_entry = ctk.CTkEntry(af, placeholder_text=header_default)
            header_entry.insert(0, cfg.webhook_auth_header_name or header_default)
            header_entry.pack(fill="x", pady=(0, 4))
            self.custom_auth_frames[key] = af
            if key == "bearer":
                self.custom_bearer_token_entry = token_entry
                self.custom_bearer_header_entry = header_entry
            else:
                self.custom_apikey_header_token_entry = token_entry
                self.custom_apikey_header_name_entry = header_entry

        af = ctk.CTkFrame(f, fg_color="transparent")
        SectionLabel(af, text="API Key Value").pack(anchor="w", pady=(0, 4))
        self.custom_apikey_query_token_entry = ctk.CTkEntry(af, placeholder_text="API key", show="•")
        self.custom_apikey_query_token_entry.insert(0, cfg.webhook_auth_token)
        self.custom_apikey_query_token_entry.pack(fill="x", pady=(0, 8))
        SectionLabel(af, text="Query Parameter Name").pack(anchor="w", pady=(0, 4))
        self.custom_apikey_query_name_entry = ctk.CTkEntry(af, placeholder_text="api_key")
        self.custom_apikey_query_name_entry.insert(0, cfg.webhook_auth_query_name or "api_key")
        self.custom_apikey_query_name_entry.pack(fill="x", pady=(0, 4))
        self.custom_auth_frames["api_key_query"] = af

        af = ctk.CTkFrame(f, fg_color="transparent")
        SectionLabel(af, text="Username").pack(anchor="w", pady=(0, 4))
        self.custom_basic_user_entry = ctk.CTkEntry(af, placeholder_text="username")
        self.custom_basic_user_entry.insert(0, cfg.webhook_basic_username)
        self.custom_basic_user_entry.pack(fill="x", pady=(0, 8))
        SectionLabel(af, text="Password").pack(anchor="w", pady=(0, 4))
        self.custom_basic_pass_entry = ctk.CTkEntry(af, placeholder_text="password", show="•")
        self.custom_basic_pass_entry.insert(0, cfg.webhook_basic_password)
        self.custom_basic_pass_entry.pack(fill="x", pady=(0, 4))
        self.custom_auth_frames["basic"] = af

        self.custom_auth_frames["none"] = ctk.CTkFrame(f, fg_color="transparent")

        self.custom_auth_container = f
        self._show_custom_auth_frame(cfg.webhook_auth_type or "none")

        divider2 = ctk.CTkFrame(f, height=1, fg_color=theme.BORDER)
        divider2.pack(fill="x", pady=10)

        SectionLabel(f, text="Success Detection").pack(anchor="w", pady=(0, 4))
        self.custom_success_menu = ctk.CTkOptionMenu(
            f, values=[SUCCESS_CHECK_DISPLAY[k] for k in SUCCESS_CHECK_KEYS], command=self._on_custom_success_change,
            fg_color=theme.BG_PANEL, button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
        )
        self.custom_success_menu.set(SUCCESS_CHECK_DISPLAY.get(cfg.webhook_success_check, SUCCESS_CHECK_DISPLAY["status_code"]))
        self.custom_success_menu.pack(fill="x", pady=(0, 10))

        self.custom_json_field_frame = ctk.CTkFrame(f, fg_color="transparent")
        row3 = ctk.CTkFrame(self.custom_json_field_frame, fg_color="transparent")
        row3.pack(fill="x")
        row3.grid_columnconfigure((0, 1), weight=1)
        colA = ctk.CTkFrame(row3, fg_color="transparent")
        colA.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        SectionLabel(colA, text="JSON Field Path (e.g. data.status)").pack(anchor="w", pady=(0, 4))
        self.custom_success_path_entry = ctk.CTkEntry(colA, placeholder_text="data.status")
        self.custom_success_path_entry.insert(0, cfg.webhook_success_json_path)
        self.custom_success_path_entry.pack(fill="x")
        colB = ctk.CTkFrame(row3, fg_color="transparent")
        colB.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        SectionLabel(colB, text="Expected Value").pack(anchor="w", pady=(0, 4))
        self.custom_success_value_entry = ctk.CTkEntry(colB, placeholder_text="success")
        self.custom_success_value_entry.insert(0, cfg.webhook_success_json_value)
        self.custom_success_value_entry.pack(fill="x")
        if (cfg.webhook_success_check or "status_code") == "json_field":
            self.custom_json_field_frame.pack(fill="x", pady=(0, 4))

    def _on_custom_auth_change(self, display_value: str):
        key = _display_to_key_in(display_value, AUTH_TYPE_DISPLAY)
        self._show_custom_auth_frame(key)

    def _show_custom_auth_frame(self, key: str):
        for frame in self.custom_auth_frames.values():
            frame.pack_forget()
        self.custom_auth_frames.get(key, self.custom_auth_frames["none"]).pack(fill="x", pady=(0, 4))

    def _on_custom_success_change(self, display_value: str):
        key = _display_to_key_in(display_value, SUCCESS_CHECK_DISPLAY)
        if key == "json_field":
            self.custom_json_field_frame.pack(fill="x", pady=(0, 4))
        else:
            self.custom_json_field_frame.pack_forget()

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

        auth_key = _display_to_key_in(self.custom_auth_menu.get(), AUTH_TYPE_DISPLAY)
        if auth_key == "bearer":
            auth_token = self.custom_bearer_token_entry.get().strip()
            auth_header_name = self.custom_bearer_header_entry.get().strip() or "Authorization"
            auth_query_name = "api_key"
        elif auth_key == "api_key_header":
            auth_token = self.custom_apikey_header_token_entry.get().strip()
            auth_header_name = self.custom_apikey_header_name_entry.get().strip() or "X-API-Key"
            auth_query_name = "api_key"
        elif auth_key == "api_key_query":
            auth_token = self.custom_apikey_query_token_entry.get().strip()
            auth_header_name = "Authorization"
            auth_query_name = self.custom_apikey_query_name_entry.get().strip() or "api_key"
        else:
            auth_token = ""
            auth_header_name = "Authorization"
            auth_query_name = "api_key"

        success_key = _display_to_key_in(self.custom_success_menu.get(), SUCCESS_CHECK_DISPLAY)

        cfg = SmsProviderConfig(
            provider=provider_key,
            from_number=self.from_entry.get().strip(),
            to_numbers=to_numbers,
            twilio_account_sid=self.twilio_sid_entry.get().strip(),
            twilio_auth_token=self.twilio_token_entry.get().strip(),
            vonage_api_key=self.vonage_key_entry.get().strip(),
            vonage_api_secret=self.vonage_secret_entry.get().strip(),
            textbelt_api_key=self.textbelt_key_entry.get().strip(),
            txtconnect_api_secret=self.txtconnect_secret_entry.get().strip(),
            txtconnect_endpoint=self.txtconnect_endpoint_entry.get().strip() or "https://api.txtconnect.net/dev/api/sms/send",
            txtconnect_unicode=bool(self.txtconnect_unicode_switch.get()),
            webhook_url=self.custom_url_entry.get().strip(),
            webhook_method=self.custom_method_menu.get(),
            webhook_content_type=_display_to_key_in(self.custom_content_type_menu.get(), CONTENT_TYPE_DISPLAY),
            webhook_auth_type=auth_key,
            webhook_auth_token=auth_token,
            webhook_auth_header_name=auth_header_name,
            webhook_auth_query_name=auth_query_name,
            webhook_basic_username=self.custom_basic_user_entry.get().strip(),
            webhook_basic_password=self.custom_basic_pass_entry.get().strip(),
            webhook_headers=_lines_to_dict(self.custom_headers_entry.get("1.0", "end")),
            webhook_query_params=_lines_to_dict(self.custom_params_entry.get("1.0", "end"), sep="="),
            webhook_body_template=self.custom_body_entry.get("1.0", "end").strip(),
            webhook_success_check=success_key,
            webhook_success_json_path=self.custom_success_path_entry.get().strip(),
            webhook_success_json_value=self.custom_success_value_entry.get().strip(),
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
        card = self._card("\u2699  App Preferences")
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
