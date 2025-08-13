from django.contrib import admin
from .models import Opportunity


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = ['solicitation_number', 'title', 'agency', 'posted_date', 'response_date']
    list_filter = ['agency', 'posted_date', 'source_api']
    search_fields = ['title', 'solicitation_number', 'description']
    filter_horizontal = ['naics_codes']
    date_hierarchy = 'posted_date'