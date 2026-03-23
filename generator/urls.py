from django.urls import path
from . import views

app_name = 'generator'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('projects/', views.project_list_view, name='project_list'),
    path('project/<int:project_id>/', views.project_detail_view, name='project_detail'),
    path('project/<int:project_id>/quotation/', views.generate_quotation_pdf, name='quotation_pdf'),
    path('project/<int:project_id>/jobcard/', views.generate_job_card_pdf, name='job_card_pdf'),
]
