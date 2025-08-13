from django.contrib import admin
from .models import ComplianceRule, ComplianceCheck


@admin.register(ComplianceRule)
class ComplianceRuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'rule_type', 'agency', 'severity', 'is_active']
    list_filter = ['rule_type', 'severity', 'agency', 'is_active']
    search_fields = ['name', 'description', 'rule_text']


@admin.register(ComplianceCheck)
class ComplianceCheckAdmin(admin.ModelAdmin):
    list_display = ['rule', 'status', 'opportunity', 'auto_detected', 'created_at']
    list_filter = ['status', 'auto_detected', 'rule__rule_type', 'created_at']
    search_fields = ['rule__name', 'opportunity__title', 'details']