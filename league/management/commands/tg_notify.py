from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from league.models import Match
from league.telegram import send_pregame_notification, send_postgame_notification


class Command(BaseCommand):
    help = "Отправляет Telegram-уведомления о предстоящих и прошедших матчах"

    def handle(self, *args, **options):
        now = timezone.localtime()
        sent_pregame = self._send_pregame(now)
        sent_postgame = self._send_postgame(now)
        self.stdout.write(
            self.style.SUCCESS(
                f"Отправлено напоминаний: {sent_pregame}, результатов: {sent_postgame}"
            )
        )

    def _send_pregame(self, now):
        # Отправляем напоминание за 24 часа до начала (или позже, если cron пропустил)
        window_start = now + timedelta(hours=24)
        candidates = (
            Match.objects.filter(
                status=Match.STATUS_ANNOUNCED,
                pregame_notification_sent=False,
            )
            .select_related("appearances__player")
            .prefetch_related("appearances__player")
        )

        sent = 0
        for match in candidates:
            match_start = timezone.make_aware(
                timezone.datetime.combine(match.played_on, match.starts_at)
            )
            if now <= match_start <= window_start:
                try:
                    if send_pregame_notification(match):
                        sent += 1
                except Exception as exc:
                    self.stderr.write(f"Ошибка отправки pregame для {match}: {exc}")
        return sent

    def _send_postgame(self, now):
        candidates = (
            Match.objects.filter(
                status=Match.STATUS_PLAYED,
                postgame_notification_sent=False,
            )
            .select_related("appearances__player")
            .prefetch_related("appearances__player")
        )

        sent = 0
        for match in candidates:
            try:
                if send_postgame_notification(match):
                    sent += 1
            except Exception as exc:
                self.stderr.write(f"Ошибка отправки postgame для {match}: {exc}")
        return sent
