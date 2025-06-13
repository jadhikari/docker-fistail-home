from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    path('revenues/', views.revenues, name='revenues'),
    path('revenues/<int:pk>/', views.revenue_detail, name='revenue_detail'),
    path('expenses/', views.expenses, name='expenses'),  # 👈 root view
    path('expenses/add/', views.hostel_expense_create, name='hostel_expense_add'),
    path('expenses/<int:pk>/edit/', views.hostel_expense_edit, name='hostel_expense_edit'),
    path('expenses/<int:pk>/', views.hostel_expense_detail, name='hostel_expense_detail'),
    path('registration/<int:customer_id>/', views.registration_fee, name='registration_fee'),
    path('rent/<int:customer_id>/', views.monthly_rent, name='monthly_rent'), 
    path('notification/', views.notification, name='notification'),  
]