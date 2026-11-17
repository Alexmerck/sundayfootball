from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from league.models import Appearance, Match, Player


PLAYERS = [
    "Саша",
    "Дима",
    "Игорь",
    "Кирилл",
    "Макс",
    "Никита",
    "Олег",
    "Паша",
    "Рома",
    "Тимур",
    "Федя",
    "Юра",
]


class Command(BaseCommand):
    help = "Демо-игроки, несколько воскресений и админ admin / sundayleague"

    def handle(self, *args, **options):
        players = []
        for name in PLAYERS:
            player, _ = Player.objects.get_or_create(name=name)
            players.append(player)

        if Match.objects.exists():
            self.stdout.write("Матчи уже есть — состав не трогаю.")
        else:
            last_sunday = date(2026, 11, 15)
            fixtures = [
                {
                    "played_on": last_sunday - timedelta(weeks=3),
                    "a": ["Саша", "Дима", "Кирилл", "Олег", "Тимур", "Федя"],
                    "b": ["Игорь", "Макс", "Никита", "Паша", "Рома", "Юра"],
                    "stats": {
                        "Саша": (2, 1, 0),
                        "Дима": (1, 1, 0),
                        "Кирилл": (0, 1, 0),
                        "Тимур": (0, 0, 4),
                        "Игорь": (1, 0, 0),
                        "Макс": (1, 1, 0),
                        "Юра": (0, 0, 3),
                    },
                    "notes": "Первый холодный вечер",
                },
                {
                    "played_on": last_sunday - timedelta(weeks=2),
                    "a": ["Саша", "Игорь", "Никита", "Рома", "Федя", "Юра"],
                    "b": ["Дима", "Кирилл", "Макс", "Олег", "Паша", "Тимур"],
                    "stats": {
                        "Саша": (1, 2, 0),
                        "Игорь": (2, 0, 0),
                        "Никита": (1, 0, 0),
                        "Юра": (0, 0, 5),
                        "Дима": (1, 0, 0),
                        "Макс": (2, 1, 0),
                        "Олег": (0, 2, 0),
                        "Тимур": (0, 0, 2),
                    },
                    "notes": "Составы перемешали",
                },
                {
                    "played_on": last_sunday - timedelta(weeks=1),
                    "a": ["Дима", "Игорь", "Кирилл", "Паша", "Тимур", "Юра"],
                    "b": ["Саша", "Макс", "Никита", "Олег", "Рома", "Федя"],
                    "stats": {
                        "Дима": (0, 2, 0),
                        "Игорь": (1, 1, 0),
                        "Кирилл": (2, 0, 0),
                        "Тимур": (0, 0, 6),
                        "Саша": (1, 0, 0),
                        "Макс": (0, 1, 0),
                        "Никита": (1, 0, 0),
                        "Федя": (0, 0, 1),
                    },
                    "notes": "5 на 5 + вратари",
                },
                {
                    "played_on": last_sunday,
                    "a": ["Саша", "Кирилл", "Макс", "Паша", "Рома", "Юра"],
                    "b": ["Дима", "Игорь", "Никита", "Олег", "Тимур", "Федя"],
                    "stats": {
                        "Саша": (3, 0, 0),
                        "Макс": (1, 2, 0),
                        "Паша": (0, 1, 0),
                        "Юра": (0, 0, 4),
                        "Дима": (1, 1, 0),
                        "Игорь": (1, 0, 0),
                        "Олег": (1, 1, 0),
                        "Тимур": (0, 0, 7),
                    },
                    "notes": "Голы Саши, сейвы Тимура",
                },
            ]

            by_name = {p.name: p for p in players}
            for fixture in fixtures:
                match = Match.objects.create(
                    played_on=fixture["played_on"],
                    notes=fixture["notes"],
                )
                appearances = []
                for name in fixture["a"]:
                    g, a, s = fixture["stats"].get(name, (0, 0, 0))
                    appearances.append(
                        Appearance(
                            match=match,
                            player=by_name[name],
                            side=Appearance.SIDE_A,
                            goals=g,
                            assists=a,
                            saves=s,
                        )
                    )
                for name in fixture["b"]:
                    g, a, s = fixture["stats"].get(name, (0, 0, 0))
                    appearances.append(
                        Appearance(
                            match=match,
                            player=by_name[name],
                            side=Appearance.SIDE_B,
                            goals=g,
                            assists=a,
                            saves=s,
                        )
                    )
                Appearance.objects.bulk_create(appearances)

            self.stdout.write(self.style.SUCCESS("Добавлены 4 воскресенья."))

        User = get_user_model()
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@sunday.local", "sundayleague")
            self.stdout.write("Админ: admin / sundayleague")
        else:
            self.stdout.write("Админ уже существует.")
