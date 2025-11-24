from components.app_header import AppHeader
import flet as ft
import asyncio
import pytz
from datetime import datetime, timedelta
from google.cloud.firestore_v1 import base_query as bq
from firebase_admin import firestore

from theme import BG, INK, MUTED, rounded_card, primary_button
from ui_helpers import date_scroller, shell_header
from services.firebase_service import FirebaseService


def NotesView(page: ft.Page):
    fb = FirebaseService()

    sess_user = page.session.get("user")
    if not isinstance(sess_user, dict) or not sess_user.get("uid"):
        return ft.View(
            route="/notes",
            controls=[AppHeader(page, active_route='notes'), ft.Text("Inicia sesión para continuar")],
            bgcolor=BG
        )
    uid = sess_user["uid"]

    header = shell_header("Mis notas", "Organiza y expresa lo que sientes")

    tz = pytz.timezone("America/Mexico_City")

    status = ft.Text("", color=MUTED)
    list_col = ft.Column(spacing=10)
    scroller_row = ft.Row([])

    now_local = datetime.now(tz)
    active_key = now_local.strftime("%Y-%m-%d")

    # --- UI helpers ---
    def toast(msg: str, error: bool = False):
        print(f"[TOAST] {msg}")
        page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor="#E5484D" if error else "#2ECC71")
        page.snack_bar.open = True
        page.update()

    def set_status(txt=""):
        status.value = txt
        print(f"[STATUS] {txt}")
        page.update()

    # --- Fecha y Firestore utils ---
    def ts_to_key(ts):
        if ts is None:
            return now_local.strftime("%Y-%m-%d")
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=pytz.utc)
        dt_local = ts.astimezone(tz)
        return dt_local.strftime("%Y-%m-%d")

    def get_first_note_date():
        print("[FUNC] get_first_note_date()")
        notes_ref = fb.db.collection("users").document(uid).collection("notes")
        q = notes_ref.order_by("createdAt", direction=firestore.Query.ASCENDING).limit(1)
        docs = list(q.stream())
        if not docs:
            print("[FUNC] No hay notas aún.")
            return now_local
        ts = (docs[0].to_dict() or {}).get("createdAt")
        if ts is None:
            return now_local
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=pytz.utc)
        dt = ts.astimezone(tz)
        print(f"[FUNC] Primera nota: {dt}")
        return dt

    # --- Scroll selector ---
    def refresh_scroller(first_date, active):
        print(f"[FUNC] refresh_scroller() desde {first_date} hasta hoy, activo={active}")
        scroller_row.controls.clear()
        scroller_row.controls.append(
            date_scroller(
                active,
                first_date.replace(hour=0, minute=0, second=0, microsecond=0),
                now_local,
                on_select=on_select_date,
            )
        )
        page.update()

    def on_select_date(key: str):
        nonlocal active_key
        print(f"[CLICK] Fecha seleccionada: {key}")
        active_key = key
        try:
            page.run_task(load_notes_for_day)
        except Exception as ex:
            print("[ERROR] run_task failed:", ex)
            asyncio.run(load_notes_for_day())

    # --- Cargar notas del día ---
    async def load_notes_for_day():
        set_status("Cargando notas…")
        print(f"[LOAD] Buscando notas para {active_key}")
        year, month, day = map(int, active_key.split("-"))
        start_local = tz.localize(datetime(year, month, day, 0, 0, 0))
        end_local = start_local + timedelta(days=1)
        start_utc = start_local.astimezone(pytz.utc)
        end_utc = end_local.astimezone(pytz.utc)

        notes_ref = fb.db.collection("users").document(uid).collection("notes")
        q = (
            notes_ref.where(filter=bq.FieldFilter("updatedAt", ">=", start_utc))
            .where(filter=bq.FieldFilter("updatedAt", "<", end_utc))
            .order_by("updatedAt", direction=firestore.Query.DESCENDING)
            .limit(200)
        )
        docs = list(q.stream())

        list_col.controls.clear()
        print(f"[LOAD] {len(docs)} notas encontradas.")

        if not docs:
            today_key = now_local.strftime("%Y-%m-%d")
            msg = "Hoy no se han hecho notas." if active_key == today_key else "No hay notas para esta fecha."
            list_col.controls.append(ft.Text(msg, color=MUTED))
            page.update()
            set_status("")
            return

        today_key = datetime.now(tz).strftime("%Y-%m-%d")

        # --- Modal para ver nota ---
        def show_note_detail(note_title: str, note_content: str):
            overlay = ft.Container(
                bgcolor=ft.Colors.with_opacity(0.5, ft.Colors.BLACK),
                alignment=ft.alignment.center,
                content=ft.Container(
                    width=400,
                    height=500,
                    padding=20,
                    bgcolor=ft.Colors.WHITE,
                    border_radius=16,
                    content=ft.Column(
                        [
                            ft.Text(note_title, size=18, weight=ft.FontWeight.W_700, color=INK),
                            ft.Container(
                                height=380,
                                content=ft.Column(
                                    [
                                        ft.Text(
                                            note_content or "(Sin contenido)",
                                            size=13,
                                            color=INK,
                                            selectable=True,
                                            text_align=ft.TextAlign.JUSTIFY,
                                        )
                                    ],
                                    scroll=ft.ScrollMode.AUTO,
                                ),
                            ),
                            ft.ElevatedButton(
                                "Cerrar",
                                bgcolor="#D9D9D9",
                                color=INK,
                                on_click=lambda e: close_overlay(),
                            ),
                        ],
                        spacing=12,
                        alignment=ft.MainAxisAlignment.START,
                    ),
                ),
            )

            def close_overlay():
                page.overlay.clear()
                page.update()

            page.overlay.append(overlay)
            page.update()
            print("[VIEW] Mostrando ventana modal de lectura")

        # --- Mostrar lista de notas ---
        for d in docs:
            data = d.to_dict() or {}
            note_id = d.id
            title = (data.get("title") or "Sin título")[:120]
            content = (data.get("content") or "").strip()
            created_at = data.get("createdAt")
            created_key = ts_to_key(created_at)
            is_same_day = (created_key == today_key)
            print(f"[NOTE] {note_id} ({created_key}) same_day={is_same_day}")

            if is_same_day:
                # ✅ Hoy: Editar / Eliminar
                edit_btn = ft.IconButton(
                    icon=ft.Icons.EDIT,
                    tooltip="Editar",
                    on_click=lambda e, nid=note_id: page.go(f"/note_editor?id={nid}&date={active_key}"),
                )
                del_btn = ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    tooltip="Eliminar",
                    on_click=lambda e, nid=note_id: on_delete_note(nid, created_key),
                )
                action_row = ft.Row([edit_btn, del_btn], alignment=ft.MainAxisAlignment.END)
            else:
                # 👁️ Anteriores: solo ver modal
                view_btn = ft.IconButton(
                    icon=ft.Icons.REMOVE_RED_EYE_OUTLINED,
                    tooltip="Ver nota completa",
                    on_click=lambda e, t=title, c=content: show_note_detail(t, c),
                )
                action_row = ft.Row([view_btn], alignment=ft.MainAxisAlignment.END)

            list_col.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(title, size=16, weight=ft.FontWeight.W_600, color=INK),
                            ft.Text(
                                content[:300] + ("…" if len(content) > 300 else ""),
                                size=12,
                                color=MUTED,
                            ),
                            action_row,
                        ],
                        spacing=6,
                    ),
                    padding=14,
                    bgcolor="#EDE7FF",
                    border_radius=16,
                )
            )
        page.update()
        set_status("")

    # --- Eliminar nota ---
    async def delete_async(note_id: str):
        print(f"[DELETE] Ejecutando delete_async para {note_id}")
        try:
            await asyncio.to_thread(fb.delete_note, uid, note_id)
            print("[DELETE] Eliminación completada en Firestore.")
            toast("Nota eliminada ✅")
            await load_notes_for_day()
        except Exception as ex:
            print("[ERROR] Durante delete_async:", ex)
            toast(f"Error al eliminar: {ex}", error=True)
        finally:
            set_status("")

    def on_delete_note(note_id: str, created_key: str):
        print(f"[CLICK] Intento de eliminar {note_id}, creado={created_key}, activo={active_key}")
        today_key = datetime.now(tz).strftime("%Y-%m-%d")

        if created_key != today_key or active_key != today_key:
            print(f"[BLOCKED] Eliminación denegada: creado={created_key}, activo={active_key}, hoy={today_key}")
            toast("Solo puedes eliminar notas del mismo día en que fueron creadas.", error=True)
            return

        overlay = ft.Container(
            bgcolor=ft.Colors.with_opacity(0.5, ft.Colors.BLACK),
            alignment=ft.alignment.center,
            content=ft.Container(
                width=320,
                padding=20,
                bgcolor=ft.Colors.WHITE,
                border_radius=12,
                content=ft.Column([
                    ft.Text("Eliminar nota", size=18, weight=ft.FontWeight.W_700, color=INK),
                    ft.Text("Esta acción no se puede deshacer.\n¿Quieres continuar?", size=13, color=MUTED),
                    ft.Row(
                        [
                            ft.ElevatedButton("Cancelar", on_click=lambda e: close_overlay(False), bgcolor="#D9D9D9", color=INK),
                            ft.ElevatedButton("Eliminar", on_click=lambda e: close_overlay(True), bgcolor="#E5484D", color="white"),
                        ],
                        alignment=ft.MainAxisAlignment.END,
                        spacing=10,
                    ),
                ], spacing=16),
            ),
        )

        def close_overlay(ok: bool):
            page.overlay.clear()
            page.update()
            if ok:
                set_status("Eliminando…")
                try:
                    page.run_task(lambda: delete_async(note_id))
                except Exception:
                    asyncio.run(delete_async(note_id))

        page.overlay.append(overlay)
        page.update()
        print("[OVERLAY] Mostrado correctamente")

    # --- Layout principal ---
    actions = ft.Row(
        [primary_button("Nueva nota", lambda _: page.go(f"/note_editor?date={active_key}"))],
        alignment=ft.MainAxisAlignment.START,
    )

    body = ft.Container(
        content=ft.Column(
            [rounded_card(ft.Column([header, actions, scroller_row, list_col, status], spacing=12), 16)],
            scroll=ft.ScrollMode.AUTO,
            spacing=16,
        ),
        padding=20,
        bgcolor=BG,
    )

    # --- Boot ---
    async def boot():
        print("[BOOT] Iniciando NotesView...")
        first_date = await asyncio.to_thread(get_first_note_date)
        refresh_scroller(first_date, active_key)
        await load_notes_for_day()
        print("[BOOT] Listo.")

    try:
        page.run_task(boot)
    except Exception as ex:
        print("[ERROR] boot run_task:", ex)
        asyncio.run(boot())

    return ft.View(
        route="/notes",
        controls=[AppHeader(page, active_route='notes'), body],
        bgcolor=BG
    )
