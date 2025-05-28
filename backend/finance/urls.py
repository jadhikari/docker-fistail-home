from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    path('revenues/', views.revenues, name='revenues'),
    path('revenues/<int:pk>/', views.revenue_detail, name='revenue_detail'),
    path('expenses/', views.expenses, name='expenses'),  # 👈 root view
    path('registration/<int:customer_id>/', views.registration_fee, name='registration_fee'),
    path('rent/<int:customer_id>/', views.monthly_rent, name='monthly_rent'), 
]