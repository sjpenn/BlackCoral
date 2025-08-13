from django.contrib import admin
from .models import NAICSCode, Agency, CapabilitySet


@admin.register(NAICSCode)
class NAICSCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'title', 'level', 'parent_code', 'is_active']
    list_filter = ['level', 'is_active']
    search_fields = ['code', 'title', 'description']
    ordering = ['code']


@admin.register(Agency)
class AgencyAdmin(admin.ModelAdmin):
    list_display = ['abbreviation', 'name', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'abbreviation', 'description']
    ordering = ['name']


@admin.register(CapabilitySet)
class CapabilitySetAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    filter_horizontal = ['naics_codes']