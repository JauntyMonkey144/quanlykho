from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.template.loader import render_to_string
from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q 

import pandas as pd
from weasyprint import HTML

# Import Models và Forms
from .models import LoanSlip, LoanImage, LoanItem, Employee
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
            
            # --- XỬ LÝ IMPORT EXCEL ---
            excel_file = request.FILES.get('excel_file')
            if excel_file:
                try:
                    df = pd.read_excel(excel_file)
                    df.columns = df.columns.str.strip().str.lower()
                    
                    for index, row in df.iterrows():
                        ten = row.get('tên tài sản/thiết bị') or row.get('tên tài sản') or row.get('tên')
                        if pd.isna(ten) or str(ten).strip() == '': continue

                        dvt = row.get('đơn vị tính') or row.get('dvt')
                        if pd.isna(dvt): dvt = 'Cái'

                        sl = row.get('số lượng') or row.get('sl')
                        try: sl = int(sl) if pd.notna(sl) else 1
                        except: sl = 1

                        # --- NGÀY THÁNG: Dùng timezone.now() thay vì loan.ngay_muon ---
                        ngay_muon_val = timezone.now().date() 
                        ngay_muon_excel = row.get('ngày mượn')
                        if pd.notna(ngay_muon_excel):
                            try: ngay_muon_val = pd.to_datetime(ngay_muon_excel, dayfirst=True).date()
                            except: pass

                        ngay_tra_val = None
                        ngay_tra_excel = row.get('ngày trả dự kiến') or row.get('ngày trả')
                        if pd.notna(ngay_tra_excel):
                            try: ngay_tra_val = pd.to_datetime(ngay_tra_excel, dayfirst=True).date()
                            except: pass

                        # --- TÌNH TRẠNG ---
                        raw_status = row.get('tình trạng')
                        db_status = 'binh_thuong'
                        db_status_other = ''
                        if pd.notna(raw_status):
                            text_status = str(raw_status).strip().lower()
                            if text_status in ['hư hỏng', 'hỏng']: db_status = 'hu_hong'
                            elif text_status not in ['bình thường', 'tốt']: 
                                db_status = 'khac'
                                db_status_other = str(raw_status).strip()

                        ghi_chu = row.get('ghi chú')
                        if pd.isna(ghi_chu): ghi_chu = ''

                        LoanItem.objects.create(
                            loan=loan,
                            ten_tai_san=ten,
                            don_vi_tinh=dvt,
                            so_luong=sl,
                            ngay_muon=ngay_muon_val,
                            ngay_tra_du_kien=ngay_tra_val,
                            tinh_trang=db_status,
                            tinh_trang_khac=db_status_other,
                            ghi_chu=ghi_chu
                        )
                except Exception as e:
                    messages.warning(request, f"Lỗi Excel: {e}")

            # --- XỬ LÝ FORMSET (NHẬP TAY) ---
            if item_formset.is_valid():
                items = item_formset.save(commit=False)
                for item in items:
                    item.loan = loan
                    item.save()
                for obj in item_formset.deleted_objects:
                    obj.delete()

            # --- XỬ LÝ ẢNH ---
            files = request.FILES.getlist('photos')
            for f in files:
                LoanImage.objects.create(loan=loan, image=f, image_type='borrow')

            messages.success(request, f"Đã tạo phiếu #{loan.id} thành công!")
            return redirect('create_loan')
            
    else:
        form = LoanSlipForm()
        item_formset = LoanItemFormSet()
    
    return render(request, 'warehouse/create_loan.html', {'form': form, 'item_formset': item_formset})

# ============================================
# 2. VIEW SỬA PHIẾU (EDIT LOAN)
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

            # --- XỬ LÝ IMPORT EXCEL (SỬA LỖI TƯƠNG TỰ CREATE) ---
            excel_file = request.FILES.get('excel_file')
            if excel_file:
                try:
                    df = pd.read_excel(excel_file)
                    df.columns = df.columns.str.strip().str.lower()
                    
                    for index, row in df.iterrows():
                        ten = row.get('tên tài sản/thiết bị') or row.get('tên tài sản') or row.get('tên')
                        if pd.isna(ten) or str(ten).strip() == '': continue

                        dvt = row.get('đơn vị tính') or row.get('dvt')
                        if pd.isna(dvt): dvt = 'Cái'

                        sl = row.get('số lượng') or row.get('sl')
                        try: sl = int(sl) if pd.notna(sl) else 1
                        except: sl = 1

                        # --- QUAN TRỌNG: Sửa lỗi ngay_muon tại đây ---
                        ngay_muon_val = timezone.now().date() # Luôn dùng ngày hiện tại làm mặc định
                        
                        ngay_muon_excel = row.get('ngày mượn')
                        if pd.notna(ngay_muon_excel):
                            try: ngay_muon_val = pd.to_datetime(ngay_muon_excel, dayfirst=True).date()
                            except: pass

                        ngay_tra_val = None
                        ngay_tra_excel = row.get('ngày trả dự kiến') or row.get('ngày trả')
                        if pd.notna(ngay_tra_excel):
                            try: ngay_tra_val = pd.to_datetime(ngay_tra_excel, dayfirst=True).date()
                            except: pass

                        raw_status = row.get('tình trạng')
                        db_status = 'binh_thuong'
                        db_status_other = ''
                        if pd.notna(raw_status):
                            text_status = str(raw_status).strip().lower()
                            if text_status in ['hư hỏng', 'hỏng']: db_status = 'hu_hong'
                            elif text_status not in ['bình thường', 'tốt']: 
                                db_status = 'khac'
                                db_status_other = str(raw_status).strip()

                        ghi_chu = row.get('ghi chú')
                        if pd.isna(ghi_chu): ghi_chu = ''

                        LoanItem.objects.create(
                            loan=loan,
                            ten_tai_san=ten,
                            don_vi_tinh=dvt,
                            so_luong=sl,
                            ngay_muon=ngay_muon_val,
                            ngay_tra_du_kien=ngay_tra_val,
                            tinh_trang=db_status,
                            tinh_trang_khac=db_status_other,
                            ghi_chu=ghi_chu
                        )
                except Exception as e:
                    messages.warning(request, f"Lỗi Excel: {e}")

            # --- LƯU FORMSET ---
            if item_formset.is_valid():
                items = item_formset.save(commit=False)
                for item in items:
                    item.loan = loan
                    item.save()
                for obj in item_formset.deleted_objects:
                    obj.delete()

            # --- XÓA ẢNH CŨ ---
            delete_ids = request.POST.getlist('delete_ids')
            if delete_ids:
                LoanImage.objects.filter(id__in=delete_ids, loan=loan).delete()

            # --- THÊM ẢNH MỚI ---
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
        'form': form,
        'item_formset': item_formset,
        'loan': loan
    })

# ============================================
# 3. CÁC VIEW KHÁC (DANH SÁCH, DUYỆT, TRẢ)
# ============================================

@login_required
def loan_list(request):
    loans = LoanSlip.objects.all().order_by('-id')
    return render(request, 'warehouse/loan_list.html', {'loans': loans})

@login_required
def loan_detail(request, pk):
    loan = get_object_or_404(LoanSlip, pk=pk)
    return render(request, 'warehouse/loan_detail.html', {'loan': loan})

@login_required
def loan_action(request, pk, action):
    loan = get_object_or_404(LoanSlip, pk=pk)
    user = request.user
    user_email = [loan.email] # Email người tạo phiếu
    
    # Lấy email các nhóm để gửi thông báo
    giam_doc_emails = get_emails_by_group('GiamDoc')
    thu_kho_emails = get_emails_by_group('ThuKho')
    truong_phong_emails = get_emails_by_group('TruongPhong')
    
    recipients = []
    msg = ""
    
    # --- HÀM KIỂM TRA QUYỀN ---
    def check_perm(group_name):
        # Cho phép nếu user thuộc nhóm HOẶC là Superuser (Admin)
        return user.groups.filter(name=group_name).exists() or user.is_superuser

    # =======================================================
    # XỬ LÝ LOGIC THEO TỪNG HÀNH ĐỘNG
    # =======================================================

    # 1. GỬI DUYỆT (Draft -> Dept Pending)
    if action == 'send':
        if user != loan.created_by and not user.is_superuser:
            messages.error(request, "Bạn không có quyền gửi phiếu này!")
            return redirect('loan_detail', pk=pk)
            
        loan.status = 'dept_pending'
        loan.ngay_gui = timezone.now()  # <--- Thêm dòng này
        recipients = truong_phong_emails
        msg = f"Nhân viên {loan.nguoi_muon} vừa gửi phiếu mượn #{loan.id}. Vui lòng duyệt."

    # 2. TRƯỞNG PHÒNG DUYỆT (Dept -> Director)
    elif action == 'dept_approve':
        if not check_perm('TruongPhong'):
            messages.error(request, "Bạn không có quyền Trưởng Phòng!")
            return redirect('loan_detail', pk=pk)
            
        loan.status = 'director_pending'
        loan.user_truong_phong = request.user  # <--- Lưu đúng người duyệt bước này
        loan.ngay_truong_phong_duyet = timezone.now() # <--- Thêm dòng này
        recipients = giam_doc_emails
        msg = f"Trưởng phòng đã duyệt phiếu #{loan.id}. Xin Giám đốc phê duyệt."

    # 3. GIÁM ĐỐC DUYỆT (Director -> Warehouse)
    elif action == 'director_approve':
        if not check_perm('GiamDoc'):
            messages.error(request, "Bạn không có quyền Giám Đốc!")
            return redirect('loan_detail', pk=pk)
            
        loan.status = 'warehouse_pending'
        loan.user_giam_doc = request.user      # <--- Lưu đúng người duyệt bước này
        loan.ngay_giam_doc_duyet = timezone.now() # <--- Thêm dòng này
        recipients = thu_kho_emails
        msg = f"Giám đốc đã duyệt phiếu #{loan.id}. Vui lòng chuẩn bị xuất kho."

    # 4. KHO XUẤT HÀNG (Warehouse -> Borrowing)
    elif action == 'warehouse_export':
        if not check_perm('ThuKho'):
            messages.error(request, "Bạn không có quyền Thủ Kho!")
            return redirect('loan_detail', pk=pk)
            
        loan.status = 'borrowing'
        loan.user_thu_kho_xuat = request.user  # <--- Lưu người xuất kho
        loan.ngay_kho_xac_nhan_muon = timezone.now() # <--- Thêm dòng này
        recipients = user_email
        msg = f"Phiếu #{loan.id} đã được xuất kho. Bạn đã nhận bàn giao thiết bị."

    # 5. NGƯỜI DÙNG TRẢ (Borrowing -> Returning)
    elif action == 'user_return':
        if user != loan.created_by and not check_perm('ThuKho'):
             messages.error(request, "Bạn không có quyền trả phiếu này!")
             return redirect('loan_detail', pk=pk)

        loan.status = 'returning'
        loan.user_nguoi_tra = request.user     # <--- Lưu người trả hàng
        loan.ngay_tra_thuc_te = timezone.now() # Dòng này đã có, giữ nguyên
        recipients = thu_kho_emails
        msg = f"Người dùng {loan.nguoi_muon} báo đã trả hàng phiếu #{loan.id}. Vui lòng kiểm tra."

    # 6. KHO XÁC NHẬN ĐÃ NHẬN (Returning -> Returned)
    elif action == 'warehouse_confirm':
        if not check_perm('ThuKho'):
            messages.error(request, "Bạn không có quyền Thủ Kho!")
            return redirect('loan_detail', pk=pk)
            
        loan.status = 'returned'
        loan.user_thu_kho_nhap = request.user  # <--- Lưu người nhận lại hàng (MỚI THÊM)
        loan.ngay_kho_xac_nhan_tra = timezone.now() # <--- Thêm dòng này
        recipients = user_email
        msg = f"Kho đã nhận lại đầy đủ hàng phiếu #{loan.id}. Quy trình hoàn tất."

    # 7. TỪ CHỐI (Reject)
    elif action == 'reject':
        if loan.status == 'dept_pending' and not check_perm('TruongPhong'):
             messages.error(request, "Chỉ Trưởng phòng mới được từ chối lúc này!")
             return redirect('loan_detail', pk=pk)
        if loan.status == 'director_pending' and not check_perm('GiamDoc'):
             messages.error(request, "Chỉ Giám đốc mới được từ chối lúc này!")
             return redirect('loan_detail', pk=pk)

        loan.status = 'rejected'
        recipients = user_email
        loan.ngay_tu_choi = timezone.now() # <--- Thêm dòng này
        msg = f"Rất tiếc, phiếu #{loan.id} của bạn đã bị từ chối."

    # Lưu thay đổi vào Database
    loan.save()
    
    # Gửi Email thông báo (kèm PDF)
    if recipients:
        try:
            send_loan_email(request, loan, f"[Thông báo] Trạng thái phiếu #{loan.id}", msg, recipients)
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
            note = form.cleaned_data.get('ghi_chu_tra')
            if note:
                current = timezone.now().strftime("%d/%m")
                loan.ghi_chu = f"{loan.ghi_chu or ''}\n[{current}] Trả: {note}"
            loan.save()
            
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
