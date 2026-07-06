"""URL configuration for practicenotes.

The catch-all owner/slug routes (GitHub-style namespace) are registered
last, in later milestones; reserved top-level prefixes (admin, api,
accounts, static, media, health, bands, songs, sets, ...) are blocked at
model validation time.
"""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from workspaces import views as workspace_views


def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("health", health, name="health"),
    path("", workspace_views.home, name="home"),
    # Catch-all owner namespace — keep last.
    path("<slug:owner_slug>/", workspace_views.owner_page, name="owner-page"),
]
