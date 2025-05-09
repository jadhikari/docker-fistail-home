from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    path('revenues/', views.revenues, name='revenues'),  # 👈 root view
    path('expenses/', views.expenses, name='expenses'),  # 👈 root view
]