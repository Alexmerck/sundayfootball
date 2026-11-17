from django.contrib import admin
from django.utils.html import format_html

from .models import Appearance, Match, Player


class AppearanceInline(admin.TabularInline):
    model = Appearance
    extra = 8
    autocomplete_fields = ["player"]
    fields = ("player", "side", "goals", "assists", "saves")


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("thumb", "name", "is_active")
    list_display_links = ("thumb", "name")
    list_filter = ("is_active",)
    search_fields = ("name",)
    fields = ("name", "is_active", "avatar", "avatar_preview")
    readonly_fields = ("avatar_preview",)

    @admin.display(description="")
    def thumb(self, obj: Player):
        if obj.avatar:
            return format_html(
                '<img src="{}" alt="" style="width:36px;height:36px;border-radius:50%;object-fit:cover">',
                obj.avatar.url,
            )
        return obj.initials

    @admin.display(description="Превью")
    def avatar_preview(self, obj: Player):
        if obj.pk and obj.avatar:
            return format_html(
                '<img src="{}" alt="" style="width:96px;height:96px;border-radius:50%;object-fit:cover">',
                obj.avatar.url,
            )
        return "Загрузите файл — друзьям он будет виден на сайте, менять может только админ."


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("played_on", "starts_at", "status", "venue", "signup_note", "squad_size")
    list_filter = ("status", "played_on")
    inlines = [AppearanceInline]
    date_hierarchy = "played_on"
    search_fields = ("venue", "signup_note", "notes", "team_a_name", "team_b_name")
    fieldsets = (
        (
            "Когда и где",
            {"fields": ("played_on", "starts_at", "venue", "address")},
        ),
        (
            "Анонс и команды",
            {
                "fields": (
                    "status",
                    "signup_note",
                    "team_a_name",
                    "team_b_name",
                    "notes",
                )
            },
        ),
    )


@admin.register(Appearance)
class AppearanceAdmin(admin.ModelAdmin):
    list_display = ("match", "player", "side", "goals", "assists", "saves")
    list_filter = ("side", "match")
    autocomplete_fields = ["player", "match"]
