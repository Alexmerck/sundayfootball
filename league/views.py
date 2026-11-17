from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import MatchMetaForm, player_line_forms
from .models import Appearance, Match, Player


def _leaderboard():
    played = Q(appearances__match__status=Match.STATUS_PLAYED)
    return (
        Player.objects.annotate(
            games=Count("appearances", filter=played),
            goals=Sum("appearances__goals", filter=played),
            assists=Sum("appearances__assists", filter=played),
            saves=Sum("appearances__saves", filter=played),
        )
        .filter(games__gt=0)
        .order_by("-goals", "-assists", "-saves", "name")
    )


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
