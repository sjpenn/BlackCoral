"""
BLACK CORAL Notification Views
HTMX-powered real-time notification interface
"""

import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q

from .models import Notification, NotificationPreference, NotificationDigest
from .services import notification_service


@login_required
def notification_center(request):
    """Main notification center view"""
    notifications = notification_service.get_user_notifications(
        user=request.user,
        limit=20
    )
    
    unread_count = notification_service.get_unread_count(request.user)
    
    context = {
        'notifications': notifications,
        'unread_count': unread_count,
    }
    
    return render(request, 'notifications/notification_center.html', context)


@login_required
def notification_list_htmx(request):
    """HTMX endpoint for notification list updates"""
    page = int(request.GET.get('page', 1))
    notification_type = request.GET.get('type', None)
    unread_only = request.GET.get('unread', 'false').lower() == 'true'
    
    # Get notifications with filtering
    notifications = notification_service.get_user_notifications(
        user=request.user,
        unread_only=unread_only,
        notification_type=notification_type,
        limit=100  # Get more for pagination
    )
    
    # Paginate results
    paginator = Paginator(notifications, 10)
    page_obj = paginator.get_page(page)
    
    context = {
        'notifications': page_obj,
        'unread_count': notification_service.get_unread_count(request.user),
    }
    
    return render(request, 'notifications/partials/notification_list.html', context)


@login_required
@require_http_methods(['POST'])
def mark_notification_read(request, notification_id):
    """Mark a specific notification as read"""
    success = notification_service.mark_notification_read(notification_id, request.user)
    
    if request.headers.get('HX-Request'):
        if success:
            # Return updated notification item
            try:
                notification = Notification.objects.get(id=notification_id, user=request.user)
                context = {'notification': notification}
                return render(request, 'notifications/partials/notification_item.html', context)
            except Notification.DoesNotExist:
                return HttpResponse(status=404)
        else:
            return HttpResponse(status=404)
    
    return JsonResponse({'success': success})


@login_required
@require_http_methods(['POST'])
def mark_all_read(request):
    """Mark all notifications as read"""
    notification_type = request.POST.get('notification_type', None)
    count = notification_service.mark_all_read(request.user, notification_type)
    
    if request.headers.get('HX-Request'):
        # Return updated notification list
        return notification_list_htmx(request)
    
    return JsonResponse({'success': True, 'count': count})


@login_required
@require_http_methods(['POST'])
def dismiss_notification(request, notification_id):
    """Dismiss a notification"""
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
        notification.mark_as_dismissed()
        
        if request.headers.get('HX-Request'):
            return HttpResponse('')  # Empty response removes the element
        
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'success': False}, status=404)


@login_required
def notification_count_badge(request):
    """HTMX endpoint for notification count badge"""
    unread_count = notification_service.get_unread_count(request.user)
    
    context = {
        'unread_count': unread_count,
    }
    
    return render(request, 'notifications/partials/notification_badge.html', context)


@login_required
def notification_dropdown(request):
    """HTMX endpoint for notification dropdown"""
    recent_notifications = notification_service.get_user_notifications(
        user=request.user,
        limit=5
    )
    
    unread_count = notification_service.get_unread_count(request.user)
    
    context = {
        'notifications': recent_notifications,
        'unread_count': unread_count,
    }
    
    return render(request, 'notifications/partials/notification_dropdown.html', context)


@login_required
def notification_preferences(request):
    """View and update notification preferences"""
    if request.method == 'POST':
        # Update preferences
        for key, value in request.POST.items():
            if key.startswith('pref_'):
                # Parse preference key: pref_notification_type_delivery_method_setting
                parts = key.split('_')
                if len(parts) >= 4:
                    notification_type = parts[1]
                    delivery_method = parts[2]
                    setting = '_'.join(parts[3:])
                    
                    # Get or create preference
                    pref, created = NotificationPreference.objects.get_or_create(
                        user=request.user,
                        notification_type=notification_type,
                        delivery_method=delivery_method,
                        defaults={'is_enabled': True}
                    )
                    
                    # Update setting
                    if setting == 'enabled':
                        pref.is_enabled = value.lower() == 'true'
                    elif setting == 'immediate':
                        pref.immediate = value.lower() == 'true'
                    elif setting == 'daily_digest':
                        pref.daily_digest = value.lower() == 'true'
                    elif setting == 'weekly_digest':
                        pref.weekly_digest = value.lower() == 'true'
                    
                    pref.save()
        
        if request.headers.get('HX-Request'):
            return HttpResponse('Preferences updated successfully!')
    
    # Get current preferences
    preferences = NotificationPreference.objects.filter(user=request.user)
    
    # Organize preferences by notification type and delivery method
    pref_matrix = {}
    for pref in preferences:
        if pref.notification_type not in pref_matrix:
            pref_matrix[pref.notification_type] = {}
        pref_matrix[pref.notification_type][pref.delivery_method] = pref
    
    context = {
        'notification_types': NotificationPreference.NOTIFICATION_TYPES,
        'delivery_methods': NotificationPreference.DELIVERY_METHODS,
        'preferences': pref_matrix,
    }
    
    return render(request, 'notifications/preferences.html', context)


@login_required
def notification_digests(request):
    """View notification digests"""
    digests = NotificationDigest.objects.filter(
        user=request.user
    ).order_by('-created_at')[:20]
    
    context = {
        'digests': digests,
    }
    
    return render(request, 'notifications/digests.html', context)


@login_required
def notification_digest_detail(request, digest_id):
    """View detailed notification digest"""
    digest = get_object_or_404(
        NotificationDigest,
        id=digest_id,
        user=request.user
    )
    
    context = {
        'digest': digest,
    }
    
    return render(request, 'notifications/digest_detail.html', context)


@login_required
def notification_search(request):
    """Search notifications"""
    query = request.GET.get('q', '')
    notification_type = request.GET.get('type', '')
    
    notifications = Notification.objects.filter(user=request.user)
    
    if query:
        notifications = notifications.filter(
            Q(title__icontains=query) | 
            Q(message__icontains=query)
        )
    
    if notification_type:
        notifications = notifications.filter(notification_type=notification_type)
    
    notifications = notifications.order_by('-created_at')[:50]
    
    if request.headers.get('HX-Request'):
        context = {'notifications': notifications}
        return render(request, 'notifications/partials/search_results.html', context)
    
    context = {
        'notifications': notifications,
        'query': query,
        'selected_type': notification_type,
        'notification_types': NotificationPreference.NOTIFICATION_TYPES,
    }
    
    return render(request, 'notifications/search.html', context)


# API Endpoints for external integrations

@csrf_exempt
@require_http_methods(['POST'])
def webhook_notification(request):
    """Webhook endpoint for external notification systems"""
    try:
        data = json.loads(request.body)
        
        # Validate webhook signature if provided
        # TODO: Implement webhook signature validation
        
        # Extract notification data
        user_email = data.get('user_email')
        notification_type = data.get('type', 'system_update')
        title = data.get('title', 'External Notification')
        message = data.get('message', '')
        priority = data.get('priority', 'medium')
        
        if not user_email:
            return JsonResponse({'error': 'user_email required'}, status=400)
        
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(email=user_email)
            
            notification = notification_service.create_notification(
                user=user,
                notification_type=notification_type,
                title=title,
                message=message,
                priority=priority,
                metadata=data.get('metadata', {})
            )
            
            return JsonResponse({
                'success': True,
                'notification_id': notification.id
            })
            
        except User.DoesNotExist:
            return JsonResponse({'error': 'User not found'}, status=404)
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def notification_stats(request):
    """Get notification statistics for dashboard"""
    today = timezone.now().date()
    week_ago = today - timezone.timedelta(days=7)
    month_ago = today - timezone.timedelta(days=30)
    
    stats = {
        'total_unread': notification_service.get_unread_count(request.user),
        'today': Notification.objects.filter(
            user=request.user,
            created_at__date=today
        ).count(),
        'this_week': Notification.objects.filter(
            user=request.user,
            created_at__date__gte=week_ago
        ).count(),
        'this_month': Notification.objects.filter(
            user=request.user,
            created_at__date__gte=month_ago
        ).count(),
        'by_type': {}
    }
    
    # Get counts by notification type
    type_counts = Notification.objects.filter(
        user=request.user,
        created_at__date__gte=month_ago
    ).values('notification_type').annotate(
        count=models.Count('id')
    ).order_by('-count')
    
    for item in type_counts:
        stats['by_type'][item['notification_type']] = item['count']
    
    return JsonResponse(stats)


# Real-time notification polling endpoint
@login_required
def notification_poll(request):
    """Polling endpoint for real-time notifications"""
    last_check = request.GET.get('last_check')
    
    queryset = Notification.objects.filter(
        user=request.user,
        status='sent'
    )
    
    if last_check:
        try:
            from django.utils.dateparse import parse_datetime
            last_check_time = parse_datetime(last_check)
            if last_check_time:
                queryset = queryset.filter(created_at__gt=last_check_time)
        except:
            pass
    
    new_notifications = list(queryset.order_by('-created_at')[:10])
    
    if request.headers.get('HX-Request'):
        context = {'notifications': new_notifications}
        return render(request, 'notifications/partials/new_notifications.html', context)
    
    return JsonResponse({
        'notifications': [
            {
                'id': n.id,
                'title': n.title,
                'message': n.message,
                'type': n.notification_type,
                'priority': n.priority,
                'created_at': n.created_at.isoformat(),
                'action_url': n.action_url,
                'action_label': n.action_label,
            }
            for n in new_notifications
        ],
        'count': len(new_notifications)
    })