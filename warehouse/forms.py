from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column
from django.forms import inlineformset_factory
from .models import LoanItem # Nhớ import thêm LoanItem ở đầu file
# === QUAN TRỌNG: DÒNG NÀY SỬA LỖI NAME ERROR CỦA BẠN ===
from .models import LoanSlip 

# ==========================================
# 1. WIDGET TÙY CHỈNH (UPLOAD NHIỀU ẢNH)
# ==========================================
class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result

# ==========================================
# 2. FORM ĐĂNG KÝ TÀI KHOẢN
# ==========================================
class RegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True, 
        label="Địa chỉ Email",
        help_text="Dùng để nhận thông báo và lấy lại mật khẩu."
    )
    first_name = forms.CharField(required=True, label="Tên")
    last_name = forms.CharField(required=True, label="Họ đệm")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'last_name', 'first_name') 
        help_texts = {
            'username': 'Tên đăng nhập viết liền không dấu.',
        }

    def __init__(self, *args, **kwargs):
        super(RegistrationForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'username',
            Row(
                Column('last_name', css_class='form-group col-md-6 mb-0'),
                Column('first_name', css_class='form-group col-md-6 mb-0'),
            ),
            'email',
            'password1', 
            'password2',
            Submit('submit', 'Đăng Ký Tài Khoản', css_class='btn btn-success w-100 mt-4 fw-bold')
        )

# ==========================================
# 3. FORM TẠO PHIẾU MƯỢN (LoanSlipForm)
# ==========================================
class LoanSlipForm(forms.ModelForm):
    # Field ảo: Import Excel
    excel_file = forms.FileField(
        label="Import Excel (Tên, ĐVT, SL)", required=False,
        widget=forms.FileInput(attrs={'accept': '.xlsx, .xls'})
    )
    
    # Field ảo: Upload nhiều ảnh
    photos = MultipleFileField(
        label="Ảnh hiện trạng (Chọn nhiều/Chụp ảnh)", required=False,
        widget=MultipleFileInput(attrs={'multiple': True, 'accept': 'image/*', 'capture': 'environment'})
    )

    class Meta:
        model = LoanSlip  # <--- Đây là chỗ bị lỗi nếu thiếu import
        fields = ['ma_nhan_vien', 'nguoi_muon', 'email', 'chuc_vu', 'phong_ban','ly_do', 'ghi_chu']
        widgets = {
            'nguoi_muon': forms.TextInput(attrs={'readonly': 'readonly'}),
            'email': forms.TextInput(attrs={'readonly': 'readonly'}),
            'chuc_vu': forms.TextInput(attrs={'readonly': 'readonly'}),
            'phong_ban': forms.TextInput(attrs={'readonly': 'readonly'}),
            'ly_do': forms.Textarea(attrs={'rows': 3}),
        }

# === 1. ĐỊNH NGHĨA FORM CON (HÀNG HÓA) - BẠN ĐANG THIẾU CÁI NÀY ===
class LoanItemForm(forms.ModelForm):
    class Meta:
        model = LoanItem
        # Thêm tinh_trang và tinh_trang_khac vào fields
        fields = ['ten_tai_san', 'don_vi_tinh', 'so_luong', 'ngay_muon', 'ngay_tra_du_kien', 'tinh_trang', 'tinh_trang_khac', 'ghi_chu']
        
        widgets = {
            'ngay_muon': forms.DateInput(attrs={'type': 'date'}),
            'ngay_tra_du_kien': forms.DateInput(attrs={'type': 'date'}),
            
            # Thêm class để Javascript bắt sự kiện
            'tinh_trang': forms.Select(attrs={'class': 'form-select condition-select form-select-sm'}),
            'tinh_trang_khac': forms.TextInput(attrs={'class': 'form-control condition-input form-control-sm', 'placeholder': 'Nhập tình trạng...'}),
            
            'ten_tai_san': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'don_vi_tinh': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'so_luong': forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
            'ghi_chu': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
        }
        labels = {
            'ten_tai_san': '', 'don_vi_tinh': '', 'so_luong': '', 'ngay_muon': '', 'ngay_tra_du_kien': '',
            'tinh_trang': '', 'tinh_trang_khac': '', 'ghi_chu': ''
        }

class ReturnLoanForm(forms.Form):
    # Form này không kế thừa ModelForm vì ta chỉ cần xử lý ảnh và ghi chú trả
    return_images = MultipleFileField(
        label="Ảnh trả hàng (Chụp ảnh tình trạng khi trả)",
        required=True, # Bắt buộc phải có ảnh mới cho trả
        widget=MultipleFileInput(attrs={'multiple': True, 'accept': 'image/*', 'capture': 'environment'})
    )
    ghi_chu_tra = forms.CharField(
        label="Ghi chú tình trạng trả (Hư hỏng/Mất mát...)",
        required=False,
        widget=forms.Textarea(attrs={'rows': 3})
    ) 

# === 2. TẠO FORMSET (QUẢN LÝ DANH SÁCH) ===
LoanItemFormSet = inlineformset_factory(
    LoanSlip, LoanItem,
    form=LoanItemForm,  # Lúc này Python đã hiểu LoanItemForm là gì
    extra=1,            # Hiển thị sẵn 1 dòng trống
    can_delete=True,     # Cho phép xóa
    max_num=100  # <--- THÊM DÒNG NÀY để cho phép nhập tối đa 100 dòng
)