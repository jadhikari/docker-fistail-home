from django.urls import path
from . import views

app_name = 'hostel'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),  # 👈 root view
    path('hostel/<int:pk>/', views.hostel_detail, name='hostel_detail'),
    path('hostel/unit/<int:pk>/', views.unit_detail, name='unit_detail'),
]