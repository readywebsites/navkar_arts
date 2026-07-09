from django.urls import path
from . import views

app_name = 'generator'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('edit/<int:project_id>/', views.home_view, name='edit_project'),
    path('projects/', views.project_list_view, name='project_list'),
    path('projects/<int:project_id>/', views.project_detail_view, name='project_detail'),
    path('projects/<int:project_id>/quotation/', views.generate_quotation_pdf, name='quotation_pdf'),
    path('projects/<int:project_id>/jobcard/', views.generate_job_card_pdf, name='job_card_pdf'),
    path('projects/delete/<int:project_id>/', views.delete_project_view, name='delete_project'),
]
