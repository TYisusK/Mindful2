
import flet as ft
from theme import BG, INK, MUTED, rounded_card

def scroll_view(*controls):
    return ft.Container(
        expand=True,
        bgcolor=BG,
        padding=20,
        content=ft.Column(
            list(controls),
            expand=True,
            scroll=ft.ScrollMode.ADAPTIVE,
            spacing=14,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
    )

def shell_header(title: str, subtitle: str = "", logo_path: str | None = "assets/logo.png"):
    items = []
    try:
        items.append(ft.Image(src=logo_path, width=40, height=40, fit=ft.ImageFit.CONTAIN))
    except Exception:
        pass
    items.append(ft.Column([
        ft.Text(title, size=20, weight=ft.FontWeight.W_700, color=INK),
        ft.Text(subtitle, size=12, color=MUTED) if subtitle else ft.Container(),
    ], spacing=2))
    return ft.Row(items, spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER)


def two_col_grid(items: list[ft.Control]):
    rows = []
    for i in range(0, len(items), 2):
        left = items[i]
        right = items[i+1] if i+1 < len(items) else ft.Container(expand=1)
        rows.append(
            ft.Row([ft.Container(left, expand=1), ft.Container(right, expand=1)], spacing=12)
        )
    return ft.Column(rows, spacing=12)


import flet as ft
import pytz
from datetime import datetime, timedelta

def date_range_by_day(start_dt, end_dt):
    cur = start_dt
    while cur <= end_dt:
        yield cur
        cur += timedelta(days=1)

def date_scroller(active_key: str, start_date: datetime, end_date: datetime, on_select):
    chips = []
    for d in date_range_by_day(start_date, end_date):
        key = d.strftime("%Y-%m-%d")
        lbl = d.strftime("%d %b")
        selected = (key == active_key)
        chips.append(
            ft.Container(
                on_click=(lambda e, k=key: on_select(k)),
                content=ft.Text(lbl, color=ft.Colors.WHITE if selected else ft.Colors.BLACK, size=12, weight=ft.FontWeight.W_600),
                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                bgcolor="#6C5CE7" if selected else "#EDE7FF",
                border_radius=16,
                margin=ft.margin.only(right=8),
            )
        )
    row = ft.Row(chips, scroll=ft.ScrollMode.AUTO)
    return row
