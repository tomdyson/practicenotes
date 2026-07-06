from django.contrib import admin

from .models import Set, SetSong


class SetSongInline(admin.TabularInline):
    model = SetSong
    extra = 0


@admin.register(Set)
class SetAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "slug", "visibility", "created_at"]
    list_filter = ["visibility"]
    search_fields = ["name", "slug", "owner__slug"]
    inlines = [SetSongInline]
