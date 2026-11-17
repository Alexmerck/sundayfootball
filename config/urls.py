from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Sunday League"
admin.site.site_title = "Sunday League"
admin.site.index_title = "Матчи, игроки и статистика"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("league.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
