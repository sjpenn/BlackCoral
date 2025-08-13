from django.contrib import admin
from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'opportunity', 'file_type', 'processing_status', 'created_at']
    list_filter = ['file_type', 'processing_status', 'created_at']
    search_fields = ['title', 'opportunity__title']