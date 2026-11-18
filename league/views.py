from datetime import timedelta

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import MatchMetaForm, player_line_forms
from .models import Appearance, Match, Player
from .services import balance_appearances
from .telegram import send_pregame_notification, send_postgame_notification


def _leaderboard():
    played = Q(appearances__match__status=Match.STATUS_PLAYED)
    players = (
        Player.objects.annotate(
            games=Count("appearances", filter=played),
            goals=Sum("appearances__goals", filter=played),
            assists=Sum("appearances__assists", filter=played),
            saves=Sum("appearances__saves", filter=played),
        )
        .filter(games__gt=0)
        .order_by("-goals", "-assists", "-saves", "name")
    )

    # Победы считаем по фактическому счёту матча
    win_counts = {}
    apps = Appearance.objects.filter(
        match__status=Match.STATUS_PLAYED,
        side__in=(Appearance.SIDE_A, Appearance.SIDE_B),
    ).select_related("match")
    for app in apps:
        if app.did_win() is True:
            win_counts[app.player_id] = win_counts.get(app.player_id, 0) + 1

    for player in players:
        player.wins = win_counts.get(player.pk, 0)
        player.win_rate = round((player.wins / player.games) * 100) if player.games else 0
    return players


def home(request):
    next_match = Match.next_upcoming()
    played = list(
        Match.objects.filter(status=Match.STATUS_PLAYED)
        .prefetch_related("appearances__player")[:8]
    )
    latest = played[0] if played else None
    return render(
        request,
        "league/home.html",
        {
            "next_match": next_match,
            "latest": latest,
            "matches": played,
            "table": _leaderboard(),
        },
    )


def match_list(request):
    today = timezone.localdate()
    upcoming = (
        Match.objects.filter(played_on__gte=today)
        .prefetch_related("appearances__player")
        .order_by("played_on", "starts_at")
    )
    past = (
        Match.objects.filter(played_on__lt=today)
        .prefetch_related("appearances__player")
        .order_by("-played_on")
    )
    return render(
        request,
        "league/match_list.html",
        {"upcoming": upcoming, "past": past},
    )


def match_detail(request, pk):
    match = get_object_or_404(
        Match.objects.prefetch_related("appearances__player"), pk=pk
    )
    return render(request, "league/match_detail.html", {"match": match})


def player_detail(request, pk):
    player = get_object_or_404(Player, pk=pk)
    appearances = player.appearances.select_related("match").order_by("-match__played_on")
    return render(
        request,
        "league/player_detail.html",
        {"player": player, "appearances": appearances, "totals": player.career_totals()},
    )


def standings(request):
    return render(request, "league/standings.html", {"table": _leaderboard()})


def rules(request):
    return render(request, "league/rules.html")


@staff_member_required
@require_http_methods(["GET", "POST"])
def match_create(request):
    meta = MatchMetaForm(request.POST or None)
    team_a = (request.POST.get("team_a_name") or "Белые").strip() or "Белые"
    team_b = (request.POST.get("team_b_name") or "Цветные").strip() or "Цветные"
    lines = player_line_forms(request.POST or None, team_a=team_a, team_b=team_b)
    error = ""

    if request.method == "POST" and meta.is_valid() and all(line.is_valid() for line in lines):
        playing = []
        for line in lines:
            side = line.cleaned_data.get("side")
            if side:
                playing.append(line)

        sides = {line.cleaned_data["side"] for line in playing}
        status = meta.cleaned_data["status"]
        if not playing:
            error = "Отметьте хотя бы одного в заявке или в команде."
        elif status == Match.STATUS_PLAYED and (
            Appearance.SIDE_A not in sides or Appearance.SIDE_B not in sides
        ):
            error = "Для сыгранного матча нужны обе команды."
        else:
            match = meta.save()
            Appearance.objects.bulk_create(
                [
                    Appearance(
                        match=match,
                        player_id=line.cleaned_data["player_id"],
                        side=line.cleaned_data["side"],
                        goals=line.cleaned_data.get("goals") or 0,
                        assists=line.cleaned_data.get("assists") or 0,
                        saves=line.cleaned_data.get("saves") or 0,
                    )
                    for line in playing
                ]
            )
            return redirect(match)

    return render(
        request,
        "league/match_form.html",
        {"meta": meta, "lines": lines, "error": error},
    )


@staff_member_required
@require_http_methods(["GET", "POST"])
def match_balance(request, pk):
    match = get_object_or_404(
        Match.objects.prefetch_related("appearances__player"), pk=pk
    )

    if not match.is_announced:
        return redirect(match)

    squad = match.appearances.filter(side=Appearance.SIDE_SQUAD).select_related(
        "player"
    )
    if not squad.exists():
        return render(
            request,
            "league/match_balance.html",
            {"match": match, "error": "В заявке пока никого нет."},
        )

    balanced = balance_appearances(squad)

    if request.method == "POST":
        team_a_ids = {app.pk for app, _ in balanced["team_a"]}
        team_b_ids = {app.pk for app, _ in balanced["team_b"]}

        Appearance.objects.filter(pk__in=team_a_ids).update(side=Appearance.SIDE_A)
        Appearance.objects.filter(pk__in=team_b_ids).update(side=Appearance.SIDE_B)
        return redirect(match)

    return render(
        request,
        "league/match_balance.html",
        {"match": match, "balanced": balanced},
    )


@require_http_methods(["GET", "POST"])
def telegram_notify(request):
    token = request.GET.get("token") or request.POST.get("token")
    if token != getattr(settings, "TELEGRAM_NOTIFY_TOKEN", None):
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=403)

    notify_type = (request.GET.get("type") or request.POST.get("type") or "all").lower()
    if notify_type not in ("pregame", "postgame", "all"):
        return JsonResponse(
            {"ok": False, "error": "invalid type, expected pregame/postgame/all"},
            status=400,
        )

    now = timezone.localtime()
    sent_pregame, errors_pregame = 0, []
    sent_postgame, errors_postgame = 0, []

    if notify_type in ("pregame", "all"):
        window_only = notify_type == "all"
        sent, errors = _send_pregame(now, window_only=window_only)
        sent_pregame += sent
        errors_pregame.extend(errors)

    if notify_type in ("postgame", "all"):
        sent, errors = _send_postgame()
        sent_postgame += sent
        errors_postgame.extend(errors)

    return JsonResponse(
        {
            "ok": True,
            "type": notify_type,
            "sent_pregame": sent_pregame,
            "sent_postgame": sent_postgame,
            "errors_pregame": errors_pregame,
            "errors_postgame": errors_postgame,
        }
    )


def _send_pregame(now, window_only: bool):
    sent = 0
    errors = []

    if window_only:
        # cron: отправляем, если до матча осталось не более 24 часов
        window_start = now + timedelta(hours=24)
        candidates = Match.objects.filter(
            status=Match.STATUS_ANNOUNCED,
            pregame_notification_sent=False,
        )
    else:
        # ручной режим: отправляем ближайший анонсированный матч
        match = Match.next_upcoming()
        candidates = [match] if match and not match.pregame_notification_sent else []

    for match in candidates:
        match_start = timezone.make_aware(
            timezone.datetime.combine(match.played_on, match.starts_at)
        )
        if not window_only or (now <= match_start <= window_start):
            try:
                if send_pregame_notification(match):
                    sent += 1
            except Exception as exc:
                errors.append(f"{match.pk}: {exc}")
    return sent, errors


def _send_postgame():
    sent = 0
    errors = []
    match = (
        Match.objects.filter(
            status=Match.STATUS_PLAYED,
            postgame_notification_sent=False,
        )
        .order_by("-played_on", "-id")
        .first()
    )
    if match:
        try:
            if send_postgame_notification(match):
                sent += 1
        except Exception as exc:
            errors.append(f"{match.pk}: {exc}")
    return sent, errors
