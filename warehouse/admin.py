from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, Employee, LoanSlip, LoanItem, LoanImage, PurchaseSlip, PurchaseItem, PurchaseImage, PurchaseHistory
from django.utils.html import format_html
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
# 1. Định nghĩa Inline để hiện ô upload chữ ký ngay trong trang User
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Thông tin mở rộng (Chữ ký)'

# 2. Hủy đăng ký User cũ và đăng ký lại với Inline mới
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)

admin.site.unregister(User)
admin.site.register(User, UserAdmin)

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

class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 0
    min_num = 1
    can_delete = True
    classes = ['collapse']

class PurchaseImageInline(admin.TabularInline):
    model = PurchaseImage
    extra = 0
    readonly_fields = ['preview_image']

    def preview_image(self, obj):
        if obj.image:
            # SỬA LỖI: Tách biến ra khỏi chuỗi
            return format_html(
                '<img src="{}" style="height: 50px; border-radius: 5px;" />',
                obj.image.url
            )
        return "-"
    preview_image.short_description = "Xem trước"

class PurchaseHistoryInline(admin.TabularInline):
    model = PurchaseHistory
    extra = 0
    readonly_fields = ['user', 'action', 'timestamp', 'note']
    can_delete = False
    classes = ['collapse']

@admin.register(PurchaseSlip)
class PurchaseSlipAdmin(admin.ModelAdmin):
    list_display = ('get_id', 'nguoi_de_xuat', 'phong_ban', 'get_status_colored', 'ngay_tao')
    list_filter = ('status', 'phong_ban', 'ngay_tao')
    search_fields = ('nguoi_de_xuat', 'ma_nhan_vien', 'id')
    inlines = [PurchaseItemInline, PurchaseImageInline, PurchaseHistoryInline]
    readonly_fields = ('ngay_tao', 'ngay_gui', 'ngay_phu_trach_duyet', 'ngay_giam_doc_duyet')

    def get_id(self, obj):
        return f"#{obj.id:04d}"
    get_id.short_description = 'Mã phiếu'
    get_id.admin_order_field = 'id'

    def get_status_colored(self, obj):
        colors = {
            'draft': 'gray',
            'dept_pending': 'blue',
            'director_pending': 'orange',
            'approved': 'green',
            'completed': 'teal',
            'rejected': 'red',
        }
        color = colors.get(obj.status, 'black')
        # SỬA LỖI: Dùng cú pháp chuẩn {} của format_html
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    get_status_colored.short_description = 'Trạng thái'