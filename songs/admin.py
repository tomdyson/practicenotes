from django.contrib import admin

from .models import Item, Song


class ItemInline(admin.TabularInline):
    model = Item
    extra = 0
    fields = ["position", "kind", "title", "format", "original_filename", "size"]


@admin.register(Song)
class SongAdmin(admin.ModelAdmin):
    list_display = ["title", "owner", "slug", "visibility", "created_at"]
    list_filter = ["visibility"]
    search_fields = ["title", "slug", "owner__slug"]
    inlines = [ItemInline]
