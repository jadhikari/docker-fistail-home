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
    path('utility-expenses/add/', views.utility_expense_create, name='utility_expense_add'),
    path('utility-expenses/<int:pk>/edit/', views.utility_expense_edit, name='utility_expense_edit'),
    path('utility-expenses/<int:pk>/', views.utility_expense_detail, name='utility_expense_detail'),
    path('registration/<int:customer_id>/', views.registration_fee, name='registration_fee'),
    path('rent/<int:customer_id>/', views.monthly_rent, name='monthly_rent'), 
    path('rent/<int:customer_id>/get-prepaid/', views.get_prepaid_amount_for_month, name='get_prepaid_amount'),
    path('rent/<int:customer_id>/validate-month/', views.validate_rent_month, name='validate_rent_month'),
    path('notification/', views.notification, name='notification'),
    path('staff-expenses/dashboard/', views.staff_expense_dashboard, name='staff_expense_dashboard'),
    path('staff-expenses/<int:pk>/status/', views.staff_expense_update_status, name='staff_expense_update_status'),
    path('staff-expenses/', views.staff_expense_list, name='staff_expense_list'),
    path('staff-expenses/add/', views.staff_expense_create, name='staff_expense_create'),
    path('staff-expenses/<int:pk>/edit/', views.staff_expense_edit, name='staff_expense_edit'),
]
