from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    path('revenues/', views.revenues, name='revenues'),
    path('revenues/add/', views.revenue_add, name='revenue_add'),
    path('revenues/<int:pk>/', views.revenue_detail, name='revenue_detail'),
    path('expenses/', views.expenses, name='expenses'),  # 👈 root view
]