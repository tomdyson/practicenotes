from django.contrib import admin

from .models import Band, BandInvite, Membership, Owner


@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    list_display = ["slug", "kind", "user", "band", "created_at"]
    list_filter = ["kind"]
    search_fields = ["slug"]


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0


class BandInviteInline(admin.TabularInline):
    model = BandInvite
    extra = 0
    readonly_fields = ["token"]


@admin.register(Band)
class BandAdmin(admin.ModelAdmin):
    list_display = ["name", "created_by", "created_at"]
    search_fields = ["name"]
    inlines = [MembershipInline, BandInviteInline]
