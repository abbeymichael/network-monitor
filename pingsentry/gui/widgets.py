"""Small reusable UI widgets."""
from __future__ import annotations

import time
import tkinter as tk

import customtkinter as ctk

from . import theme


class Badge(ctk.CTkLabel):
    """A small rounded status pill, e.g. ONLINE / DOWN / PENDING."""

    def __init__(self, master, text="", status="unknown", **kwargs):
        color = theme.STATUS_COLORS.get(status, theme.MUTED)
        soft = theme.STATUS_SOFT.get(status, theme.BG_CARD)
        super().__init__(
            master,
            text=text,
            text_color=color,
            fg_color=soft,
            corner_radius=10,
            font=theme.font(11, "bold"),
            padx=10,
            pady=3,
            **kwargs,
        )

    def set_status(self, status: str, text: str = None):
        color = theme.STATUS_COLORS.get(status, theme.MUTED)
        soft = theme.STATUS_SOFT.get(status, theme.BG_CARD)
        self.configure(
            text=text if text is not None else theme.STATUS_LABELS.get(status, status.upper()),
            text_color=color,
            fg_color=soft,
        )


class SectionLabel(ctk.CTkLabel):
    def __init__(self, master, text="", **kwargs):
        super().__init__(
            master,
            text=text.upper(),
            text_color=theme.MUTED,
            font=theme.font(11, "bold"),
            anchor="w",
            **kwargs,
        )


class PrimaryButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        defaults = dict(
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            text_color="#ffffff",
            font=theme.font(13, "bold"),
            corner_radius=8,
            height=36,
        )
        defaults.update(kwargs)
        super().__init__(master, **defaults)


class GhostButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        defaults = dict(
            fg_color="transparent",
            hover_color=theme.BG_CARD_HOVER,
            text_color=theme.TEXT_DIM,
            font=theme.font(12),
            corner_radius=8,
            height=32,
            border_width=1,
            border_color=theme.BORDER,
        )
        defaults.update(kwargs)
        super().__init__(master, **defaults)


class DangerButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        defaults = dict(
            fg_color="transparent",
            hover_color=theme.DANGER_SOFT,
            text_color=theme.DANGER,
            font=theme.font(12),
            corner_radius=8,
            height=32,
            border_width=1,
            border_color=theme.DANGER,
        )
        defaults.update(kwargs)
        super().__init__(master, **defaults)


class StatCard(ctk.CTkFrame):
    def __init__(self, master, label="", value="0", value_color=None, **kwargs):
        super().__init__(master, fg_color=theme.BG_CARD, corner_radius=12, **kwargs)
        self.value_label = ctk.CTkLabel(
            self, text=value, font=theme.title_font(26, "bold"),
            text_color=value_color or theme.TEXT,
        )
        self.value_label.pack(padx=18, pady=(14, 0), anchor="w")
        SectionLabel(self, text=label).pack(padx=18, pady=(2, 14), anchor="w")

    def set_value(self, value):
        self.value_label.configure(text=str(value))


class Heartbeat(tk.Canvas):
    """A tiny animated 'pulse' dot that visually proves a check is happening.

    - A steady breathing pulse (colour = current status) shows the monitor is
      alive and watching this target.
    - Calling ``beat()`` triggers a bright expanding ring flash — fired every
      time an actual network check completes for this server, so the user can
      literally see each heartbeat land.
    """

    SIZE = 26

    def __init__(self, master, status: str = "unknown", **kwargs):
        super().__init__(
            master, width=self.SIZE, height=self.SIZE,
            highlightthickness=0, bd=0,
            bg=theme.BG_CARD, **kwargs,
        )
        self._status = status
        self._phase = 0.0
        self._ring = None          # (radius, alpha_steps_left)
        self._core = None
        self._running = True
        self._animate()

    def _color(self) -> str:
        return theme.STATUS_COLORS.get(self._status, theme.MUTED)

    def set_bg(self, color: str):
        try:
            self.configure(bg=color)
        except tk.TclError:
            pass

    def set_status(self, status: str):
        self._status = status

    def beat(self):
        """Trigger a visible ring flash for a completed check."""
        self._ring = self.SIZE * 0.28  # starting radius; grows outward

    def _blend(self, hex_color: str, bg_hex: str, t: float) -> str:
        """Linear blend between hex_color and bg for a fake-alpha glow."""
        def _c(h):
            h = h.lstrip("#")
            return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
        r1, g1, b1 = _c(hex_color)
        r2, g2, b2 = _c(bg_hex)
        r = int(r1 * t + r2 * (1 - t))
        g = int(g1 * t + g2 * (1 - t))
        b = int(b1 * t + b2 * (1 - t))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _animate(self):
        if not self._running:
            return
        try:
            self.delete("all")
            cx = cy = self.SIZE / 2
            color = self._color()
            bg = self.cget("bg")

            # Breathing halo behind the core
            self._phase += 0.14
            import math
            breathe = (math.sin(self._phase) + 1) / 2  # 0..1
            halo_r = self.SIZE * (0.30 + 0.12 * breathe)
            halo_col = self._blend(color, bg, 0.18 + 0.15 * breathe)
            self.create_oval(cx - halo_r, cy - halo_r, cx + halo_r, cy + halo_r,
                             fill=halo_col, outline="")

            # Expanding beat ring (fires on each completed check)
            if self._ring is not None:
                r = self._ring
                max_r = self.SIZE * 0.5
                t = max(0.0, 1 - (r / max_r))
                ring_col = self._blend(color, bg, 0.5 * t)
                self.create_oval(cx - r, cy - r, cx + r, cy + r,
                                 outline=ring_col, width=2)
                self._ring = r + 1.6
                if self._ring >= max_r:
                    self._ring = None

            # Solid core dot
            core_r = self.SIZE * 0.16
            self.create_oval(cx - core_r, cy - core_r, cx + core_r, cy + core_r,
                             fill=color, outline="")
        except tk.TclError:
            self._running = False
            return
        self.after(40, self._animate)

    def destroy(self):
        self._running = False
        super().destroy()


class Sparkline(tk.Canvas):
    """Minimal latency/uptime sparkline for the detail page."""

    def __init__(self, master, width=320, height=54, **kwargs):
        super().__init__(master, width=width, height=height,
                         highlightthickness=0, bd=0, bg=theme.BG_PANEL, **kwargs)
        self._cw = width
        self._ch = height

    def render(self, values, statuses=None):
        """values: list of floats (latency ms, None allowed).
        statuses: optional parallel list of 'up'/'down' to colour points."""
        self.delete("all")
        vals = [v for v in values if v is not None]
        if not vals:
            self.create_text(self._cw / 2, self._ch / 2, text="no data yet",
                             fill=theme.MUTED, font=("Roboto", 10))
            return
        lo, hi = min(vals), max(vals)
        span = (hi - lo) or 1
        n = len(values)
        pad = 6
        usable_w = self._cw - 2 * pad
        usable_h = self._ch - 2 * pad
        pts = []
        for i, v in enumerate(values):
            x = pad + (usable_w * i / max(1, n - 1))
            if v is None:
                pts.append((x, None))
                continue
            y = pad + usable_h * (1 - (v - lo) / span)
            pts.append((x, y))
        # line
        line_pts = []
        for x, y in pts:
            if y is None:
                continue
            line_pts.extend([x, y])
        if len(line_pts) >= 4:
            self.create_line(*line_pts, fill=theme.ACCENT, width=2, smooth=True)
        # dots
        for i, (x, y) in enumerate(pts):
            if y is None:
                continue
            col = theme.SUCCESS
            if statuses and i < len(statuses) and statuses[i] == "down":
                col = theme.DANGER
            self.create_oval(x - 2, y - 2, x + 2, y + 2, fill=col, outline="")


class Toast(ctk.CTkFrame):
    """A transient in-app notification banner that slides in at the top-right
    of the main window, auto-dismisses, and can be clicked."""

    def __init__(self, master, title: str, message: str, kind: str = "info",
                 on_click=None, duration_ms: int = 5200):
        accent = {
            "down": theme.DANGER,
            "recovery": theme.SUCCESS,
            "success": theme.SUCCESS,
            "error": theme.DANGER,
            "test": theme.ACCENT,
            "info": theme.ACCENT,
        }.get(kind, theme.ACCENT)
        super().__init__(master, fg_color=theme.BG_CARD, corner_radius=12,
                         border_width=1, border_color=theme.BORDER)
        self._on_click = on_click

        stripe = ctk.CTkFrame(self, width=4, fg_color=accent, corner_radius=2)
        stripe.pack(side="left", fill="y", padx=(6, 0), pady=8)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True, padx=(10, 12), pady=8)
        icon = {"down": "✕", "recovery": "✓", "success": "✓",
                "error": "✕", "test": "✎", "info": "🔔"}.get(kind, "🔔")
        title_row = ctk.CTkFrame(body, fg_color="transparent")
        title_row.pack(fill="x")
        ctk.CTkLabel(title_row, text=f"{icon}  {title}", font=theme.font(13, "bold"),
                     text_color=accent, anchor="w").pack(side="left")
        ctk.CTkLabel(body, text=message, font=theme.font(11), text_color=theme.TEXT_DIM,
                     anchor="w", justify="left", wraplength=260).pack(fill="x", pady=(2, 0))

        close = ctk.CTkButton(self, text="✕", width=22, height=22, corner_radius=6,
                              fg_color="transparent", hover_color=theme.BG_CARD_HOVER,
                              text_color=theme.MUTED, font=theme.font(11),
                              command=self.dismiss)
        close.pack(side="right", padx=(0, 8), pady=8)

        for w in (self, body):
            w.bind("<Button-1>", self._clicked)
        self.after(duration_ms, self.dismiss)

    def _clicked(self, _event=None):
        if self._on_click:
            try:
                self._on_click()
            except Exception:
                pass
        self.dismiss()

    def dismiss(self):
        try:
            self.destroy()
        except tk.TclError:
            pass


class NotificationBell(ctk.CTkFrame):
    """A bell button with an unread-count badge, shown in the top bar."""

    def __init__(self, master, on_click: "callable", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._on_click = on_click
        self._count = 0

        self.btn = ctk.CTkButton(
            self, text="🔔", width=42, height=38, corner_radius=10,
            fg_color=theme.BG_CARD, hover_color=theme.BG_CARD_HOVER,
            text_color=theme.TEXT, font=theme.font(18),
            command=self._clicked,
        )
        self.btn.pack()

        # Unread count badge overlay
        self.badge = ctk.CTkLabel(
            self, text="", fg_color=theme.DANGER, text_color="#ffffff",
            corner_radius=9, font=theme.font(10, "bold"), width=18, height=18,
        )
        # placed only when count > 0

    def _clicked(self):
        if self._on_click:
            self._on_click()

    def set_count(self, count: int):
        self._count = max(0, count)
        if self._count <= 0:
            self.badge.place_forget()
            return
        txt = "9+" if self._count > 9 else str(self._count)
        self.badge.configure(text=txt)
        self.badge.place(relx=1.0, rely=0.0, x=-4, y=-2, anchor="ne")

    def flash(self):
        """Brief attention pulse on the bell icon."""
        try:
            self.btn.configure(text_color=theme.ACCENT)
            self.after(260, lambda: self.btn.configure(text_color=theme.TEXT))
        except tk.TclError:
            pass
