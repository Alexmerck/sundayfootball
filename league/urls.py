from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("table/", views.standings, name="standings"),
    path("dates/", views.match_list, name="match-list"),
    path("rules/", views.rules, name="rules"),
    path("matches/new/", views.match_create, name="match-create"),
    path("matches/<int:pk>/", views.match_detail, name="match-detail"),
    path("players/<int:pk>/", views.player_detail, name="player-detail"),
]
