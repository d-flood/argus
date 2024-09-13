# add models to admin
from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin
from core import models


class ArgusAdminSite(admin.AdminSite):
    site_header = "Argus Administration"


admin_site = ArgusAdminSite(name="argus-admin")


class OwnerAdmin(admin.ModelAdmin):
    readonly_fields = ("created_by",)

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is None:
            return True
        return obj.created_by == request.user

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is None:
            return True
        return obj.created_by == request.user

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(created_by=request.user)

    def save_model(self, request, obj, form, change):
        if not change or not obj.created_by:
            obj.created_by = request.user
        obj.save()


class DatasetAdmin(OwnerAdmin):
    readonly_fields = ("created_by", "data", "bms")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "bms":
            kwargs["queryset"] = models.BMSDevice.objects.filter(
                created_by=request.user
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class BMSDeviceAdmin(OwnerAdmin):
    readonly_fields = (
        "created_by",
        "token",
    )  # Make created_by read-only

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is None:
            return True
        return obj.created_by == request.user

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is None:
            return True
        return obj.created_by == request.user

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(created_by=request.user)

    def save_model(self, request, obj, form, change):
        if not change or not obj.created_by:
            obj.created_by = request.user
        obj.save()

    def generate_token_action(self, request, queryset):
        for device in queryset:
            device.generate_token()
        self.message_user(request, "Token(s) generated successfully.")

    generate_token_action.short_description = "Generate token for selected devices"

    actions = [generate_token_action]


admin_site.register(models.BMSDevice, BMSDeviceAdmin)
admin_site.register(models.Dataset, DatasetAdmin)
admin_site.register(User, UserAdmin)
admin_site.register(Group)
