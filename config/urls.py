"""URL configuration for practicenotes.

The catch-all owner/slug routes (GitHub-style namespace) are registered
last, in later milestones; reserved top-level prefixes (admin, api,
accounts, static, media, health, bands, songs, sets, ...) are blocked at
model validation time.
"""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from setlists import views as set_views
from songs import views as song_views
from workspaces import views as workspace_views


def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("health", health, name="health"),
    path("", workspace_views.home, name="home"),
    # Owner-scoped routes. Sub-paths of /<owner>/ can't collide with content
    # because "songs", "sets" etc. are reserved slugs.
    path("<slug:owner_slug>/songs/new", song_views.song_create, name="song-create"),
    path("<slug:owner_slug>/sets/new", set_views.set_create, name="set-create"),
    path(
        "<slug:owner_slug>/sets/<slug:set_slug>/edit",
        set_views.set_edit,
        name="set-edit",
    ),
    path(
        "<slug:owner_slug>/sets/<slug:set_slug>/delete",
        set_views.set_delete,
        name="set-delete",
    ),
    path(
        "<slug:owner_slug>/sets/<slug:set_slug>/songs/add",
        set_views.set_add_song,
        name="set-add-song",
    ),
    path(
        "<slug:owner_slug>/sets/<slug:set_slug>/songs/<int:entry_id>/remove",
        set_views.set_remove_song,
        name="set-remove-song",
    ),
    path(
        "<slug:owner_slug>/sets/<slug:set_slug>/reorder",
        set_views.set_reorder,
        name="set-reorder",
    ),
    path(
        "<slug:owner_slug>/<slug:song_slug>/edit",
        song_views.song_edit,
        name="song-edit",
    ),
    path(
        "<slug:owner_slug>/<slug:song_slug>/delete",
        song_views.song_delete,
        name="song-delete",
    ),
    path(
        "<slug:owner_slug>/<slug:song_slug>/items/new",
        song_views.item_create,
        name="item-create",
    ),
    path(
        "<slug:owner_slug>/<slug:song_slug>/items/upload",
        song_views.item_upload,
        name="item-upload",
    ),
    path(
        "<slug:owner_slug>/<slug:song_slug>/items/<int:item_id>/file",
        song_views.item_file,
        name="item-file",
    ),
    path(
        "<slug:owner_slug>/<slug:song_slug>/items/reorder",
        song_views.item_reorder,
        name="item-reorder",
    ),
    path(
        "<slug:owner_slug>/<slug:song_slug>/items/<int:item_id>/edit",
        song_views.item_edit,
        name="item-edit",
    ),
    path(
        "<slug:owner_slug>/<slug:song_slug>/items/<int:item_id>/delete",
        song_views.item_delete,
        name="item-delete",
    ),
    # Catch-all owner namespace — keep last.
    path("<slug:owner_slug>/", workspace_views.owner_page, name="owner-page"),
    path(
        "<slug:owner_slug>/<slug:content_slug>/",
        workspace_views.content_page,
        name="content-page",
    ),
]
