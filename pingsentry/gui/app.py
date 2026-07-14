"""Main application window."""
from __future__ import annotations

import sys
from typing import Optional

import customtkinter as ctk

from ..core.engine import MonitorEngine, EngineEvent
from ..core.models import Server
from ..core import storage
from . import theme
from .widgets import GhostButton
from .dashboard_view import DashboardView
from .settings_view import SettingsView
from .logs_view import LogsView
from .server_dialog import ServerDialog

APP_TITLE = "PingSentry — Uptime & SMS Alerts"
POLL_MS = 400


class PingSentryApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        theme.apply_theme()

        self.title(APP_TITLE)
        self.geometry("1080x720")
        self.minsize(920, 620)
        self.configure(fg_color=theme.BG_DARK)

        self.engine = MonitorEngine()
        self._tray_icon = None

        self._build_layout()
        self._refresh_dashboard()
        self._refresh_logs_initial()

        if self.engine.settings.launch_monitoring_on_start:
            self.start_monitoring()
        else:
            self._set_running_indicator(False)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(POLL_MS, self._poll_engine_events)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar --------------------------------------------------------------
        sidebar = ctk.CTkFrame(self, width=210, fg_color=theme.BG_PANEL, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)

        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=20, pady=(26, 30))
        ctk.CTkLabel(brand, text="📡", font=theme.title_font(24)).pack(side="left")
        title_box = ctk.CTkFrame(brand, fg_color="transparent")
        title_box.pack(side="left", padx=(8, 0))
        ctk.CTkLabel(title_box, text="PingSentry", font=theme.title_font(17, "bold")).pack(anchor="w")
        ctk.CTkLabel(title_box, text="Uptime Monitor", font=theme.font(11), text_color=theme.MUTED).pack(anchor="w")

        self.nav_buttons = {}
        for key, label, icon in [
            ("dashboard", "Dashboard", "🏠"),
            ("logs", "Activity Log", "📜"),
            ("settings", "Settings", "⚙️"),
        ]:
            btn = ctk.CTkButton(
                sidebar, text=f"  {icon}   {label}", anchor="w",
                fg_color="transparent", hover_color=theme.BG_CARD_HOVER,
                text_color=theme.TEXT_DIM, font=theme.font(13, "bold"),
                height=42, corner_radius=8,
                command=lambda k=key: self._show_view(k),
            )
            btn.pack(fill="x", padx=14, pady=4)
            self.nav_buttons[key] = btn

        # Monitoring status / toggle -----------------------------------------------
        status_box = ctk.CTkFrame(sidebar, fg_color=theme.BG_CARD, corner_radius=12)
        status_box.pack(fill="x", padx=14, pady=(20, 14), side="bottom")
        self.running_dot = ctk.CTkLabel(status_box, text="●", font=theme.font(14), text_color=theme.SUCCESS)
        self.running_dot.grid(row=0, column=0, padx=(14, 6), pady=(14, 4), sticky="w")
        self.running_label = ctk.CTkLabel(status_box, text="Monitoring Active", font=theme.font(12, "bold"), text_color=theme.TEXT)
        self.running_label.grid(row=0, column=1, padx=(0, 14), pady=(14, 4), sticky="w")
        self.toggle_btn = GhostButton(status_box, text="Pause", command=self._toggle_monitoring)
        self.toggle_btn.grid(row=1, column=0, columnspan=2, padx=14, pady=(0, 14), sticky="ew")
        status_box.grid_columnconfigure(1, weight=1)

        # Main content area ---------------------------------------------------
        content = ctk.CTkFrame(self, fg_color=theme.BG_DARK, corner_radius=0)
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)
        self.content = content

        self.views = {}
        self.dashboard_view = DashboardView(
            content,
            on_add_server=self._open_add_dialog,
            on_edit_server=self._open_edit_dialog,
            on_delete_server=self._delete_server,
            on_check_now=self._check_now,
            on_toggle_enabled=self._toggle_server_enabled,
        )
        self.views["dashboard"] = self.dashboard_view

        self.logs_view = LogsView(content, on_clear=self._clear_logs)
        self.views["logs"] = self.logs_view

        self.settings_view = SettingsView(
            content,
            sms_config=self.engine.sms_config,
            app_settings=self.engine.settings,
            on_save_sms=self._save_sms_config,
            on_save_app=self._save_app_settings,
        )
        self.views["settings"] = self.settings_view

        for v in self.views.values():
            v.grid(row=0, column=0, sticky="nsew", padx=26, pady=24)

        self._show_view("dashboard")

    def _show_view(self, key: str):
        for k, v in self.views.items():
            if k == key:
                v.tkraise()
                self.nav_buttons[k].configure(fg_color=theme.ACCENT_SOFT, text_color=theme.TEXT)
            else:
                self.nav_buttons[k].configure(fg_color="transparent", text_color=theme.TEXT_DIM)

    # ------------------------------------------------------------------
    # Dashboard <-> engine actions
    # ------------------------------------------------------------------

    def _refresh_dashboard(self):
        self.dashboard_view.render_servers(self.engine.list_servers())

    def _refresh_logs_initial(self):
        entries = storage.load_recent_logs(limit=300)
        self.logs_view.set_entries(entries)

    def _open_add_dialog(self):
        ServerDialog(self, None, on_save=self._save_new_server)

    def _open_edit_dialog(self, server: Server):
        ServerDialog(self, server, on_save=self._save_edited_server)

    def _save_new_server(self, server: Server):
        self.engine.add_server(server)
        self._refresh_dashboard()

    def _save_edited_server(self, server: Server):
        self.engine.update_server(server)
        self._refresh_dashboard()

    def _delete_server(self, server: Server):
        answer = ConfirmDialog(self, f"Remove '{server.name}' from monitoring?").wait()
        if answer:
            self.engine.remove_server(server.id)
            self._refresh_dashboard()

    def _check_now(self, server: Server):
        self.engine.check_now(server.id)

    def _toggle_server_enabled(self, server: Server, enabled: bool):
        server.enabled = enabled
        if not enabled:
            server.status = "paused"
        else:
            server.status = "unknown"
            server.consecutive_failures = 0
            server.consecutive_successes = 0
        self.engine.update_server(server)
        self.engine.check_now(server.id)
        self._refresh_dashboard()

    def _clear_logs(self):
        storage.clear_logs()

    # ------------------------------------------------------------------
    # Settings actions
    # ------------------------------------------------------------------

    def _save_sms_config(self, cfg):
        storage.save_sms_config(cfg)
        self.engine.sms_config = cfg

    def _save_app_settings(self, settings):
        storage.save_settings(settings)
        self.engine.settings = settings

    # ------------------------------------------------------------------
    # Monitoring control
    # ------------------------------------------------------------------

    def start_monitoring(self):
        self.engine.start()
        self._set_running_indicator(True)

    def _toggle_monitoring(self):
        if self.engine.is_running:
            self.engine.pause()
            self._set_running_indicator(False)
        else:
            self.engine.start()
            self._set_running_indicator(True)

    def _set_running_indicator(self, running: bool):
        if running:
            self.running_dot.configure(text_color=theme.SUCCESS)
            self.running_label.configure(text="Monitoring Active")
            self.toggle_btn.configure(text="Pause")
        else:
            self.running_dot.configure(text_color=theme.MUTED)
            self.running_label.configure(text="Monitoring Paused")
            self.toggle_btn.configure(text="Resume")

    # ------------------------------------------------------------------
    # Event polling from engine background thread
    # ------------------------------------------------------------------

    def _poll_engine_events(self):
        events = self.engine.drain_events()
        needs_dash_refresh = False
        for ev in events:
            if ev.kind in ("check", "status_change", "alert_sent"):
                needs_dash_refresh = True
            if ev.kind == "log":
                self.logs_view.prepend_entry(ev.payload.get("entry", {}))
        if needs_dash_refresh:
            self._refresh_dashboard()
        self.after(POLL_MS, self._poll_engine_events)

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def _on_close(self):
        if self.engine.settings.minimize_to_tray:
            try:
                self._minimize_to_tray()
                return
            except Exception:
                pass
        self._quit_app()

    def _quit_app(self):
        self.engine.stop()
        self.destroy()
        sys.exit(0)

    def _minimize_to_tray(self):
        # Lightweight tray support via pystray; falls back to iconify if
        # pystray / a display tray isn't available on this platform.
        try:
            import pystray
            from PIL import Image, ImageDraw
        except ImportError:
            self.iconify()
            return

        if self._tray_icon is None:
            img = Image.new("RGB", (64, 64), theme.BG_DARK)
            d = ImageDraw.Draw(img)
            d.ellipse((8, 8, 56, 56), fill=theme.ACCENT)
            menu = pystray.Menu(
                pystray.MenuItem("Open PingSentry", self._restore_from_tray, default=True),
                pystray.MenuItem("Quit", self._quit_from_tray),
            )
            self._tray_icon = pystray.Icon("PingSentry", img, "PingSentry", menu)
            import threading
            threading.Thread(target=self._tray_icon.run, daemon=True).start()

        self.withdraw()

    def _restore_from_tray(self, icon=None, item=None):
        self.after(0, self._do_restore)

    def _do_restore(self):
        if self._tray_icon:
            self._tray_icon.stop()
            self._tray_icon = None
        self.deiconify()
        self.lift()

    def _quit_from_tray(self, icon=None, item=None):
        if self._tray_icon:
            self._tray_icon.stop()
        self.after(0, self._quit_app)


class ConfirmDialog(ctk.CTkToplevel):
    """Tiny modal Yes/No confirmation dialog, returns via wait()."""

    def __init__(self, master, message: str):
        super().__init__(master)
        self.title("Confirm")
        self.geometry("360x150")
        self.configure(fg_color=theme.BG_DARK)
        self.resizable(False, False)
        self.grab_set()
        self.transient(master)
        self._result = False

        ctk.CTkLabel(self, text=message, wraplength=320, font=theme.font(13)).pack(padx=20, pady=(26, 16))
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(pady=6)
        GhostButton(btns, text="Cancel", command=self._cancel).pack(side="left", padx=8)
        ctk.CTkButton(
            btns, text="Remove", fg_color=theme.DANGER, hover_color="#c8402e",
            command=self._confirm,
        ).pack(side="left", padx=8)

        self.after(50, self._center)

    def _center(self):
        try:
            self.update_idletasks()
            px = self.master.winfo_rootx()
            py = self.master.winfo_rooty()
            pw = self.master.winfo_width()
            ph = self.master.winfo_height()
            w = self.winfo_width()
            h = self.winfo_height()
            self.geometry(f"+{px + (pw - w)//2}+{py + (ph - h)//2}")
        except Exception:
            pass

    def _confirm(self):
        self._result = True
        self.destroy()

    def _cancel(self):
        self._result = False
        self.destroy()

    def wait(self) -> bool:
        self.master.wait_window(self)
        return self._result
