from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from league.models import Match
from league.telegram import send_pregame_notification, send_postgame_notification


class Command(BaseCommand):
    help = "Отправляет Telegram-уведомления о предстоящих и прошедших матчах"

    def add_arguments(self, parser):
        parser.add_argument(
            "--type",
            choices=["pregame", "postgame", "all"],
            default="all",
            help="pregame — ближайший анонс, postgame — только последняя игра, all — оба в автоматическом режиме",
        )

    def handle(self, *args, **options):
        notify_type = options["type"]
        now = timezone.localtime()
        sent_pregame, sent_postgame = 0, 0

        if notify_type in ("pregame", "all"):
            sent_pregame, errors_pregame = self._send_pregame(
                now, window_only=(notify_type == "all")
            )
            for err in errors_pregame:
                self.stderr.write(err)

        if notify_type in ("postgame", "all"):
            sent_postgame, errors_postgame = self._send_postgame()
            for err in errors_postgame:
                self.stderr.write(err)

        self.stdout.write(
            self.style.SUCCESS(
                f"Отправлено напоминаний: {sent_pregame}, результатов: {sent_postgame}"
            )
        )

    def _send_pregame(self, now, window_only: bool):
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
                    errors.append(f"Ошибка отправки pregame для {match}: {exc}")
        return sent, errors

    def _send_postgame(self):
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
                errors.append(f"Ошибка отправки postgame для {match}: {exc}")
        return sent, errors
