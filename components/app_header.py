# components/app_header.py
import os
import uuid
import time
import threading
import requests
import flet as ft
from theme import INK, BG

# URL del microservicio (Render/local). Cambia si lo tienes en otro dominio.
UPLOADER_URL = os.getenv("UPLOADER_URL", "https://mindful-imagenes.onrender.com")


def AppHeader(page: ft.Page, active_route: str):
    """
    Header reutilizable con navegación principal + menú hamburguesa sutil.
    Incluye botón para activar notificaciones (OneSignal) vía microservicio.
    """

    # ---------- helpers de sesión / navegación ----------
    def ensure_session() -> bool:
        user = page.session.get("user")
        if user:
            return True
        stored = page.client_storage.get("user")
        if stored:
            page.session.set("user", stored)
            return True
        return False

    def go_to(route: str):
        if not ensure_session() and route not in ("/", "/login", "/register", "/welcome"):
            page.snack_bar = ft.SnackBar(ft.Text("Inicia sesión primero 🪄"), bgcolor="#E5484D")
            page.snack_bar.open = True
            page.update()
            page.go("/login")
            return
        page.go(route)

    def toast(msg: str):
        page.snack_bar = ft.SnackBar(ft.Text(msg))
        page.snack_bar.open = True
        page.update()

    # ---------- botón: activar notificaciones ----------
    def _push_button():
        # Solo mostrar si hay sesión iniciada
        if not ensure_session():
            return ft.Container()  # vacío

        def start_push(_):
            try:
                sess = page.session.get("user") or {}
                uid = sess.get("uid", "")
                # Rol aproximado (si tu sesión guarda algo, úsalo)
                role = sess.get("role") or ("profesional" if page.route.startswith("/pro") else "normal")

                if not uid:
                    toast("No encuentro tu sesión. Vuelve a iniciar.")
                    page.go("/login")
                    return

                session_id = uuid.uuid4().hex
                # Abrir página de permisos (puede abrirse en pestaña del navegador)
                page.launch_url(f"{UPLOADER_URL}/notify?session={session_id}&uid={uid}&role={role}")
                toast("Abre la pestaña y acepta notificaciones. Estoy esperando confirmación…")

                def poll():
                    for _ in range(60):  # 60s
                        try:
                            r = requests.get(f"{UPLOADER_URL}/notify/poll", params={"session": session_id}, timeout=5)
                            if r.ok and r.json().get("ready"):
                                def ok():
                                    toast("Notificaciones activadas ✅")
                                try:
                                    page.invoke_later(ok)
                                except Exception:
                                    ok()
                                return
                        except Exception:
                            pass
                        time.sleep(1)
                    def ko():
                        toast("No se confirmó la activación (tiempo agotado).")
                    try:
                        page.invoke_later(ko)
                    except Exception:
                        ko()

                threading.Thread(target=poll, daemon=True).start()
            except Exception as ex:
                toast(f"No pude iniciar la activación: {ex}")

        return ft.IconButton(
            icon=ft.Icons.NOTIFICATIONS_ACTIVE,
            tooltip="Activar notificaciones",
            icon_color="#5A00D0",
            on_click=start_push,
        )

    # ---------- Nav principal ----------
    nav_items = [
        ("home", ft.Icons.HOME_OUTLINED, "Inicio", "/home"),
        ("diagnostic", ft.Icons.PSYCHOLOGY_OUTLINED, "Diagnóstico", "/diagnostic"),
        ("notes", ft.Icons.NOTE_ALT_OUTLINED, "Notas", "/notes"),
        ("recommendations", ft.Icons.LIGHTBULB_OUTLINED, "Recomendaciones", "/recommendations"),
        ("tellme", ft.Icons.FORUM_OUTLINED, "Tell Me +", "/tellme"),
        ("help", ft.Icons.SUPPORT_AGENT, "Ayuda profesional", "/help"),
    ]

    nav_icons = ft.Row(
        [
            ft.IconButton(
                icon=icon,
                tooltip=label,
                icon_color="#5A00D0" if route == active_route else INK,
                on_click=lambda e, r=path: go_to(r),
            )
            for route, icon, label, path in nav_items
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=5,
    )

    # ---------- Menú hamburguesa ----------
    menu_open = {"value": False}

    def toggle_menu(_):
        if not menu_open["value"]:
            show_menu()
        else:
            close_menu()

    def logout(_):
        page.session.clear()
        page.client_storage.remove("user")
        close_menu()
        page.go("/login")

    def show_menu():
        menu_open["value"] = True
        chips = ft.Column(
            [
                ft.Container(
                    on_click=lambda e, r=route: (logout(e) if r == "logout" else go_to(r)),
                    content=ft.Row(
                        [ft.Text(emoji, size=16), ft.Text(label, size=13, color=INK)],
                        spacing=10,
                        alignment=ft.MainAxisAlignment.START,
                    ),
                    padding=ft.padding.symmetric(horizontal=12, vertical=8),
                    bgcolor="#F6F1FF",
                    border_radius=12,
                    shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.18, ft.Colors.BLACK)),
                )
                for emoji, label, route in [
                    ("🏠", "Inicio", "/home"),
                    ("👩‍⚕️", "Ayuda profesional", "/help"),
                    ("📊", "Estadísticas", "/stats"),
                    ("🚪", "Cerrar sesión", "logout"),
                ]
            ],
            spacing=6,
        )

        panel = ft.Container(
            alignment=ft.alignment.top_left,
            padding=ft.padding.only(top=58, left=12),
            content=chips,
        )

        def close_bg(_):
            close_menu()

        # overlay ligero (casi transparente) para capturar el click
        glass = ft.Container(
            bgcolor=ft.Colors.with_opacity(0.01, ft.Colors.BLACK),
            content=panel,
            on_click=close_bg,
        )

        page.overlay.append(glass)
        page.update()
        menu_open["value"] = glass

    def close_menu():
        glass = menu_open["value"]
        if isinstance(glass, ft.Control) and glass in page.overlay:
            page.overlay.remove(glass)
        menu_open["value"] = False
        page.update()

    # ---------- Header ----------
    header_bar = ft.Container(
        bgcolor="#EDE7FF",
        padding=ft.padding.symmetric(horizontal=15, vertical=8),
        content=ft.Row(
            [
                ft.IconButton(icon=ft.Icons.MENU, tooltip="Menú", on_click=toggle_menu),
                ft.Text("Mindful+", size=18, weight=ft.FontWeight.W_700, color=INK),
                ft.Container(expand=True),
                nav_icons,
                _push_button(),  # << botón de notificaciones
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.15, "black")),
    )

    return header_bar
