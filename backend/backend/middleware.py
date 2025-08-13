import time
from django.contrib.auth import logout
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

class SessionTimeoutMiddleware:
    """
    Middleware to handle session timeout after 20 minutes of inactivity.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Check if user is authenticated
        if request.user.is_authenticated:
            # Get current timestamp
            current_time = time.time()
            
            # Get last activity timestamp from session
            last_activity = request.session.get('last_activity', current_time)
            
            # Check if 20 minutes (1200 seconds) have passed since last activity
            if current_time - last_activity > 1200:
                # Session expired, logout user
                logout(request)
                messages.warning(request, 'Your session has expired due to inactivity. Please log in again.')
                return redirect(reverse('login'))
            
            # Update last activity timestamp
            request.session['last_activity'] = current_time
            
        response = self.get_response(request)
        return response
