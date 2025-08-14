"""
Celery configuration for BLACK CORAL.
Handles background tasks for API calls, document processing, and AI operations.
"""

import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blackcoral.settings')

# Create Celery app
app = Celery('blackcoral')

# Load configuration from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all registered Django apps
app.autodiscover_tasks()

# Configure periodic tasks
app.conf.beat_schedule = {
    # Fetch new opportunities every hour during business hours
    'fetch-sam-gov-opportunities': {
        'task': 'apps.opportunities.tasks.fetch_new_opportunities',
        'schedule': crontab(minute=0, hour='8-18'),  # Every hour 8am-6pm
        'options': {
            'expires': 3600,  # Expire if not executed within an hour
        }
    },
    
    # Daily NAICS code update check
    'update-naics-codes': {
        'task': 'apps.core.tasks.update_naics_codes',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
    },
    
    # Process pending documents every 15 minutes
    'process-pending-documents': {
        'task': 'apps.documents.tasks.process_pending_documents',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    
    # Clean up old sessions daily
    'cleanup-sessions': {
        'task': 'apps.authentication.tasks.cleanup_old_sessions',
        'schedule': crontab(hour=3, minute=0),  # 3 AM daily
    },
}

# Configure task routing
app.conf.task_routes = {
    'apps.opportunities.tasks.*': {'queue': 'opportunities'},
    'apps.documents.tasks.*': {'queue': 'documents'},
    'apps.ai_integration.tasks.*': {'queue': 'ai_processing'},
    'apps.compliance.tasks.*': {'queue': 'compliance'},
}

# Configure task priorities
app.conf.task_annotations = {
    'apps.opportunities.tasks.fetch_opportunity_details': {'priority': 10},
    'apps.documents.tasks.parse_document': {'priority': 8},
    'apps.ai_integration.tasks.generate_summary': {'priority': 6},
    'apps.compliance.tasks.check_compliance': {'priority': 9},
}

# Configure result backend
app.conf.result_expires = 3600  # Results expire after 1 hour

# Error handling
app.conf.task_acks_late = True
app.conf.task_reject_on_worker_lost = True

@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery configuration."""
    print(f'Request: {self.request!r}')