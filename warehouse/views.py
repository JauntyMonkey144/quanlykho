from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.template.loader import render_to_string
from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q 
from django.utils.safestring import mark_safe # <--- Để hiển thị HTML trong thông báo
from django.urls import reverse               # <--- Để lấy đường dẫn URL
import pandas as pd
from weasyprint import HTML
from .forms import UserUpdateForm, ProfileUpdateForm
# Import Models và Forms
from .models import LoanSlip, LoanImage, LoanItem, Employee, LoanHistory
from .forms import LoanSlipForm, RegistrationForm, LoanItemFormSet, ReturnLoanForm
from .utils import send_loan_email, get_emails_by_group

# ============================================
# CÁC VIEW HỆ THỐNG
# ============================================

def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Tài khoản {username} đã được tạo! Vui lòng đăng nhập.')
            return redirect('login')
    else:
        form = RegistrationForm()
    return render(request, 'registration/register.html', {'form': form})

def home_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
    return render(request, 'home.html')

def home_redirect(request):
    if request.user.is_authenticated:
        return redirect('home')
    return redirect('login')

def api_get_employee(request):
    query = request.GET.get('query')
    if query:
        employees = Employee.objects.filter(
            Q(ma_nhan_vien__icontains=query) | 
            Q(ho_ten__icontains=query)
        )[:10]
        results = []
        for emp in employees:
            results.append({
                'ma_nhan_vien': emp.ma_nhan_vien,
                'ho_ten': emp.ho_ten,
                'email': emp.email,
                'chuc_vu': emp.chuc_vu,
                'phong_ban': emp.phong_ban,
            })
        return JsonResponse({'results': results})
    
    # Logic tìm chính xác
    ma_nv = request.GET.get('ma_nv')
    if ma_nv:
        try:
            emp = Employee.objects.get(ma_nhan_vien=ma_nv)
            return JsonResponse({
                'found': True,
                'ho_ten': emp.ho_ten,
                'email': emp.email,
                'chuc_vu': emp.chuc_vu,
                'phong_ban': emp.phong_ban
            })
        except Employee.DoesNotExist:
            return JsonResponse({'found': False})

    return JsonResponse({'results': []})

# ============================================
# 1. VIEW TẠO PHIẾU MƯỢN
# ============================================
@login_required
def create_loan(request):
    if request.method == 'POST':
        form = LoanSlipForm(request.POST, request.FILES)
        item_formset = LoanItemFormSet(request.POST)

        if form.is_valid():
            loan = form.save(commit=False)
            loan.created_by = request.user
            loan.save()
            
            # --- 1. GHI NHẬT KÝ ---
            LoanHistory.objects.create(
                loan=loan, user=request.user, action="Tạo mới", note=f"Lý do: {loan.ly_do}"
            )

            # --- 2. XỬ LÝ IMPORT EXCEL ---
            excel_file = request.FILES.get('excel_file')
            if excel_file:
                try:
                    df = pd.read_excel(excel_file)
                    df.columns = df.columns.str.strip().str.lower()
                    
                    for index, row in df.iterrows():
                        ten = row.get('tên tài sản/thiết bị') or row.get('tên tài sản') or row.get('tên')
                        if pd.isna(ten) or str(ten).strip() == '': continue

                        dvt = row.get('đơn vị tính') or row.get('dvt') or 'Cái'
                        sl = row.get('số lượng') or row.get('sl') or 1
                        try: sl = int(sl) 
                        except: sl = 1

                        # Xử lý ngày tháng
                        ngay_muon_val = timezone.now().date()
                        if pd.notna(row.get('ngày mượn')):
                            try: ngay_muon_val = pd.to_datetime(row.get('ngày mượn'), dayfirst=True).date()
                            except: pass

                        ngay_tra_val = None
                        if pd.notna(row.get('ngày trả dự kiến')):
                            try: ngay_tra_val = pd.to_datetime(row.get('ngày trả dự kiến'), dayfirst=True).date()
                            except: pass

                        # Xử lý tình trạng
                        raw_status = row.get('tình trạng')
                        db_status = 'binh_thuong'
                        db_status_other = ''
                        if pd.notna(raw_status):
                            text = str(raw_status).lower()
                            if 'hư' in text or 'hỏng' in text: db_status = 'hu_hong'
                            elif 'bình thường' not in text and 'tốt' not in text:
                                db_status = 'khac'
                                db_status_other = str(raw_status)

                        ghi_chu = row.get('ghi chú') or ''

                        LoanItem.objects.create(
                            loan=loan, ten_tai_san=ten, don_vi_tinh=dvt, so_luong=sl,
                            ngay_muon=ngay_muon_val, ngay_tra_du_kien=ngay_tra_val,
                            tinh_trang=db_status, tinh_trang_khac=db_status_other, ghi_chu=ghi_chu
                        )
                except Exception as e:
                    messages.warning(request, f"Lỗi Excel: {e}")

            # --- 3. XỬ LÝ FORMSET ---
            if item_formset.is_valid():
                items = item_formset.save(commit=False)
                for item in items:
                    item.loan = loan
                    item.save()
                for obj in item_formset.deleted_objects:
                    obj.delete()

            # --- 4. XỬ LÝ ẢNH ---
            files = request.FILES.getlist('photos')
            for f in files:
                LoanImage.objects.create(loan=loan, image=f, image_type='borrow')
            detail_url = reverse('loan_detail', args=[loan.id])
            
            # Tạo nội dung HTML cho thông báo
            # class 'alert-link' của Bootstrap giúp link đậm và đẹp hơn trong khung thông báo
            msg_html = f"""
                Đã tạo phiếu <b>#{loan.id}</b> thành công! 
                <a href="{detail_url}" class="alert-link text-decoration-underline">
                    Bấm vào đây để xem chi tiết
                </a>
            """
            messages.success(request, mark_safe(msg_html))
            
            return redirect('create_loan')
            
    else:
        form = LoanSlipForm()
        item_formset = LoanItemFormSet()
    
    return render(request, 'warehouse/create_loan.html', {'form': form, 'item_formset': item_formset})

# ============================================
# 2. VIEW SỬA PHIẾU
# ============================================
@login_required
def edit_loan(request, pk):
    loan = get_object_or_404(LoanSlip, pk=pk)

    if loan.status not in ['draft', 'rejected']:
        messages.error(request, "Chỉ có thể sửa phiếu khi ở trạng thái Nháp hoặc Bị từ chối.")
        return redirect('loan_detail', pk=pk)

    if request.method == 'POST':
        form = LoanSlipForm(request.POST, request.FILES, instance=loan)
        item_formset = LoanItemFormSet(request.POST, instance=loan)

        if form.is_valid():
            loan = form.save(commit=False)
            if loan.status == 'rejected':
                loan.status = 'draft'
            loan.save()
            
            # Ghi nhật ký
            LoanHistory.objects.create(loan=loan, user=request.user, action="Cập nhật phiếu", note="Chỉnh sửa thông tin")

            # (Logic import Excel và Formset tương tự create - Giữ nguyên logic cũ của bạn)
            # ... Bạn dán lại phần logic xử lý Excel/Formset ở đây nếu cần ...
            
            # Xử lý Formset
            if item_formset.is_valid():
                items = item_formset.save(commit=False)
                for item in items:
                    item.loan = loan
                    item.save()
                for obj in item_formset.deleted_objects:
                    obj.delete()
            
            # Xóa ảnh cũ
            delete_ids = request.POST.getlist('delete_ids')
            if delete_ids:
                LoanImage.objects.filter(id__in=delete_ids, loan=loan).delete()
            
            # Thêm ảnh mới
            files = request.FILES.getlist('photos')
            for f in files:
                LoanImage.objects.create(loan=loan, image=f, image_type='borrow')

            messages.success(request, "Đã cập nhật phiếu thành công!")
            return redirect('loan_detail', pk=loan.pk)
    else:
        form = LoanSlipForm(instance=loan)
        item_formset = LoanItemFormSet(instance=loan)
        item_formset.extra = 0 

    return render(request, 'warehouse/edit_loan.html', {
        'form': form, 'item_formset': item_formset, 'loan': loan
    })

# ============================================
# 3. CÁC VIEW KHÁC
# ============================================

@login_required
def loan_list(request):
    loans = LoanSlip.objects.all().order_by('-id')
    return render(request, 'warehouse/loan_list.html', {'loans': loans})

@login_required
def loan_detail(request, pk):
    loan = get_object_or_404(LoanSlip, pk=pk)
    return render(request, 'warehouse/loan_detail.html', {'loan': loan})

# --- HÀM DUYỆT ĐƠN (SỬA LỖI LOGIC) ---
@login_required
def loan_action(request, pk, action):
    loan = get_object_or_404(LoanSlip, pk=pk)
    user = request.user
    user_email = [loan.email]
    
    # Lấy email nhóm
    giam_doc_emails = get_emails_by_group('GiamDoc')
    thu_kho_emails = get_emails_by_group('ThuKho')
    truong_phong_emails = get_emails_by_group('TruongPhong')
    
    recipients = []
    msg = ""
    history_action = ""

    # Hàm check quyền
    def check_perm(group_name):
        return user.groups.filter(name=group_name).exists() or user.is_superuser

    # 1. Gửi duyệt
    if action == 'send':
        if user != loan.created_by and not user.is_superuser:
            messages.error(request, "Không có quyền gửi!")
            return redirect('loan_detail', pk=pk)
        
        loan.status = 'dept_pending'
        loan.ngay_gui = timezone.now()
        history_action = "Gửi duyệt"
        recipients = truong_phong_emails
        msg = "Vui lòng duyệt phiếu."

    # 2. TP Duyệt
    elif action == 'dept_approve':
        if not check_perm('TruongPhong'):
            messages.error(request, "Cần quyền Trưởng phòng!")
            return redirect('loan_detail', pk=pk)
            
        loan.status = 'director_pending'
        loan.user_truong_phong = user
        loan.ngay_truong_phong_duyet = timezone.now()
        history_action = "Trưởng phòng Duyệt"
        recipients = giam_doc_emails
        msg = "Trưởng phòng đã duyệt. Xin Giám đốc phê duyệt."

    # 3. GĐ Duyệt
    elif action == 'director_approve':
        if not check_perm('GiamDoc'):
            messages.error(request, "Cần quyền Giám đốc!")
            return redirect('loan_detail', pk=pk)
            
        loan.status = 'warehouse_pending'
        loan.user_giam_doc = user
        loan.ngay_giam_doc_duyet = timezone.now()
        history_action = "Giám đốc Duyệt"
        recipients = thu_kho_emails
        msg = "Giám đốc đã duyệt. Chuẩn bị xuất kho."

    # 4. Kho xuất
    elif action == 'warehouse_export':
        if not check_perm('ThuKho'):
            messages.error(request, "Cần quyền Thủ kho!")
            return redirect('loan_detail', pk=pk)
            
        loan.status = 'borrowing'
        loan.user_thu_kho_xuat = user
        loan.ngay_kho_xac_nhan_muon = timezone.now()
        history_action = "Kho Xuất hàng"
        recipients = user_email
        msg = "Đã xuất kho. Bạn đã nhận bàn giao."

    # 5. Trả hàng (Fallback)
    elif action == 'user_return':
        # Lưu ý: Thường dùng view return_loan, đây là dự phòng
        if user != loan.created_by and not check_perm('ThuKho'):
             messages.error(request, "Không có quyền trả!")
             return redirect('loan_detail', pk=pk)

        loan.status = 'returning'
        loan.ngay_tra_thuc_te = timezone.now()
        loan.user_nguoi_tra = user
        history_action = f"Yêu cầu Trả hàng ({user.username})"
        recipients = thu_kho_emails
        msg = "Người dùng báo trả hàng."

    # 6. Kho nhận lại
    elif action == 'warehouse_confirm':
        if not check_perm('ThuKho'):
            messages.error(request, "Cần quyền Thủ kho!")
            return redirect('loan_detail', pk=pk)
            
        loan.status = 'returned'
        loan.user_thu_kho_nhap = user
        loan.ngay_kho_xac_nhan_tra = timezone.now()
        
        # Bổ sung nếu bước trước chưa lưu ngày trả
        if not loan.ngay_tra_thuc_te:
            loan.ngay_tra_thuc_te = timezone.now()
            
        history_action = "Kho xác nhận Đã nhận"
        recipients = user_email
        msg = "Đã hoàn tất trả hàng."

    # 7. Từ chối
    elif action == 'reject':
        # Check quyền từ chối tùy bước (TP chỉ từ chối khi đang chờ TP...)
        can_reject = False
        if loan.status == 'dept_pending' and check_perm('TruongPhong'): can_reject = True
        elif loan.status == 'director_pending' and check_perm('GiamDoc'): can_reject = True
        
        if not can_reject and not user.is_superuser:
             messages.error(request, "Không có quyền từ chối lúc này!")
             return redirect('loan_detail', pk=pk)

        loan.status = 'rejected'
        loan.ngay_tu_choi = timezone.now()
        history_action = f"Từ chối ({user.username})"
        recipients = user_email
        msg = "Phiếu bị từ chối."

    loan.save()
    
    # Ghi nhật ký
    if history_action:
        LoanHistory.objects.create(
            loan=loan, user=user, action=history_action,
            note=f"Trạng thái: {loan.get_status_display()}"
        )
    
    # Gửi mail
    if recipients:
        try:
            send_loan_email(request, loan, f"[Thông báo] Phiếu #{loan.id}", msg, recipients)
        except Exception as e:
            print(f"Lỗi gửi mail: {e}")
        
    messages.success(request, f"Đã cập nhật trạng thái: {loan.get_status_display()}")
    return redirect('loan_detail', pk=pk)

@login_required
def return_loan(request, pk):
    loan = get_object_or_404(LoanSlip, pk=pk)
    if loan.status != 'borrowing':
        messages.error(request, "Phiếu không ở trạng thái đang mượn.")
        return redirect('loan_detail', pk=pk)

    if request.method == 'POST':
        form = ReturnLoanForm(request.POST, request.FILES)
        if form.is_valid():
            files = request.FILES.getlist('return_images')
            for f in files:
                LoanImage.objects.create(loan=loan, image=f, image_type='return')
            
            loan.status = 'returning'
            loan.ngay_tra_thuc_te = timezone.now()
            loan.user_nguoi_tra = request.user
            
            note = form.cleaned_data.get('ghi_chu_tra')
            if note:
                current = timezone.now().strftime("%d/%m")
                loan.ghi_chu = f"{loan.ghi_chu or ''}\n[{current}] Trả: {note}"
            loan.save()
            
            # Ghi nhật ký
            LoanHistory.objects.create(
                loan=loan, user=request.user, action="Yêu cầu Trả hàng",
                note=f"Ghi chú trả: {note}" if note else ""
            )
            
            messages.success(request, "Đã gửi yêu cầu trả hàng!")
            return redirect('loan_detail', pk=pk)
    else:
        form = ReturnLoanForm()

    return render(request, 'warehouse/return_loan.html', {'loan': loan, 'form': form})

def export_loan_pdf(request, pk):
    loan = get_object_or_404(LoanSlip, pk=pk)
    html_string = render_to_string('warehouse/pdf/loan_template.html', {
        'loan': loan,
        'items': loan.items.all(),
        'request': request
    })
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename=phieu_{pk}.pdf'
    HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)
    return response

@login_required
def profile(request):
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.profile)
        
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, 'Tài khoản của bạn đã được cập nhật!')
            return redirect('profile') # Load lại trang profile
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)

    context = {
        'u_form': u_form,
        'p_form': p_form
    }
    return render(request, 'warehouse/profile.html', context)
