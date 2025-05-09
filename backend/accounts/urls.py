from django.urls import path
from .views import user_login, CustomPasswordChangeView
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path('login/', user_login, name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    path('change-password/', CustomPasswordChangeView.as_view(), name='change_password'),
]
