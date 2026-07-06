"""URL configuration for practicenotes.

The catch-all owner/slug routes (GitHub-style namespace) are registered
last, in later milestones; reserved top-level prefixes (admin, api,
accounts, static, media, health, bands, songs, sets, ...) are blocked at
model validation time.
"""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import path
from django.views.generic import TemplateView


def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health", health, name="health"),
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
]
