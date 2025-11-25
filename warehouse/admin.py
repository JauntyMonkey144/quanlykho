from django.contrib import admin
from .models import Employee, LoanSlip, LoanItem, LoanImage

# =========================================
# 1. QUẢN LÝ NHÂN VIÊN
# =========================================
@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('ma_nhan_vien', 'ho_ten', 'chuc_vu', 'phong_ban')
    search_fields = ('ma_nhan_vien', 'ho_ten', 'email')
    list_filter = ('phong_ban',)

# =========================================
# 2. CẤU HÌNH CHO PHIẾU MƯỢN
# =========================================

# Bảng nhập liệu Hàng hóa (Đã thêm ngày mượn/trả)
class LoanItemInline(admin.TabularInline):
    model = LoanItem
    extra = 0
    min_num = 1
    # Hiển thị các trường mới trong bảng chi tiết
    fields = ('ten_tai_san', 'don_vi_tinh', 'so_luong', 'ngay_muon', 'ngay_tra_du_kien', 'ghi_chu')

# Bảng hình ảnh
class LoanImageInline(admin.TabularInline):
    model = LoanImage
    extra = 0
    fields = ('image', 'image_type', 'uploaded_at')
    readonly_fields = ('uploaded_at',)

# Quản lý chính: Phiếu Mượn
@admin.register(LoanSlip)
class LoanSlipAdmin(admin.ModelAdmin):
    # --- SỬA LỖI TẠI ĐÂY ---
    # Đã xóa 'ngay_tra_du_kien' khỏi list_display
    list_display = (
        'id', 
        'ma_nhan_vien', 
        'nguoi_muon', 
        'phong_ban', 
        'ngay_tao', # Dùng ngày tạo thay thế để theo dõi
        'status',
        'created_by'
    )
    
    # Đã xóa 'ngay_tra_du_kien' khỏi list_filter
    list_filter = ('status', 'phong_ban', 'ngay_tao')
    
    search_fields = ('nguoi_muon', 'ma_nhan_vien', 'ly_do', 'id')
    
    inlines = [LoanItemInline, LoanImageInline]
    
    fieldsets = (
        ('Thông tin người mượn', {
            'fields': ('ma_nhan_vien', 'nguoi_muon', 'email', 'chuc_vu', 'phong_ban')
        }),
        ('Chi tiết phiếu', {
            # Xóa ngay_tra_du_kien ở đây luôn
            'fields': ('ly_do', 'ghi_chu', 'status', 'created_by')
        }),
        ('Thời gian', {
            'fields': ('ngay_tao', 'ngay_tra_thuc_te')
        }),
    )
    
    readonly_fields = ('ngay_tao', 'created_by')
    ordering = ('-id',)