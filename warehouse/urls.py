# warehouse/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Trang chủ là Dashboard
    path('', views.home_view, name='home'), 

    # Các chức năng
    path('loan/create/', views.create_loan, name='create_loan'),
    path('api/employee/', views.api_get_employee, name='api_get_employee'),
    path('loan/<int:pk>/pdf/', views.export_loan_pdf, name='export_loan_pdf'),
    path('api/employee/', views.api_get_employee, name='api_get_employee'),
    path('loan/list/', views.loan_list, name='loan_list'),
    path('loan/<int:pk>/', views.loan_detail, name='loan_detail'),
    path('loan/<int:pk>/action/<str:action>/', views.loan_action, name='loan_action'),
    path('loan/<int:pk>/edit/', views.edit_loan, name='edit_loan'),
    path('loan/<int:pk>/return/', views.return_loan, name='return_loan'),
    path('profile/', views.profile, name='profile'), # <--- Thêm dòng này
]
