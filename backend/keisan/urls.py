from django.urls import path
from . import views

app_name = 'keisan'

urlpatterns = [
    # Business URLs (main dashboard)
    path('', views.business_list, name='dashboard'),
    path('businesses/', views.business_list, name='business_list'),
    path('businesses/create/', views.business_create, name='business_create'),
    path('businesses/<int:pk>/', views.business_detail, name='business_detail'),
    path('businesses/<int:pk>/edit/', views.business_edit, name='business_edit'),
    
    # Municipal Shop URLs
    path('shops/create/', views.shop_create, name='shop_create'),
    path('shops/<int:pk>/', views.shop_detail, name='shop_detail'),
    path('shops/<int:pk>/edit/', views.shop_edit, name='shop_edit'),
    
    # Staff URLs
    path('staff/create/', views.staff_create, name='staff_create'),
    path('staff/<int:pk>/', views.staff_detail, name='staff_detail'),
    path('staff/<int:pk>/edit/', views.staff_edit, name='staff_edit'),
    
    # Dependent URLs
    path('staff/<int:staff_id>/dependents/create/', views.dependent_create, name='dependent_create'),
    path('dependents/<int:pk>/edit/', views.dependent_edit, name='dependent_edit'),
    
    # AJAX URLs
    path('ajax/business/<int:business_id>/shops/', views.get_business_shops, name='get_business_shops'),
    path('ajax/business/<int:business_id>/staff/', views.get_staff_by_business, name='get_staff_by_business'),
]
