"""Small reusable UI widgets."""
from __future__ import annotations

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
