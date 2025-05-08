from django.urls import path
from . import views

app_name = 'hostel'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),  # 👈 root view
    path('hostel/<int:pk>/', views.hostel_detail, name='hostel_detail'),
    path('hostel/unit/<int:pk>/', views.unit_detail, name='unit_detail'),
    path('hostel/add/', views.hostel_create, name='hostel_add'),
    path('hostel/<int:pk>/edit/', views.hostel_update, name='hostel_edit'),
    path('hostel/<int:hostel_id>/units/add/', views.unit_create, name='unit_create'),
    path('unit/<int:pk>/edit/', views.unit_edit, name='unit_edit'),


]