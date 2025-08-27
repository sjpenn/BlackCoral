"""
Celery configuration for BLACK CORAL
"""
import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blackcoral.settings_dev')

# Create Celery app
app = Celery('blackcoral')

# Configure Celery using Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps
app.autodiscover_tasks()

# Celery beat schedule for periodic tasks
from celery.schedules import crontab

app.conf.beat_schedule = {
    # Agent health checks every 5 minutes
    'agent-health-check': {
        'task': 'apps.agents.tasks.check_agent_health',
        'schedule': crontab(minute='*/5'),
    },
    # SAM.gov sync every hour
    'sam-gov-sync': {
        'task': 'apps.agents.tasks.sync_sam_opportunities',
        'schedule': crontab(minute=0),
    },
    # Clean up old sessions daily
    'cleanup-sessions': {
        'task': 'apps.agents.tasks.cleanup_old_sessions',
        'schedule': crontab(hour=2, minute=0),
    },
    # Agent performance analysis daily
    'agent-performance-analysis': {
        'task': 'apps.agents.tasks.analyze_agent_performance',
        'schedule': crontab(hour=3, minute=0),
    },
    # Phase 3: Periodic opportunity data refresh every 4 hours
    'periodic-opportunity-refresh': {
        'task': 'apps.opportunities.tasks_phase3.periodic_opportunity_refresh',
        'schedule': crontab(minute=0, hour='*/4'),
    },
    # Phase 3: Cleanup old extraction sessions daily
    'cleanup-extraction-sessions': {
        'task': 'apps.opportunities.tasks_phase3.cleanup_old_extraction_sessions',
        'schedule': crontab(hour=1, minute=30),
    },
    # Phase 3: Health check processing pipeline every 30 minutes
    'health-check-processing': {
        'task': 'apps.opportunities.tasks_phase3.health_check_processing_pipeline',
        'schedule': crontab(minute='*/30'),
    },
    # Phase 4: Agent performance monitoring every 15 minutes
    'agent-performance-monitoring': {
        'task': 'apps.agents.tasks_phase4.monitor_agent_performance',
        'schedule': crontab(minute='*/15'),
    },
    # Phase 4: Agent system health check every 30 minutes
    'agent-system-health-check': {
        'task': 'apps.agents.tasks_phase4.health_check_agent_system',
        'schedule': crontab(minute='*/30'),
    },
    # Phase 4: Cleanup completed sessions daily
    'cleanup-completed-sessions': {
        'task': 'apps.agents.tasks_phase4.cleanup_completed_sessions',
        'schedule': crontab(hour=4, minute=0),
    },
}

# Task routing
app.conf.task_routes = {
    'apps.agents.tasks.*': {'queue': 'agents'},
    'apps.opportunities.tasks.*': {'queue': 'opportunities'},
    'apps.documents.tasks.*': {'queue': 'documents'},
    'apps.ai_integration.tasks.*': {'queue': 'ai'},
    # Phase 3: Specialized queues for document processing
    'apps.opportunities.tasks_phase3.process_single_opportunity_documents': {'queue': 'document_processing'},
    'apps.opportunities.tasks_phase3.aggregate_opportunity_data_async': {'queue': 'data_aggregation'},
    'apps.opportunities.tasks_phase3.process_document_batch': {'queue': 'document_processing'},
    'apps.opportunities.tasks_phase3.bulk_process_opportunities': {'queue': 'bulk_processing'},
    'apps.opportunities.tasks_phase3.periodic_opportunity_refresh': {'queue': 'periodic'},
    'apps.opportunities.tasks_phase3.cleanup_old_extraction_sessions': {'queue': 'maintenance'},
    'apps.opportunities.tasks_phase3.health_check_processing_pipeline': {'queue': 'monitoring'},
    # Phase 4: Enhanced AGENT army integration queues
    'apps.agents.tasks_phase4.coordinate_opportunity_analysis': {'queue': 'agent_coordination'},
    'apps.agents.tasks_phase4.execute_agent_task': {'queue': 'agent_execution'},
    'apps.agents.tasks_phase4.bulk_opportunity_analysis': {'queue': 'bulk_analysis'},
    'apps.agents.tasks_phase4.process_coordination_session': {'queue': 'session_management'},
    'apps.agents.tasks_phase4.monitor_agent_performance': {'queue': 'monitoring'},
    'apps.agents.tasks_phase4.cleanup_completed_sessions': {'queue': 'maintenance'},
    'apps.agents.tasks_phase4.health_check_agent_system': {'queue': 'monitoring'},
}

# Task time limits
app.conf.task_time_limit = 3600  # 1 hour hard limit
app.conf.task_soft_time_limit = 3000  # 50 minutes soft limit

# Result backend using Redis
app.conf.result_backend = 'redis://localhost:6379/0'
app.conf.result_expires = 3600  # Results expire after 1 hour

# Worker configuration
app.conf.worker_prefetch_multiplier = 4
app.conf.worker_max_tasks_per_child = 100

@app.task(bind=True)
def debug_task(self):
    """Debug task to test Celery setup"""
    print(f'Request: {self.request!r}')