from datetime import date
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from .models import Appearance, Match, Player


class LeagueTests(TestCase):
    def setUp(self):
        self.sasha = Player.objects.create(name="Саша")
        self.dima = Player.objects.create(name="Дима")
        self.timur = Player.objects.create(name="Тимур")
        self.match = Match.objects.create(played_on=date(2026, 11, 15))
        Appearance.objects.create(
            match=self.match, player=self.sasha, side=Appearance.SIDE_A, goals=2, assists=1
        )
        Appearance.objects.create(
            match=self.match, player=self.dima, side=Appearance.SIDE_B, goals=1
        )
        Appearance.objects.create(
            match=self.match, player=self.timur, side=Appearance.SIDE_B, saves=4
        )

    def test_score_comes_from_goals(self):
        self.assertEqual(self.match.score_a(), 2)
        self.assertEqual(self.match.score_b(), 1)

    def test_player_can_switch_teams_next_week(self):
        next_match = Match.objects.create(played_on=date(2026, 11, 8), team_a_name="Красные")
        Appearance.objects.create(
            match=next_match, player=self.sasha, side=Appearance.SIDE_B, goals=1
        )
        sides = list(
            self.sasha.appearances.order_by("match__played_on").values_list("side", flat=True)
        )
        self.assertEqual(sides, [Appearance.SIDE_B, Appearance.SIDE_A])

    def test_home_shows_table(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Саша")
        self.assertContains(response, "2")

    def test_create_match(self):
        payload = {
            "played_on": "2026-11-01",
            "team_a_name": "Белые",
            "team_b_name": "Цветные",
            "notes": "",
        }
        sides = {self.sasha.pk: "a", self.dima.pk: "b", self.timur.pk: ""}
        goals = {self.sasha.pk: "1", self.dima.pk: "0", self.timur.pk: "0"}
        assists = {self.sasha.pk: "0", self.dima.pk: "1", self.timur.pk: "0"}
        for index, player in enumerate(Player.objects.filter(is_active=True)):
            payload.update(
                {
                    f"p{index}-player_id": player.pk,
                    f"p{index}-side": sides[player.pk],
                    f"p{index}-goals": goals[player.pk],
                    f"p{index}-assists": assists[player.pk],
                    f"p{index}-saves": "0",
                }
            )
        response = self.client.post(reverse("match-create"), payload)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)
        self.assertFalse(Match.objects.filter(played_on=date(2026, 11, 1)).exists())

        staff = get_user_model().objects.create_user(
            "coach", password="secret", is_staff=True
        )
        self.client.force_login(staff)
        response = self.client.post(reverse("match-create"), payload)
        self.assertEqual(response.status_code, 302)
        created = Match.objects.get(played_on=date(2026, 11, 1))
        self.assertEqual(created.score_a(), 1)
        self.assertEqual(created.appearances.count(), 2)

    def test_avatar_shows_on_player_page(self):
        buffer = BytesIO()
        Image.new("RGB", (8, 8), "#1f6a43").save(buffer, format="PNG")
        self.sasha.avatar = SimpleUploadedFile(
            "sasha.png", buffer.getvalue(), content_type="image/png"
        )
        self.sasha.save()
        response = self.client.get(self.sasha.get_absolute_url())
        self.assertContains(response, self.sasha.avatar.url)
        self.assertNotContains(response, "Изменить аватар")
