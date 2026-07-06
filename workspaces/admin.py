from django.contrib import admin

from .models import Owner


@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    list_display = ["slug", "kind", "user", "created_at"]
    list_filter = ["kind"]
    search_fields = ["slug"]
