import json
import locale
import urllib.error
import urllib.request
from datetime import datetime

from django.conf import settings


def _call_tg_api(method: str, payload: dict) -> dict:
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
    chat_id = getattr(settings, "TELEGRAM_CHAT_ID", None)
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не настроен")
    if not chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID не настроен")

    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps({**payload, "chat_id": chat_id}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        raise RuntimeError(f"Telegram API error: {exc.code} {body}") from exc


def send_message(text: str) -> dict:
    return _call_tg_api("sendMessage", {"text": text})


def _mention(player) -> str:
    return player.telegram_mention


def _russian_month(date_value) -> str:
    months = [
        "января",
        "февраля",
        "марта",
        "апреля",
        "мая",
        "июня",
        "июля",
        "августа",
        "сентября",
        "октября",
        "ноября",
        "декабря",
    ]
    return months[date_value.month - 1]


def _format_pregame(match) -> str:
    month = _russian_month(match.played_on)
    lines = [
        f"⚽ Воскресный футбол · {match.played_on.day} {month} в {match.starts_at.strftime('%H:%M')}",
        f"📍 {match.venue}",
    ]
    if match.address:
        lines.append(f"🗺 {match.address}")
    if match.signup_note:
        lines.append(f"📝 {match.signup_note}")

    squad = list(match.appearances.select_related("player").order_by("player__name"))
    mentions = [_mention(app.player) for app in squad]
    lines.append("")
    lines.append(f"В заявке ({len(squad)}):")
    lines.append(" ".join(mentions) if mentions else "Пока никого")
    lines.append("")
    lines.append("Не забудьте сменку и хорошее настроение 💚")
    return "\n".join(lines)


def _format_postgame(match) -> str:
    lines = [
        f"🏁 {match.team_a_name} {match.score_a()} : {match.score_b()} {match.team_b_name}",
        "",
    ]

    def _team_block(title, appearances, emoji):
        lines.append(f"{emoji} {title}:")
        apps = list(appearances.order_by("-goals", "-assists", "-saves", "player__name"))
        for app in apps:
            stats = []
            if app.goals:
                stats.append(f"{app.goals}⚽")
            if app.assists:
                stats.append(f"{app.assists}🅰️")
            if app.saves:
                stats.append(f"{app.saves} сейвов")
            stat_str = " ".join(stats) if stats else ""
            lines.append(f"{_mention(app.player)} — {stat_str}" if stat_str else _mention(app.player))
        lines.append("")

    _team_block(match.team_a_name, match.team_a(), "⚪")
    _team_block(match.team_b_name, match.team_b(), "🔵")

    return "\n".join(lines).strip()


def send_pregame_notification(match) -> bool:
    if not match.is_announced:
        return False
    text = _format_pregame(match)
    send_message(text)
    match.pregame_notification_sent = True
    match.save(update_fields=["pregame_notification_sent"])
    return True


def send_postgame_notification(match) -> bool:
    if not match.is_played:
        return False
    text = _format_postgame(match)
    send_message(text)
    match.postgame_notification_sent = True
    match.save(update_fields=["postgame_notification_sent"])
    return True
