from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.views import PasswordChangeView
from django.urls import reverse_lazy
from django.contrib.messages.views import SuccessMessageMixin

def user_login(request):
    # If user is already logged in, redirect to dashboard
    if request.user.is_authenticated:
        return redirect('hostel:dashboard')  # or your homepage

    if request.method == 'POST':
        email = request.POST.get('username')  # 'username' holds the email
        password = request.POST.get('password')
        user = authenticate(request, email=email, password=password)
        if user is not None:
            login(request, user)
            return redirect('hostel:dashboard')
        else:
            messages.error(request, 'Invalid email or password')
    
    return render(request, 'accounts/login.html')

class CustomPasswordChangeView(SuccessMessageMixin, PasswordChangeView):
    template_name = 'accounts/change_password.html'
    success_url = reverse_lazy('hostel:dashboard')
    success_message = "Your password was successfully updated."
