from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import UserSession


def login_view(request):
    """
    Custom login view with session tracking and HTMX support.
    """
    # If user is already authenticated, redirect to dashboard
    if request.user.is_authenticated:
        if request.headers.get('HX-Request'):
            # For HTMX requests, redirect with HX-Redirect header
            from django.http import HttpResponse
            response = HttpResponse()
            response['HX-Redirect'] = '/dashboard/'
            return response
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            
            # Track user session
            UserSession.objects.create(
                user=user,
                session_key=request.session.session_key,
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                login_time=timezone.now()
            )
            
            # Update last activity
            user.last_activity = timezone.now()
            user.save()
            
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            
            # Handle HTMX login
            if request.headers.get('HX-Request'):
                from django.http import HttpResponse
                response = HttpResponse()
                response['HX-Redirect'] = '/dashboard/'
                return response
            
            return redirect('core:dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'authentication/login.html')


@login_required
def logout_view(request):
    """
    Custom logout view with session cleanup.
    """
    # Update session record
    try:
        session = UserSession.objects.filter(
            user=request.user,
            session_key=request.session.session_key,
            logout_time__isnull=True
        ).first()
        if session:
            session.logout_time = timezone.now()
            session.save()
    except UserSession.DoesNotExist:
        pass
    
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('authentication:login')


@login_required
def profile_view(request):
    """
    User profile view.
    """
    context = {
        'user': request.user,
        'recent_sessions': UserSession.objects.filter(user=request.user)[:5]
    }
    return render(request, 'authentication/profile.html', context)