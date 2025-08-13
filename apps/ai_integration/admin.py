from django.contrib import admin
from .models import AITask


@admin.register(AITask)
class AITaskAdmin(admin.ModelAdmin):
    list_display = ['task_type', 'ai_service', 'status', 'created_at']
    list_filter = ['task_type', 'ai_service', 'status', 'created_at']
    search_fields = ['opportunity__title', 'document__title']