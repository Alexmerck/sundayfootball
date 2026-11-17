from .models import Appearance


def _player_rating(totals: dict) -> float:
    """Оценка игрока на основе карьерной статистики."""
    return (
        (totals.get("goals") or 0) * 1.0
        + (totals.get("assists") or 0) * 0.7
        + (totals.get("saves") or 0) * 0.4
        + (totals.get("win_rate") or 0) * 0.05
    )


def balance_appearances(appearances):
    """
    Распределяет заявку на две равные команды методом snake-draft.

    Принимает queryset или список Appearance со стороной SIDE_SQUAD.
    Возвращает словарь:
        {
            "team_a": [(appearance, rating), ...],
            "team_b": [(appearance, rating), ...],
            "team_a_rating": float,
            "team_b_rating": float,
        }
    """
    items = []
    for app in appearances:
        if app.side != Appearance.SIDE_SQUAD:
            continue
        totals = app.player.career_totals()
        rating = _player_rating(totals)
        items.append((app, rating, totals))

    # Сортировка по убыванию рейтинга
    items.sort(key=lambda x: x[1], reverse=True)

    team_a, team_b = [], []
    a_rating, b_rating = 0.0, 0.0

    for index, (app, rating, _totals) in enumerate(items):
        # Змейка: 0-A, 1-B, 2-B, 3-A, 4-A, 5-B, 6-B, 7-A...
        snake_group = index // 2
        in_a = (snake_group % 2 == 0 and index % 2 == 0) or (
            snake_group % 2 == 1 and index % 2 == 1
        )
        if in_a:
            team_a.append((app, rating))
            a_rating += rating
        else:
            team_b.append((app, rating))
            b_rating += rating

    return {
        "team_a": team_a,
        "team_b": team_b,
        "team_a_rating": round(a_rating, 1),
        "team_b_rating": round(b_rating, 1),
    }
