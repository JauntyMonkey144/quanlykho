from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve # Dùng để phục vụ Media trên Railway
from warehouse import views as warehouse_views # Import view để làm trang đăng ký

urlpatterns = [
    # 1. Trang Admin
    path('admin/', admin.site.urls),

    # 2. Hệ thống xác thực mặc định (Login, Logout, Password Reset)
    # Django tự tìm template trong thư mục registration/login.html
    path('accounts/', include('django.contrib.auth.urls')),

    # 3. Trang Đăng ký (Tự viết view)
    path('accounts/register/', warehouse_views.register, name='register'),

    # 4. URLs của ứng dụng Kho (Warehouse)
    path('', include('warehouse.urls')),

    # 5. Cấu hình phục vụ file Media trên Railway (BẮT BUỘC)
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]