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
# --- PHẦN MỚI: PHIẾU MUA HÀNG (PURCHASE) ---
    path('purchase/list/', views.purchase_list, name='purchase_list'),
    path('purchase/create/', views.create_purchase, name='create_purchase'),
    path('purchase/<int:pk>/', views.purchase_detail, name='purchase_detail'),
    
    # === ĐÂY LÀ DÒNG BẠN ĐANG THIẾU ===
    path('purchase/<int:pk>/action/<str:action>/', views.purchase_action, name='purchase_action'),
    path('purchase/<int:pk>/edit/', views.edit_purchase, name='edit_purchase'),
    # URL xuất PDF cho phiếu mua (nếu đã làm)
    path('purchase/<int:pk>/pdf/', views.export_purchase_pdf, name='export_purchase_pdf'),

    path('export/list/', views.export_list, name='export_list'),
    path('export/create/', views.create_export, name='create_export'),
    path('export/<int:pk>/', views.export_detail, name='export_detail'),
    path('export/<int:pk>/edit/', views.edit_export, name='edit_export'),
    path('export/<int:pk>/action/<str:action>/', views.export_action, name='export_action'),
    path('export/<int:pk>/pdf/', views.export_export_pdf, name='export_export_pdf'),
]
