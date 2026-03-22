from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('worker-dashboard/', views.worker_dashboard, name='worker_dashboard'),
    path('create-request/', views.create_request, name='create_request'),
    path('edit-request/<int:pk>/', views.edit_request, name='edit_request'),
    path('close-request/<int:pk>/', views.close_request, name='close_request'),
    path('view-request/<int:pk>/', views.view_request, name='view_request'),
    path('update-money-delivered/', views.update_money_delivered, name='update_money_delivered'),
    path('api/requests/', views.get_requests, name='api_requests'),
    path('api/worker-requests/', views.get_worker_requests, name='api_worker_requests'),
    path('reopen-request/<int:pk>/', views.reopen_request, name='reopen_request'),
    path('generate-tg-code/', views.generate_tg_code, name='generate_tg_code'),
    path('generate-max-code/', views.generate_max_code, name='generate_max_code'),
    path('bind-messengers/', views.bind_messengers, name='bind_messengers'),
]