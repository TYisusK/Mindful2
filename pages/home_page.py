from components.app_header import AppHeader
import flet as ft
from datetime import datetime, timedelta
import pytz
from google.cloud import firestore as gcfirestore

from theme import BG, INK, MUTED, rounded_card
from services.firebase_service import FirebaseService
from ui_helpers import scroll_view, shell_header, two_col_grid


def HomeView(page: ft.Page):
    sess_user = page.session.get("user")
    if isinstance(sess_user, dict):
        name = (sess_user.get("username") or (sess_user.get("email") or "").split("@")[0] or "Unknown")
        uid = sess_user.get("uid")
    else:
        name = "Unknown"
        uid = None

    fb = FirebaseService()

    # --- Header ---
    header = shell_header(f"Hola {name}", "Tu espacio para sentirte mejor")

    # --- Frase del día ---
    phrase_title = ft.Text("Frase del día ✨", size=16, weight=ft.FontWeight.W_600, color=INK)
    phrase_text = ft.Text(
        "Cargando…",
        size=12,
        color=MUTED,
        selectable=True,
        max_lines=3,
        overflow=ft.TextOverflow.ELLIPSIS,
    )
    refresh_btn = ft.IconButton(icon=ft.Icons.REFRESH, tooltip="Actualizar")
    spinner = ft.ProgressRing(visible=True)

    def set_phrase(text: str, loading: bool):
        phrase_text.value = text
        spinner.visible = loading
        page.update()

    async def load_phrase_for_today():
        if not uid:
            set_phrase("Inicia sesión para ver tu frase del día.", loading=False)
            return
        try:
            tz = pytz.timezone("America/Mexico_City")
            now_local = datetime.now(tz)
            start_local = tz.localize(datetime(now_local.year, now_local.month, now_local.day, 0, 0, 0))
            end_local = start_local + timedelta(days=1)
            start_utc = start_local.astimezone(pytz.utc)
            end_utc = end_local.astimezone(pytz.utc)

            ref = fb.db.collection("users").document(uid).collection("diagnostics")
            q = (
                ref.where("createdAt", ">=", start_utc)
                .where("createdAt", "<", end_utc)
                .order_by("createdAt", direction=gcfirestore.Query.DESCENDING)
                .limit(1)
            )
            docs = list(q.stream())
            if not docs:
                set_phrase("Aún no haces un diagnóstico hoy. Hazlo para obtener tu frase.", loading=False)
                return
            doc = docs[0].to_dict() or {}
            phrase = doc.get("phrase")
            if phrase:
                set_phrase(phrase, loading=False)
            else:
                set_phrase("Guardaste tu diagnóstico hoy. La frase está en proceso…", loading=False)
        except Exception as ex:
            set_phrase(f"No se pudo cargar la frase: {ex}", loading=False)

    def on_refresh(_):
        try:
            page.run_task(load_phrase_for_today)
        except Exception:
            import asyncio, threading

            threading.Thread(target=lambda: asyncio.run(load_phrase_for_today()), daemon=True).start()

    refresh_btn.on_click = on_refresh

    phrase_card = rounded_card(
        ft.Column(
            [
                ft.Row(
                    [phrase_title, ft.Row([refresh_btn, spinner])],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                phrase_text,
            ],
            spacing=10,
        ),
        16,
    )

    # --- Acciones ---
    def action_card(title: str, subtitle: str, on_click=None, emoji: str = "•"):
        return ft.Container(
            on_click=on_click,
            content=ft.Column(
                [
                    ft.Text(f"{emoji} {title}", size=15, weight=ft.FontWeight.W_600, color=INK),
                    ft.Text(subtitle, size=12, color=MUTED),
                ],
                spacing=4,
            ),
            padding=16,
            bgcolor="#EDE7FF",
            border_radius=16,
        )

    grid_items = [
        action_card("¿Cómo te sientes?", "Habla y expresa todo lo que sientes", on_click=lambda _: page.go("/diagnostic"), emoji="📝"),
        action_card("Mis notas", "Escribir todo lo que sientes es algo bueno", on_click=lambda _: page.go("/notes"), emoji="📒"),
        action_card("Recomendaciones", "¿Qué puedo hacer para sentirme mejor?", on_click=lambda _: page.go("/recommendations"), emoji="💡"),
        action_card("Tell Me +", "Habla con tu asistente Mindful+", on_click=lambda _: page.go("/tellme"), emoji="✨"),
    ]
    grid = two_col_grid(grid_items)

    # --- Estructura principal con scroll ---
    body = scroll_view(
        rounded_card(
            ft.Column([header, phrase_card, grid], spacing=16),
            16,
        )
    )

    # Cargar frase automáticamente al abrir
    on_refresh(None)

    return ft.View(
        route="/home",
        bgcolor=BG,
        controls=[AppHeader(page, active_route='home'), body]
    )
