from django.urls import path
from . import views

app_name = 'targets'

urlpatterns = [
    # Super user views
    path('management/', views.target_management, name='management'),
    path('export-excel/', views.export_targets_excel, name='export_excel'),
    path('assign/', views.assign_target, name='assign'),
    path('edit/<int:target_id>/', views.edit_target, name='edit'),
    path('delete/<int:target_id>/', views.delete_target, name='delete'),
    path('statistics/', views.target_statistics, name='statistics'),
    path('contracts/', views.contracts_list, name='contracts'),
    path('contracts/export/', views.export_contracts_excel, name='export_contracts_excel'),

    path('target/<int:target_id>/achievements/', views.target_achievements, name='target_achievements'),
    
    # User views
    path('profile/', views.user_profile, name='profile'),
    path('achievements/<int:year>/<int:month>/', views.achievement_details, name='achievement_details'),
    path('achievements/add/', views.create_rental_contract, name='create_rental_contract'),
]