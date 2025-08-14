from django.contrib import admin
from .models import AITask


@admin.register(AITask)
class AITaskAdmin(admin.ModelAdmin):
    list_display = ['task_type', 'ai_provider', 'model_used', 'status', 'confidence_score', 'created_at']
    list_filter = ['task_type', 'ai_provider', 'status', 'created_at']
    search_fields = ['opportunity__title', 'document__title', 'model_used']
    readonly_fields = ['tokens_used', 'processing_time', 'confidence_score', 'created_at', 'updated_at']