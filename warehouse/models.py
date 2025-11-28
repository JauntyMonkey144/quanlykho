from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

# 1. Model Nhân Viên (Giả lập dữ liệu nhân sự để tra cứu)
class Employee(models.Model):
    ma_nhan_vien = models.CharField(max_length=20, unique=True)
    ho_ten = models.CharField(max_length=100)
    email = models.EmailField()
    chuc_vu = models.CharField(max_length=100)
    phong_ban = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.ma_nhan_vien} - {self.ho_ten}"

# 2. Model Phiếu Mượn (Loan)
class LoanSlip(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Nháp (Chờ gửi)'),
        ('dept_pending', 'Chờ Trưởng phòng duyệt'),  # Bước 1
        ('director_pending', 'Chờ Giám đốc duyệt'),  # Bước 2
        ('warehouse_pending', 'Chờ Kho xuất hàng'),  # Bước 3
        ('borrowing', 'Đang mượn (Đã xuất kho)'),    # Hoàn tất mượn
        ('returning', 'Chờ xác nhận trả'),           # Người dùng báo trả
        ('returned', 'Đã trả / Hoàn tất'),           # Kho xác nhận đã nhận
        ('rejected', 'Đã từ chối'),
    )
    
    # Thông tin người mượn
    ma_nhan_vien = models.CharField("Mã NV", max_length=20)
    nguoi_muon = models.CharField("Họ tên", max_length=100) # Tự động điền
    email = models.EmailField("Email") # Tự động điền
    chuc_vu = models.CharField("Chức vụ", max_length=100) # Tự động điền
    phong_ban = models.CharField("Phòng ban", max_length=100) # Tự động điền
    ly_do = models.TextField("Lý do mượn")
    ghi_chu = models.TextField("Ghi chú", blank=True, null=True)    
    ngay_tao = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    user_truong_phong = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='duyet_tp')
    user_giam_doc = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='duyet_gd')
    user_thu_kho_xuat = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='duyet_kho_xuat')
    user_thu_kho_nhap = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='duyet_kho_nhap')
    user_nguoi_tra = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='nguoi_tra')
        # --- THÊM CÁC TRƯỜNG THỜI GIAN (LOGGING) ---
    ngay_gui = models.DateTimeField("Ngày gửi duyệt", null=True, blank=True)
    ngay_truong_phong_duyet = models.DateTimeField("Ngày TP duyệt", null=True, blank=True)
    ngay_giam_doc_duyet = models.DateTimeField("Ngày GĐ duyệt", null=True, blank=True)
    ngay_kho_xac_nhan_muon = models.DateTimeField("Ngày xuất kho", null=True, blank=True)
    # ngay_tra_thuc_te đã có rồi
    ngay_kho_xac_nhan_tra = models.DateTimeField("Ngày nhập kho lại", null=True, blank=True)
    ngay_tu_choi = models.DateTimeField("Ngày từ chối", null=True, blank=True)
    ngay_tra_thuc_te = models.DateTimeField("Ngày trả thực tế", null=True, blank=True)

    def __str__(self):
        return f"Phiếu mượn #{self.id} - {self.nguoi_muon}"
# Hàm hỗ trợ hiển thị màu sắc trạng thái trên giao diện
    @property
    def status_color(self):
        colors = {
            'draft': 'secondary',
            'dept_pending': 'info',
            'director_pending': 'primary',
            'warehouse_pending': 'warning',
            'borrowing': 'success',
            'returning': 'danger',
            'returned': 'dark',
            'rejected': 'danger',
        }
        return colors.get(self.status, 'secondary')

# 3. Model Hàng hóa trong phiếu (Items)
class LoanItem(models.Model):
    loan = models.ForeignKey(LoanSlip, related_name='items', on_delete=models.CASCADE)
    ten_tai_san = models.CharField("Tên tài sản", max_length=200)
    don_vi_tinh = models.CharField("ĐVT", max_length=50)
    so_luong = models.IntegerField("Số lượng", default=1)
    ngay_muon = models.DateField("Ngày mượn", default=timezone.now) # <--- Thêm dòng này
    ngay_tra_du_kien = models.DateField("Ngày trả DK", null=True, blank=True)
    ghi_chu = models.CharField("Ghi chú/Tình trạng", max_length=200, blank=True, null=True)
    # --- THÊM MỚI ---
    TINH_TRANG_CHOICES = (
        ('binh_thuong', 'Bình thường'),
        ('hu_hong', 'Hư hỏng'),
        ('khac', 'Khác (Ghi chú thêm)'),
    )
    
    tinh_trang = models.CharField("Tình trạng", max_length=20, choices=TINH_TRANG_CHOICES, default='binh_thuong')
    tinh_trang_khac = models.CharField("Chi tiết (nếu chọn Khác)", max_length=200, blank=True, null=True)
    
    # Giữ lại ghi chú cũ nếu bạn muốn dùng cho mục đích khác, hoặc xóa đi tùy bạn
    ghi_chu = models.CharField("Ghi chú chung", max_length=200, blank=True, null=True)

    # Hàm này giúp in ra PDF gọn gàng
    @property
    def chi_tiet_tinh_trang(self):
        if self.tinh_trang == 'khac':
            return self.tinh_trang_khac if self.tinh_trang_khac else "Khác"
        return self.get_tinh_trang_display()

# 4. Model Ảnh (Lưu nhiều ảnh lúc mượn và lúc trả)
class LoanImage(models.Model):
    TYPE_CHOICES = (
        ('borrow', 'Trước khi mượn'),
        ('return', 'Sau khi trả'),
    )
    loan = models.ForeignKey(LoanSlip, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='loan_photos/%Y/%m/')
    image_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    uploaded_at = models.DateTimeField(auto_now_add=True)

# --- THÊM MODEL MỚI: LỊCH SỬ XỬ LÝ PHIẾU ---
class LoanHistory(models.Model):
    loan = models.ForeignKey(LoanSlip, on_delete=models.CASCADE, related_name='history')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField("Hành động", max_length=100) # Ví dụ: "Trưởng phòng duyệt"
    timestamp = models.DateTimeField(auto_now_add=True)
    note = models.TextField("Ghi chú", blank=True, null=True)

    def __str__(self):
        return f"{self.loan.id} - {self.action}"

# --- MODEL MỞ RỘNG ĐỂ LƯU CHỮ KÝ ---
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    signature = models.ImageField("Ảnh chữ ký", upload_to='signatures/', blank=True, null=True)

    def __str__(self):
        return f"Profile của {self.user.username}"

# Tự động tạo Profile khi tạo User mới (Signal)
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save() 
