from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Device, Configuration, Publication, DescRun, VmecRun


@admin.register(User)
class UserModelAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'institution', 'is_approved', 'is_staff')
    list_filter = ('is_approved', 'is_staff', 'is_active')
    list_editable = ('is_approved',)
    fieldsets = UserAdmin.fieldsets + (
        ('Stellarator DB', {'fields': ('is_approved', 'institution')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Stellarator DB', {'fields': ('is_approved', 'institution')}),
    )
    search_fields = ('username', 'email', 'first_name', 'last_name', 'institution')


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('deviceid', 'name', 'device_class', 'NFP', 'stell_sym', 'user_created')
    search_fields = ('name', 'description')


@admin.register(Configuration)
class ConfigurationAdmin(admin.ModelAdmin):
    list_display = ('configid', 'name', 'device', 'config_class', 'NFP', 'stell_sym', 'user_created')
    search_fields = ('name', 'description')
    list_filter = ('config_class', 'NFP')


@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ('publicationid', 'correspauthor_firstname', 'correspauthor_lastname', 'DOI')
    search_fields = ('publicationid', 'correspauthor_firstname', 'correspauthor_lastname', 'DOI', 'citation')


@admin.register(DescRun)
class DescRunAdmin(admin.ModelAdmin):
    list_display = ('descrunid', 'config_name', 'version', 'user_created', 'date_created')
    search_fields = ('user_created', 'version', 'description')
    list_filter = ('version', 'vacuum', 'sym')


@admin.register(VmecRun)
class VmecRunAdmin(admin.ModelAdmin):
    list_display = ('vmecrunid', 'config_name', 'vmec_version', 'user_created', 'date_created')
    search_fields = ('user_created', 'vmec_version', 'description')
