from django.urls import path
from . import views

app_name = 'ai_integration'

urlpatterns = [
    path('', views.ai_dashboard, name='dashboard'),
]