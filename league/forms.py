from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import Appearance, Match, Player


class MatchMetaForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = (
            "status",
            "played_on",
            "starts_at",
            "venue",
            "address",
            "signup_note",
            "team_a_name",
            "team_b_name",
            "notes",
        )
        widgets = {
            "status": forms.Select(attrs={"class": "input"}),
            "played_on": forms.DateInput(attrs={"type": "date", "class": "input"}),
            "starts_at": forms.TimeInput(attrs={"type": "time", "class": "input"}),
            "venue": forms.TextInput(attrs={"class": "input"}),
            "address": forms.TextInput(attrs={"class": "input"}),
            "signup_note": forms.TextInput(
                attrs={"class": "input", "placeholder": "1/10 в заявке · 1 350 ₽ при 10 платящих"}
            ),
            "team_a_name": forms.TextInput(attrs={"class": "input", "placeholder": "Белые"}),
            "team_b_name": forms.TextInput(attrs={"class": "input", "placeholder": "Цветные"}),
            "notes": forms.TextInput(
                attrs={"class": "input", "placeholder": "Короткий комментарий к игре"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and not self.instance.pk:
            self.fields["played_on"].initial = next_sunday()
            self.fields["status"].initial = Match.STATUS_ANNOUNCED


class PlayerLineForm(forms.Form):
    player_id = forms.IntegerField(widget=forms.HiddenInput)
    side = forms.ChoiceField(required=False)
    goals = forms.IntegerField(min_value=0, max_value=30, required=False, initial=0)
    assists = forms.IntegerField(min_value=0, max_value=30, required=False, initial=0)
    saves = forms.IntegerField(min_value=0, max_value=50, required=False, initial=0)

    def __init__(self, *args, player: Player | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.player = player
        for name in ("goals", "assists", "saves"):
            self.fields[name].widget.attrs.update({"class": "stat-input", "inputmode": "numeric"})
        self.fields["side"].widget.attrs.update({"class": "side-select"})
        if player and not self.is_bound:
            self.fields["player_id"].initial = player.pk


def next_sunday():
    today = timezone.localdate()
    days = (6 - today.weekday()) % 7
    return today if days == 0 else today + timedelta(days=days)


def player_line_forms(data=None, team_a="Белые", team_b="Цветные"):
    players = list(Player.objects.filter(is_active=True))
    forms_list = []
    for index, player in enumerate(players):
        prefix = f"p{index}"
        form = PlayerLineForm(data, prefix=prefix, player=player)
        form.fields["side"].choices = [
            ("", "Не идёт"),
            (Appearance.SIDE_SQUAD, "В заявке"),
            (Appearance.SIDE_A, team_a),
            (Appearance.SIDE_B, team_b),
        ]
        forms_list.append(form)
    return forms_list
