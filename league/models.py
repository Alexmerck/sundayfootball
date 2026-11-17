from datetime import datetime, time

from django.db import models
from django.db.models import Count, Q, Sum
from django.urls import reverse
from django.utils import timezone


class Player(models.Model):
    name = models.CharField("Имя", max_length=80)
    avatar = models.ImageField("Аватар", upload_to="avatars/%Y/", blank=True)
    is_active = models.BooleanField("В составе", default=True)

    class Meta:
        verbose_name = "Игрок"
        verbose_name_plural = "Игроки"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self):
        return reverse("player-detail", args=[self.pk])

    @property
    def initials(self) -> str:
        parts = [part for part in self.name.split() if part]
        if len(parts) >= 2:
            return f"{parts[0][0]}{parts[1][0]}".upper()
        return self.name[:1].upper()

    def career_totals(self):
        played = Q(match__status=Match.STATUS_PLAYED)
        totals = self.appearances.filter(played).aggregate(
            games=Count("id"),
            goals=Sum("goals"),
            assists=Sum("assists"),
            saves=Sum("saves"),
        )
        games = totals["games"] or 0
        totals["wins"] = sum(
            1
            for app in self.appearances.filter(
                played, side__in=(Appearance.SIDE_A, Appearance.SIDE_B)
            )
            if app.did_win() is True
        )
        totals["win_rate"] = round((totals["wins"] / games) * 100) if games else None
        return totals


class Match(models.Model):
    STATUS_ANNOUNCED = "announced"
    STATUS_PLAYED = "played"
    STATUS_CHOICES = [
        (STATUS_ANNOUNCED, "Анонс"),
        (STATUS_PLAYED, "Сыгран"),
    ]

    played_on = models.DateField("Дата")
    starts_at = models.TimeField("Начало", default=time(12, 0))
    venue = models.CharField("Площадка", max_length=120, default="CAMPUS · Павелецкая")
    address = models.CharField(
        "Адрес",
        max_length=200,
        blank=True,
        default="Москва, ул. Дубининская, д. 68, стр. 11",
    )
    status = models.CharField(
        "Статус",
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_PLAYED,
    )
    signup_note = models.CharField(
        "Заявка",
        max_length=200,
        blank=True,
        help_text="Например: 1/10 в заявке · при 10 платящих 1 350 ₽/чел.",
    )
    team_a_name = models.CharField("Команда А", max_length=40, default="Белые")
    team_b_name = models.CharField("Команда Б", max_length=40, default="Цветные")
    notes = models.CharField("Заметка", max_length=200, blank=True)

    class Meta:
        verbose_name = "Матч"
        verbose_name_plural = "Матчи"
        ordering = ["-played_on", "-id"]

    def __str__(self) -> str:
        label = "анонс" if self.is_announced else "матч"
        return f"{self.played_on:%d.%m.%Y} · {label}"

    def get_absolute_url(self):
        return reverse("match-detail", args=[self.pk])

    @property
    def is_announced(self) -> bool:
        return self.status == self.STATUS_ANNOUNCED

    @property
    def is_played(self) -> bool:
        return self.status == self.STATUS_PLAYED

    def team_a(self):
        return self.appearances.filter(side=Appearance.SIDE_A).select_related("player")

    def team_b(self):
        return self.appearances.filter(side=Appearance.SIDE_B).select_related("player")

    def unassigned(self):
        return self.appearances.filter(side=Appearance.SIDE_SQUAD).select_related("player")

    def squad_size(self) -> int:
        return self.appearances.count()

    def score_a(self) -> int:
        return self.appearances.filter(side=Appearance.SIDE_A).aggregate(
            total=Sum("goals")
        )["total"] or 0

    def score_b(self) -> int:
        return self.appearances.filter(side=Appearance.SIDE_B).aggregate(
            total=Sum("goals")
        )["total"] or 0

    def result_label(self) -> str:
        a, b = self.score_a(), self.score_b()
        if a > b:
            return f"победа {self.team_a_name}"
        if b > a:
            return f"победа {self.team_b_name}"
        return "ничья"

    @classmethod
    def next_upcoming(cls):
        now = timezone.localtime()
        return (
            cls.objects.filter(
                models.Q(played_on__gt=now.date())
                | models.Q(played_on=now.date(), starts_at__gte=now.time())
            )
            .prefetch_related("appearances__player")
            .order_by("played_on", "starts_at", "id")
            .first()
        )


class Appearance(models.Model):
    SIDE_SQUAD = "s"
    SIDE_A = "a"
    SIDE_B = "b"
    SIDE_CHOICES = [
        (SIDE_SQUAD, "В заявке"),
        (SIDE_A, "Команда А"),
        (SIDE_B, "Команда Б"),
    ]

    match = models.ForeignKey(
        Match,
        verbose_name="Матч",
        related_name="appearances",
        on_delete=models.CASCADE,
    )
    player = models.ForeignKey(
        Player,
        verbose_name="Игрок",
        related_name="appearances",
        on_delete=models.CASCADE,
    )
    side = models.CharField("Сторона", max_length=1, choices=SIDE_CHOICES, default=SIDE_SQUAD)
    goals = models.PositiveSmallIntegerField("Голы", default=0)
    assists = models.PositiveSmallIntegerField("Пасы", default=0)
    saves = models.PositiveSmallIntegerField("Сейвы", default=0)

    class Meta:
        verbose_name = "Участие"
        verbose_name_plural = "Участия"
        unique_together = [("match", "player")]
        ordering = ["side", "player__name"]

    def __str__(self) -> str:
        return f"{self.player} · {self.match.played_on}"

    def team_name(self) -> str:
        if self.side == self.SIDE_A:
            return self.match.team_a_name
        if self.side == self.SIDE_B:
            return self.match.team_b_name
        return "В заявке"

    def did_win(self) -> bool | None:
        if not self.match.is_played or self.side == self.SIDE_SQUAD:
            return None
        a, b = self.match.score_a(), self.match.score_b()
        if a == b:
            return None
        if self.side == self.SIDE_A:
            return a > b
        return b > a
