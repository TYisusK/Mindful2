import flet as ft
import asyncio, io, base64, calendar
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import pytz
from collections import defaultdict, Counter

from components.app_header import AppHeader
from theme import BG, INK, rounded_card, MUTED
from services.firebase_service import FirebaseService
from google.cloud.firestore_v1 import base_query as bq


def StatsView(page: ft.Page):
    fb = FirebaseService()
    sess_user = page.session.get("user")
    if not sess_user or not sess_user.get("uid"):
        return ft.View(route="/stats", controls=[ft.Text("Inicia sesión para continuar")], bgcolor=BG)

    uid = sess_user["uid"]
    username = sess_user.get("username") or (sess_user.get("email") or "").split("@")[0]
    tz = pytz.timezone("America/Mexico_City")

    today = datetime.now(tz)
    monday = today - timedelta(days=today.weekday())
    week_days = [monday + timedelta(days=i) for i in range(7)]
    first_day_month = today.replace(day=1)
    _, last_day_num = calendar.monthrange(today.year, today.month)
    last_day_month = today.replace(day=last_day_num)

    # ---------- Utilidades ----------
    def plot_to_base64(fig):
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", transparent=True)
        buf.seek(0)
        img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        buf.close()
        plt.close(fig)
        return img_b64

    def create_chart(data, title, color, emoji, ylabel, kind="bar"):
        if not data:
            fig, ax = plt.subplots(figsize=(5, 3))
            ax.text(0.5, 0.5, "Sin datos disponibles", fontsize=14, ha="center", va="center")
            ax.axis("off")
            return plot_to_base64(fig)

        labels, values = zip(*data.items())
        fig, ax = plt.subplots(figsize=(5.5, 3.3))

        if kind == "bar":
            ax.bar(labels, values, color=color)
        elif kind == "line":
            ax.plot(labels, values, marker="o", color=color, linewidth=2.5)
            ax.fill_between(range(len(values)), values, alpha=0.2, color=color)

        ax.set_title(f"{emoji} {title}", fontsize=13, color="#4A148C")
        ax.set_ylabel(ylabel)
        ax.grid(True, linestyle="--", alpha=0.3)
        plt.xticks(rotation=25, ha="right")
        plt.tight_layout()
        return plot_to_base64(fig)

    # ---------- Cargar datos ----------
    async def load_notes_data():
        ref = fb.db.collection("users").document(uid).collection("notes")
        date_limit = (today - timedelta(days=60)).astimezone(pytz.utc)
        q = ref.where(filter=bq.FieldFilter("createdAt", ">=", date_limit))
        docs = list(q.stream())
        daily = defaultdict(int)
        for d in docs:
            data = d.to_dict() or {}
            if data.get("createdAt"):
                dt = data["createdAt"].astimezone(tz).date()
                daily[dt] += 1
        return daily

    async def load_diagnostics_data():
        ref = fb.db.collection("users").document(uid).collection("diagnostics")
        date_limit = (today - timedelta(days=60)).astimezone(pytz.utc)
        q = ref.where(filter=bq.FieldFilter("createdAt", ">=", date_limit))
        docs = list(q.stream())
        daily = defaultdict(list)
        emotions = []
        for d in docs:
            data = d.to_dict() or {}
            if not data.get("createdAt"):
                continue
            dt = data["createdAt"].astimezone(tz).date()
            mood = str(data.get("mood", "")).capitalize()
            if mood:
                emotions.append((dt, mood))
            score = 3
            lm = mood.lower()
            if "feliz" in lm:
                score = 5
            elif "bien" in lm:
                score = 4
            elif "neutral" in lm:
                score = 3
            elif "triste" in lm:
                score = 2
            elif "mal" in lm:
                score = 1
            elif lm.isdigit():
                score = int(lm)
            daily[dt].append(score)
        return {k: sum(v) / len(v) for k, v in daily.items()}, emotions

    # ---------- UI ----------
    transparent_pixel = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
        "/w8AAgMBAp9x0W8AAAAASUVORK5CYII="
    )

    chart_notes = ft.Image(src_base64=transparent_pixel, width=600)
    chart_mood = ft.Image(src_base64=transparent_pixel, width=600)
    chart_emotions = ft.Image(src_base64=transparent_pixel, width=600)
    insights_txt = ft.Text("Cargando estadísticas…", color=MUTED, italic=True)

    mode_dropdown = ft.Dropdown(
        options=[ft.dropdown.Option("Semana actual"), ft.dropdown.Option("Mes actual")],
        value="Semana actual",
        label="Ver por",
        border_color="#B39DDB",
        text_style=ft.TextStyle(color=INK, size=13),
        bgcolor="white",
        width=220,
    )

    # ---------- Lógica de carga ----------
    async def load_and_update():
        insights_txt.value = "Analizando tus datos 🌿"
        page.update()

        notes_data, (mood_data, emotions_data) = await asyncio.gather(
            load_notes_data(), load_diagnostics_data()
        )

        # mapa de emojis amigable
        emoji_map = {
            "feliz": "😊 Feliz",
            "bien": "🙂 Bien",
            "neutral": "😐 Neutral",
            "triste": "😢 Triste",
            "mal": "😞 Mal",
            "ansioso": "😰 Ansioso",
            "estresado": "😫 Estresado",
            "enojado": "😡 Enojado",
            "motivado": "💪 Motivado",
            "calmado": "🕊️ Calmado",
            "1": "😞 Muy mal",
            "2": "😢 Triste",
            "3": "😐 Neutral",
            "4": "🙂 Bien",
            "5": "😊 Feliz",
        }

        # --- SEMANA ---
        if mode_dropdown.value == "Semana actual":
            labels = [d.strftime("%a %d") for d in week_days]
            notes_week = {d.strftime("%a %d"): notes_data.get(d.date(), 0) for d in week_days}
            mood_week = {d.strftime("%a %d"): mood_data.get(d.date(), 0) for d in week_days}

            # emociones de la semana
            emotion_week = [m for (dt, m) in emotions_data if monday.date() <= dt <= (monday + timedelta(days=6)).date()]
            normalized = []
            for emo in emotion_week:
                key = str(emo).lower().strip()
                found = next((v for k, v in emoji_map.items() if k in key), str(emo))
                normalized.append(found)
            counter = Counter(normalized)
            top_emotions = dict(counter.most_common(7))

            chart_notes.src_base64 = create_chart(notes_week, "Notas por día", "#9575CD", "📝", "Notas", "bar")
            chart_mood.src_base64 = create_chart(mood_week, "Estado emocional diario", "#7E57C2", "💜", "Promedio", "line")
            chart_emotions.src_base64 = create_chart(top_emotions, "Emociones más frecuentes (semana)", "#B39DDB", "💬", "Veces", "bar")

            total_notes = sum(notes_week.values())
            avg_mood = sum(v for v in mood_week.values() if v) / (len([v for v in mood_week.values() if v]) or 1)

        # --- MES ---
        else:
            start = first_day_month.date()
            week_ranges = []
            while start <= last_day_month.date():
                end = min(start + timedelta(days=6), last_day_month.date())
                week_ranges.append((start, end))
                start = end + timedelta(days=1)

            notes_weeks, mood_weeks = {}, {}
            emotion_month = [m for (_, m) in emotions_data if first_day_month.date() <= _ <= last_day_month.date()]
            normalized_month = []
            for emo in emotion_month:
                key = str(emo).lower().strip()
                found = next((v for k, v in emoji_map.items() if k in key), str(emo))
                normalized_month.append(found)
            counter_month = Counter(normalized_month)
            top_month = dict(counter_month.most_common(7))

            for i, (start, end) in enumerate(week_ranges, 1):
                label = f"Semana {i} ({start.day}-{end.day})"
                ndays = [d for d in notes_data if start <= d <= end]
                mdays = [d for d in mood_data if start <= d <= end]
                notes_weeks[label] = sum(notes_data[d] for d in ndays)
                mood_weeks[label] = sum(mood_data[d] for d in mdays) / len(mdays) if mdays else 0

            chart_notes.src_base64 = create_chart(notes_weeks, "Notas por semana", "#9575CD", "📝", "Notas", "bar")
            chart_mood.src_base64 = create_chart(mood_weeks, "Promedio emocional semanal", "#7E57C2", "💜", "Promedio", "line")
            chart_emotions.src_base64 = create_chart(top_month, "Emociones más comunes del mes", "#B39DDB", "💬", "Veces", "bar")

            total_notes = sum(notes_weeks.values())
            avg_mood = sum(mood_weeks.values()) / (len(mood_weeks) or 1)

        # --- RESUMEN ---
        if avg_mood >= 4:
            mood_txt = "😊 Tu ánimo ha estado alto, ¡sigue así!"
        elif avg_mood >= 3:
            mood_txt = "😌 Has mantenido estabilidad emocional."
        else:
            mood_txt = "🌧️ Algunos días difíciles, pero sigues avanzando 💪"

        insights_txt.value = (
            f"📝 Notas totales: {total_notes}\n"
            f"{mood_txt}"
        )
        page.update()

    mode_dropdown.on_change = lambda e: page.run_task(load_and_update)

    try:
        page.run_task(load_and_update)
    except Exception:
        import threading
        threading.Thread(target=lambda: asyncio.run(load_and_update()), daemon=True).start()

    # ---------- Layout responsivo ----------
    content = ft.Column(
        [
            ft.Row(
                [
                    ft.Text(f"📊 Estadísticas de {username}", size=20, weight=ft.FontWeight.W_700, color=INK),
                    mode_dropdown,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            rounded_card(ft.Column([chart_notes], spacing=8), 16),
            rounded_card(ft.Column([chart_mood], spacing=8), 16),
            rounded_card(ft.Column([chart_emotions], spacing=8), 16),
            rounded_card(
                ft.Column(
                    [ft.Text("🌟 Insights personalizados", size=16, weight=ft.FontWeight.W_600), insights_txt],
                    spacing=8,
                ),
                16,
            ),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=25,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    scrollable_container = ft.Container(
        content=ft.Column(
            [content],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.padding.all(20),
        alignment=ft.alignment.center,
        expand=True,
        bgcolor=BG,
    )

    return ft.View(
        route="/stats",
        bgcolor=BG,
        scroll=ft.ScrollMode.AUTO,
        controls=[AppHeader(page, active_route="stats"), scrollable_container],
    )
