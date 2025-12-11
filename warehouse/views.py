from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.auth.models import User
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
from .utils import send_loan_email, get_emails_by_group, send_purchase_email
from .models import PurchaseSlip, PurchaseItem, PurchaseHistory, PurchaseImage # Import
from .forms import PurchaseSlipForm, PurchaseItemFormSet # Import
from .models import ExportSlip, ExportItem, ExportImage, ExportHistory
from .forms import ExportSlipForm, ExportItemFormSet
from .utils import send_export_email # Import hàm mới
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

# 1. TẠO PHIẾU XUẤT
@login_required
def create_export(request):
    if request.method == 'POST':
        form = ExportSlipForm(request.POST, request.FILES)
        item_formset = ExportItemFormSet(request.POST)

        if form.is_valid():
            slip = form.save(commit=False)
            slip.created_by = request.user
            slip.save()
            
            # Ghi nhật ký khởi tạo
            ExportHistory.objects.create(
                slip=slip, user=request.user, action="Tạo mới", note=f"Lý do: {slip.ly_do}"
            )

            # --- XỬ LÝ IMPORT EXCEL ---
            excel_file = request.FILES.get('excel_file')
            if excel_file:
                try:
                    df = pd.read_excel(excel_file)
                    df.columns = df.columns.str.strip().str.lower()
                    
                    def find_col(df, keywords):
                        for col in df.columns:
                            if all(k in col for k in keywords): return col
                        return None

                    for index, row in df.iterrows():
                        # Tìm cột Tên (Bắt buộc)
                        col_ten = find_col(df, ['tên']) 
                        ten = row.get(col_ten)
                        if pd.isna(ten) or str(ten).strip() == '': continue
                        
                        # Tìm cột ĐVT, SL, Ghi chú
                        col_dvt = find_col(df, ['đơn', 'vị']) or find_col(df, ['dvt'])
                        dvt = row.get(col_dvt) or 'Cái'

                        col_sl = find_col(df, ['số', 'lượng']) or find_col(df, ['sl'])
                        try:
                            sl = int(row.get(col_sl)) if pd.notna(row.get(col_sl)) else 1
                        except: sl = 1

                        col_gc = find_col(df, ['ghi', 'chú'])
                        ghi_chu = row.get(col_gc) or ''

                        ExportItem.objects.create(
                            slip=slip, ten_hang_hoa=ten, don_vi_tinh=dvt, 
                            so_luong=sl, ghi_chu=ghi_chu
                        )
                except Exception as e:
                    messages.warning(request, f"Lỗi đọc file Excel: {e}")

            # --- LƯU FORMSET (Dữ liệu nhập tay) ---
            if item_formset.is_valid():
                items = item_formset.save(commit=False)
                for item in items:
                    item.slip = slip
                    item.save()
                for obj in item_formset.deleted_objects: obj.delete()
            
            # --- LƯU ẢNH ---
            files = request.FILES.getlist('photos')
            for f in files:
                ExportImage.objects.create(slip=slip, image=f)

            messages.success(request, f"Đã tạo phiếu xuất kho #{slip.id:04d} thành công!")
            return redirect('export_detail', pk=slip.id)
    else:
        form = ExportSlipForm()
        item_formset = ExportItemFormSet()
    
    return render(request, 'warehouse/create_export.html', {'form': form, 'item_formset': item_formset})

# 2. SỬA PHIẾU XUẤT
@login_required
def edit_export(request, pk):
    slip = get_object_or_404(ExportSlip, pk=pk)
    
    # Chỉ cho sửa khi Nháp hoặc Từ chối
    if slip.status not in ['draft', 'rejected']:
        messages.error(request, "Chỉ được sửa phiếu khi ở trạng thái Nháp hoặc Bị từ chối.")
        return redirect('export_detail', pk=pk)

    if request.method == 'POST':
        form = ExportSlipForm(request.POST, request.FILES, instance=slip)
        item_formset = ExportItemFormSet(request.POST, instance=slip)

        if form.is_valid():
            slip = form.save(commit=False)
            # Nếu đang bị từ chối -> Reset về nháp để gửi lại
            if slip.status == 'rejected': 
                slip.status = 'draft'
            slip.save()
            
            ExportHistory.objects.create(slip=slip, user=request.user, action="Cập nhật phiếu")

            # Import Excel thêm (nếu có)
            excel_file = request.FILES.get('excel_file')
            if excel_file:
                try:
                    df = pd.read_excel(excel_file)
                    df.columns = df.columns.str.strip().str.lower()
                    def find_col(df, keywords):
                        for col in df.columns:
                            if all(k in col for k in keywords): return col
                        return None
                    
                    for index, row in df.iterrows():
                        col_ten = find_col(df, ['tên']) 
                        ten = row.get(col_ten)
                        if pd.isna(ten) or str(ten).strip() == '': continue
                        
                        col_dvt = find_col(df, ['đơn', 'vị']) or find_col(df, ['dvt'])
                        dvt = row.get(col_dvt) or 'Cái'
                        col_sl = find_col(df, ['số', 'lượng']) or find_col(df, ['sl'])
                        try: sl = int(row.get(col_sl)) if pd.notna(row.get(col_sl)) else 1
                        except: sl = 1
                        col_gc = find_col(df, ['ghi', 'chú'])
                        ghi_chu = row.get(col_gc) or ''

                        ExportItem.objects.create(slip=slip, ten_hang_hoa=ten, don_vi_tinh=dvt, so_luong=sl, ghi_chu=ghi_chu)
                except Exception as e:
                    messages.warning(request, f"Lỗi Excel: {e}")

            # Lưu Formset
            if item_formset.is_valid():
                items = item_formset.save(commit=False)
                for item in items:
                    item.slip = slip
                    item.save()
                for obj in item_formset.deleted_objects: obj.delete()
            
            # Xóa ảnh cũ (nếu user tích chọn xóa)
            delete_ids = request.POST.getlist('delete_ids')
            if delete_ids:
                ExportImage.objects.filter(id__in=delete_ids, slip=slip).delete()

            # Thêm ảnh mới
            files = request.FILES.getlist('photos')
            for f in files:
                ExportImage.objects.create(slip=slip, image=f)

            messages.success(request, "Cập nhật phiếu thành công!")
            return redirect('export_detail', pk=slip.id)
    else:
        form = ExportSlipForm(instance=slip)
        item_formset = ExportItemFormSet(instance=slip)
        item_formset.extra = 0 # Không hiện dòng trống khi sửa

    return render(request, 'warehouse/edit_export.html', {'form': form, 'item_formset': item_formset, 'slip': slip})

# 3. DANH SÁCH (CÓ LỌC & SẮP XẾP)
@login_required
def export_list(request):
    slips = ExportSlip.objects.all().order_by('-id')

    # --- BỘ LỌC ---
    # 1. Tìm kiếm từ khóa
    search_query = request.GET.get('q', '')
    if search_query:
        slips = slips.filter(
            Q(id__icontains=search_query) | 
            Q(nguoi_de_xuat__icontains=search_query) | 
            Q(ma_nhan_vien__icontains=search_query)
        )
    
    # 2. Trạng thái
    status = request.GET.get('status', '')
    if status:
        slips = slips.filter(status=status)

    # 3. Phòng ban
    dept = request.GET.get('dept', '')
    if dept:
        slips = slips.filter(phong_ban__icontains=dept)

    # 4. Ngày tạo
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        slips = slips.filter(ngay_tao__date__gte=date_from)
    if date_to:
        slips = slips.filter(ngay_tao__date__lte=date_to)

    context = {
        'slips': slips,
        'status_choices': ExportSlip.STATUS_CHOICES,
        'current_search': search_query,
        'current_status': status,
        'current_dept': dept,
        'current_date_from': date_from,
        'current_date_to': date_to,
    }
    return render(request, 'warehouse/export_list.html', context)

# 4. CHI TIẾT
@login_required
def export_detail(request, pk):
    slip = get_object_or_404(ExportSlip, pk=pk)
    return render(request, 'warehouse/export_detail.html', {'slip': slip})

# 5. XỬ LÝ DUYỆT (ACTION)
@login_required
def export_action(request, pk, action):
    slip = get_object_or_404(ExportSlip, pk=pk)
    user = request.user
    note = request.POST.get('note', '')
    
    def check_perm(group): return user.groups.filter(name=group).exists() or user.is_superuser
    
    history_action = ""
    mail_subject = ""
    mail_message = ""
    mail_recipients = []

    # BƯỚC 1: Gửi duyệt (Nhân viên -> Trưởng phòng)
    if action == 'send':
        if slip.status not in ['draft', 'rejected']: return redirect('export_detail', pk=pk)
        slip.status = 'dept_pending'
        slip.ngay_gui = timezone.now()
        history_action = "Gửi yêu cầu duyệt"
        
        mail_subject = f"[DUYỆT XUẤT] Phiếu #{slip.id:04d} chờ Trưởng phòng duyệt"
        mail_message = f"Nhân viên {slip.nguoi_de_xuat} gửi yêu cầu xuất kho.\nLý do: {slip.ly_do}"
        users = User.objects.filter(groups__name='TruongPhong')
        mail_recipients = [u.email for u in users if u.email]

    # BƯỚC 2: Trưởng phòng duyệt (TP -> Thủ kho)
    elif action == 'dept_approve':
        if not check_perm('TruongPhong'):
            messages.error(request, "Cần quyền Trưởng phòng!")
            return redirect('export_detail', pk=pk)
        
        slip.status = 'warehouse_pending'
        slip.user_truong_phong = user
        slip.ngay_truong_phong_duyet = timezone.now()
        history_action = "Trưởng phòng đã duyệt"
        
        mail_subject = f"[DUYỆT XUẤT] Phiếu #{slip.id:04d} chờ Thủ kho kiểm tra"
        mail_message = f"Trưởng phòng đã duyệt phiếu #{slip.id:04d}.\nMời Thủ kho kiểm tra hàng hóa."
        users = User.objects.filter(groups__name='ThuKho')
        mail_recipients = [u.email for u in users if u.email]

    # BƯỚC 3: Thủ kho duyệt (TK -> Giám đốc)
    elif action == 'warehouse_approve':
        if not check_perm('ThuKho'):
            messages.error(request, "Cần quyền Thủ kho!")
            return redirect('export_detail', pk=pk)
            
        slip.status = 'director_pending'
        slip.user_thu_kho = user
        slip.ngay_thu_kho_duyet = timezone.now()
        history_action = "Thủ kho đã duyệt (Đủ hàng)"
        
        mail_subject = f"[DUYỆT XUẤT] Phiếu #{slip.id:04d} chờ Giám đốc duyệt"
        mail_message = f"Thủ kho xác nhận đủ hàng cho phiếu #{slip.id:04d}.\nMời Giám đốc phê duyệt."
        users = User.objects.filter(groups__name='GiamDoc')
        mail_recipients = [u.email for u in users if u.email]

    # BƯỚC 4: Giám đốc duyệt (GĐ -> Hoàn tất)
    elif action == 'director_approve':
        if not check_perm('GiamDoc'):
            messages.error(request, "Cần quyền Giám đốc!")
            return redirect('export_detail', pk=pk)
            
        slip.status = 'completed'
        slip.user_giam_doc = user
        slip.ngay_giam_doc_duyet = timezone.now()
        history_action = "Giám đốc đã duyệt (Hoàn tất)"
        
        mail_subject = f"[THÀNH CÔNG] Phiếu xuất #{slip.id:04d} đã được duyệt"
        mail_message = f"Phiếu xuất kho của bạn đã được phê duyệt đầy đủ các cấp."
        if slip.created_by and slip.created_by.email:
            mail_recipients = [slip.created_by.email]

    # TỪ CHỐI
    elif action == 'reject':
        # Cho phép TP, TK, GĐ từ chối
        if not (check_perm('TruongPhong') or check_perm('ThuKho') or check_perm('GiamDoc')):
            messages.error(request, "Bạn không có quyền từ chối!")
            return redirect('export_detail', pk=pk)
            
        slip.status = 'rejected'
        slip.ngay_tu_choi = timezone.now()
        history_action = f"Từ chối bởi {user.last_name} {user.first_name}"
        
        mail_subject = f"[TỪ CHỐI] Phiếu xuất #{slip.id:04d} bị từ chối"
        mail_message = f"Phiếu xuất kho đã bị từ chối.\nLý do: {note if note else 'Không có'}"
        if slip.created_by and slip.created_by.email:
            mail_recipients = [slip.created_by.email]

    # LƯU & GHI LOG & GỬI MAIL
    slip.save()
    if history_action:
        ExportHistory.objects.create(slip=slip, user=user, action=history_action, note=note)
    
    if mail_recipients:
        try:
            send_export_email(request, slip, mail_subject, mail_message, mail_recipients)
        except Exception as e:
            print(f"Lỗi gửi mail export: {e}")
    
    messages.success(request, f"Đã cập nhật trạng thái: {slip.get_status_display()}")
    return redirect('export_detail', pk=pk)

# 6. XUẤT PDF
def export_export_pdf(request, pk):
    slip = get_object_or_404(ExportSlip, pk=pk)
    try:
        html_string = render_to_string('warehouse/pdf/export_template.html', {
            'slip': slip, 
            'items': slip.items.all(), 
            'request': request
        })
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename=phieu_xuat_{pk}.pdf'
        HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)
        return response
    except Exception as e:
        messages.error(request, f"Lỗi tạo PDF: {e}")
        return redirect('export_detail', pk=pk)

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
            common_return_date = form.cleaned_data.get('ngay_tra_chung')
            # --- 1. GHI NHẬT KÝ ---
            LoanHistory.objects.create(
                loan=loan, user=request.user, action="Tạo mới", note=f"Lý do: {loan.ly_do}"
            )

            # ==========================================
            # 1. XỬ LÝ IMPORT EXCEL (GỌN NHẸ - KHÔNG CẦN NGÀY THÁNG)
            # ==========================================
            excel_file = request.FILES.get('excel_file')
            if excel_file:
                try:
                    df = pd.read_excel(excel_file)
                    df.columns = df.columns.str.strip().str.lower()
                    
                    # Hàm tìm tên cột linh hoạt
                    def find_column(df, keywords):
                        for col in df.columns:
                            if all(key in col for key in keywords): return col
                        return None

                    for index, row in df.iterrows():
                        # 1. Tên tài sản
                        col_ten = find_column(df, ['tên']) 
                        ten = row.get(col_ten) if col_ten else None
                        if pd.isna(ten) or str(ten).strip() == '': continue

                        # 2. ĐVT & SL
                        col_dvt = find_column(df, ['đơn', 'vị']) or find_column(df, ['dvt'])
                        dvt = row.get(col_dvt) if col_dvt else 'Cái'

                        col_sl = find_column(df, ['số', 'lượng']) or find_column(df, ['sl'])
                        sl = row.get(col_sl) if col_sl else 1
                        try: sl = int(sl)
                        except: sl = 1

                        # --- ĐÃ XÓA BỎ ĐOẠN XỬ LÝ NGÀY THÁNG Ở ĐÂY ---

                        # 3. Tình trạng
                        col_tt = find_column(df, ['tình', 'trạng'])
                        raw_status = row.get(col_tt) if col_tt else None
                        
                        db_status = 'binh_thuong'
                        db_status_other = ''
                        if pd.notna(raw_status):
                            txt = str(raw_status).lower()
                            # Ưu tiên Bình thường
                            if any(k in txt for k in ['bình thường', 'tốt', 'mới', 'ok']):
                                db_status = 'binh_thuong'
                            # Check Hư hỏng
                            elif any(k in txt for k in ['hư', 'hỏng', 'lỗi', 'vỡ']):
                                db_status = 'hu_hong'
                            # Còn lại là Khác
                            else:
                                db_status = 'khac'; db_status_other = str(raw_status).strip()

                        # 4. Ghi chú
                        col_gc = find_column(df, ['ghi', 'chú'])
                        ghi_chu = row.get(col_gc) if col_gc else ''

                        # TẠO DÒNG DỮ LIỆU (KHÔNG TRUYỀN NGÀY VÀO ITEM NỮA)
                        LoanItem.objects.create(
                            loan=loan,
                            ten_tai_san=ten,
                            don_vi_tinh=dvt,
                            so_luong=sl,
                            # ngay_muon=... (ĐÃ XÓA)
                            # ngay_tra=...  (ĐÃ XÓA)
                            tinh_trang=db_status,
                            tinh_trang_khac=db_status_other,
                            ghi_chu=ghi_chu
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

            # ==========================================
            # 1. XỬ LÝ IMPORT EXCEL (GỌN NHẸ - KHÔNG CẦN NGÀY THÁNG)
            # ==========================================
            excel_file = request.FILES.get('excel_file')
            if excel_file:
                try:
                    df = pd.read_excel(excel_file)
                    df.columns = df.columns.str.strip().str.lower()
                    
                    # Hàm tìm tên cột linh hoạt
                    def find_column(df, keywords):
                        for col in df.columns:
                            if all(key in col for key in keywords): return col
                        return None

                    for index, row in df.iterrows():
                        # 1. Tên tài sản
                        col_ten = find_column(df, ['tên']) 
                        ten = row.get(col_ten) if col_ten else None
                        if pd.isna(ten) or str(ten).strip() == '': continue

                        # 2. ĐVT & SL
                        col_dvt = find_column(df, ['đơn', 'vị']) or find_column(df, ['dvt'])
                        dvt = row.get(col_dvt) if col_dvt else 'Cái'

                        col_sl = find_column(df, ['số', 'lượng']) or find_column(df, ['sl'])
                        sl = row.get(col_sl) if col_sl else 1
                        try: sl = int(sl)
                        except: sl = 1

                        # --- ĐÃ XÓA BỎ ĐOẠN XỬ LÝ NGÀY THÁNG Ở ĐÂY ---

                        # 3. Tình trạng
                        col_tt = find_column(df, ['tình', 'trạng'])
                        raw_status = row.get(col_tt) if col_tt else None
                        
                        db_status = 'binh_thuong'
                        db_status_other = ''
                        if pd.notna(raw_status):
                            txt = str(raw_status).lower()
                            # Ưu tiên Bình thường
                            if any(k in txt for k in ['bình thường', 'tốt', 'mới', 'ok']):
                                db_status = 'binh_thuong'
                            # Check Hư hỏng
                            elif any(k in txt for k in ['hư', 'hỏng', 'lỗi', 'vỡ']):
                                db_status = 'hu_hong'
                            # Còn lại là Khác
                            else:
                                db_status = 'khac'; db_status_other = str(raw_status).strip()

                        # 4. Ghi chú
                        col_gc = find_column(df, ['ghi', 'chú'])
                        ghi_chu = row.get(col_gc) if col_gc else ''

                        # TẠO DÒNG DỮ LIỆU (KHÔNG TRUYỀN NGÀY VÀO ITEM NỮA)
                        LoanItem.objects.create(
                            loan=loan,
                            ten_tai_san=ten,
                            don_vi_tinh=dvt,
                            so_luong=sl,
                            # ngay_muon=... (ĐÃ XÓA)
                            # ngay_tra=...  (ĐÃ XÓA)
                            tinh_trang=db_status,
                            tinh_trang_khac=db_status_other,
                            ghi_chu=ghi_chu
                        )
                except Exception as e:
                    messages.warning(request, f"Lỗi Excel: {e}")
            
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
    # 1. Lấy danh sách gốc (Sắp xếp mới nhất trước)
    loans = LoanSlip.objects.all().order_by('-id')

    # 2. --- XỬ LÝ BỘ LỌC ---
    
    # A. Tìm kiếm từ khóa
    search_query = request.GET.get('q', '')
    if search_query:
        loans = loans.filter(
            Q(id__icontains=search_query) |
            Q(nguoi_muon__icontains=search_query) |
            Q(ma_nhan_vien__icontains=search_query)
        )

    # B. Lọc theo Trạng thái
    status_filter = request.GET.get('status', '')
    if status_filter:
        loans = loans.filter(status=status_filter)

    # C. Lọc theo Phòng ban
    dept_filter = request.GET.get('dept', '')
    if dept_filter:
        loans = loans.filter(phong_ban__icontains=dept_filter)

    # D. LỌC THEO NGÀY TẠO (CẬP NHẬT MỚI)
    date_from = request.GET.get('date_from') # Từ ngày
    date_to = request.GET.get('date_to')     # Đến ngày

    if date_from:
        # __date__gte: Lớn hơn hoặc bằng ngày này
        loans = loans.filter(ngay_tao__date__gte=date_from)
    
    if date_to:
        # __date__lte: Nhỏ hơn hoặc bằng ngày này
        loans = loans.filter(ngay_tao__date__lte=date_to)

    # 3. Xử lý Sắp xếp (Giữ nguyên code cũ)
    sort_by = request.GET.get('sort', '-id')
    valid_sort_fields = ['id', 'nguoi_muon', 'phong_ban', 'ngay_tao', 'ngay_tra_du_kien', 'status']
    clean_sort = sort_by.lstrip('-')
    if clean_sort in valid_sort_fields:
        loans = loans.order_by(sort_by)

    # 4. Context
    context = {
        'loans': loans,
        'status_choices': LoanSlip.STATUS_CHOICES,
        # Trả lại giá trị đã nhập để hiển thị trên ô input
        'current_status': status_filter,
        'current_search': search_query,
        'current_dept': dept_filter,
        'current_date_from': date_from,
        'current_date_to': date_to,
        'current_sort': sort_by
    }
    return render(request, 'warehouse/loan_list.html', context)

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
        history_action = f"Từ chối"
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

# 1. TẠO PHIẾU MUA
# warehouse/views.py

@login_required
def create_purchase(request):
    if request.method == 'POST':
        form = PurchaseSlipForm(request.POST, request.FILES)
        item_formset = PurchaseItemFormSet(request.POST)

        if form.is_valid():
            slip = form.save(commit=False)
            slip.created_by = request.user
            slip.save()

            # 1. GHI NHẬT KÝ
            PurchaseHistory.objects.create(
                slip=slip, user=request.user, action="Tạo mới", note=f"Lý do: {slip.ly_do}"
            )

            # 2. XỬ LÝ IMPORT EXCEL
            excel_file = request.FILES.get('excel_file')
            if excel_file:
                try:
                    df = pd.read_excel(excel_file)
                    df.columns = df.columns.str.strip().str.lower()
                    
                    # Hàm tìm cột
                    def find_col(df, keywords):
                        for col in df.columns:
                            if all(key in col for key in keywords): return col
                        return None

                    for index, row in df.iterrows():
                        # Tìm tên hàng
                        col_ten = find_col(df, ['tên']) 
                        ten = row.get(col_ten) if col_ten else None
                        if pd.isna(ten) or str(ten).strip() == '': continue

                        # ĐVT & SL
                        col_dvt = find_col(df, ['đơn', 'vị', 'tính']) or find_col(df, ['dvt'])
                        dvt = row.get(col_dvt) if col_dvt else 'Cái'

                        col_sl = find_col(df, ['số', 'lượng']) or find_col(df, ['sl'])
                        sl = row.get(col_sl) if col_sl else 1
                        try: sl = int(sl)
                        except: sl = 1

                        col_gc = find_col(df, ['ghi', 'chú'])
                        ghi_chu = row.get(col_gc) if col_gc else ''

                        PurchaseItem.objects.create(
                            slip=slip,
                            ten_hang_hoa=ten,
                            don_vi_tinh=dvt,
                            so_luong=sl,
                            ghi_chu=ghi_chu
                        )
                except Exception as e:
                    messages.warning(request, f"Lỗi Excel: {e}")

            # 3. LƯU FORMSET
            if item_formset.is_valid():
                items = item_formset.save(commit=False)
                for item in items:
                    item.slip = slip
                    item.save()
                for obj in item_formset.deleted_objects: obj.delete()

            # 4. LƯU ẢNH
            files = request.FILES.getlist('photos')
            for f in files:
                PurchaseImage.objects.create(slip=slip, image=f)

            detail_url = reverse('purchase_detail', args=[slip.id])
            
            # Tạo nội dung HTML cho thông báo
            # class 'alert-link' của Bootstrap giúp link đậm và đẹp hơn trong khung thông báo
            msg_html = f"""
                Đã tạo phiếu <b>#{slip.id}</b> thành công! 
                <a href="{detail_url}" class="alert-link text-decoration-underline">
                    Bấm vào đây để xem chi tiết
                </a>
            """
            messages.success(request, mark_safe(msg_html))            
            return redirect('create_purchase') # Hoặc purchase_detail
    else:
        form = PurchaseSlipForm()
        item_formset = PurchaseItemFormSet()

    return render(request, 'warehouse/create_purchase.html', {'form': form, 'item_formset': item_formset})

# 2. CHI TIẾT & DUYỆT
@login_required
def purchase_detail(request, pk):
    slip = get_object_or_404(PurchaseSlip, pk=pk)
    return render(request, 'warehouse/purchase_detail.html', {'slip': slip})

@login_required
def edit_purchase(request, pk):
    slip = get_object_or_404(PurchaseSlip, pk=pk)

    # 1. Kiểm tra quyền sửa
    if slip.status not in ['draft', 'rejected']:
        messages.error(request, "Chỉ có thể sửa phiếu khi ở trạng thái Nháp hoặc Bị từ chối.")
        return redirect('purchase_detail', pk=pk)

    if request.method == 'POST':
        form = PurchaseSlipForm(request.POST, request.FILES, instance=slip)
        item_formset = PurchaseItemFormSet(request.POST, instance=slip)

        if form.is_valid():
            slip = form.save(commit=False)
            # Nếu đang bị từ chối -> Chuyển về nháp để gửi lại
            if slip.status == 'rejected':
                slip.status = 'draft'
            slip.save()

            # 2. Ghi Nhật Ký
            PurchaseHistory.objects.create(
                slip=slip, user=request.user, action="Cập nhật phiếu", note="Chỉnh sửa thông tin mua hàng"
            )

            # 3. XỬ LÝ IMPORT EXCEL
            excel_file = request.FILES.get('excel_file')
            if excel_file:
                try:
                    df = pd.read_excel(excel_file)
                    df.columns = df.columns.str.strip().str.lower()
                    
                    def find_col(df, keys):
                        for c in df.columns:
                            if all(k in c for k in keys): return c
                        return None

                    for index, row in df.iterrows():
                        # Tên hàng
                        col_ten = find_col(df, ['tên']) 
                        ten = row.get(col_ten)
                        if pd.isna(ten) or str(ten).strip() == '': continue

                        # ĐVT & SL
                        col_dvt = find_col(df, ['đơn', 'vị', 'tính']) or find_col(df, ['dvt'])
                        dvt = row.get(col_dvt) or 'Cái'

                        col_sl = find_col(df, ['số', 'lượng']) or find_col(df, ['sl'])
                        sl = row.get(col_sl) or 1
                        try: sl = int(sl)
                        except: sl = 1

                        col_gc = find_col(df, ['ghi', 'chú'])
                        ghi_chu = row.get(col_gc) or ''

                        PurchaseItem.objects.create(
                            slip=slip, ten_hang_hoa=ten, don_vi_tinh=dvt, so_luong=sl, ghi_chu=ghi_chu
                        )
                except Exception as e:
                    messages.warning(request, f"Lỗi Excel: {e}")

            # 4. Xử lý Formset (Lưu sửa / Xóa dòng)
            if item_formset.is_valid():
                items = item_formset.save(commit=False)
                for item in items:
                    item.slip = slip
                    item.save()
                for obj in item_formset.deleted_objects:
                    obj.delete()

            # 5. Xóa ảnh cũ
            delete_ids = request.POST.getlist('delete_ids')
            if delete_ids:
                PurchaseImage.objects.filter(id__in=delete_ids, slip=slip).delete()

            # 6. Thêm ảnh mới
            files = request.FILES.getlist('photos')
            for f in files:
                PurchaseImage.objects.create(slip=slip, image=f)

            messages.success(request, "Đã cập nhật phiếu mua hàng thành công!")
            return redirect('purchase_detail', pk=slip.id)
    else:
        form = PurchaseSlipForm(instance=slip)
        item_formset = PurchaseItemFormSet(instance=slip)
        item_formset.extra = 0 # Không hiện dòng trống khi sửa

    return render(request, 'warehouse/edit_purchase.html', {
        'form': form, 
        'item_formset': item_formset, 
        'loan': slip # Để dùng chung template logic ảnh cũ nếu cần (hoặc đổi tên biến trong template)
    })

@login_required
def purchase_action(request, pk, action):
    slip = get_object_or_404(PurchaseSlip, pk=pk)
    user = request.user
    note = request.POST.get('note', '') 
    
    def check_perm(group_name): 
        return user.groups.filter(name=group_name).exists() or user.is_superuser

    history_action = ""
    mail_subject = ""
    mail_message = ""
    mail_recipients = []

    # --- 1. GỬI DUYỆT ---
    if action == 'send':
        if slip.status not in ['draft', 'rejected']:
            messages.error(request, "Trạng thái không hợp lệ.")
            return redirect('purchase_detail', pk=pk)
            
        slip.status = 'dept_pending'
        slip.ngay_gui = timezone.now()
        history_action = "Gửi yêu cầu duyệt"
        
        mail_subject = f"[DUYỆT MUA] Phiếu #{slip.id:04d} chờ Trưởng phòng duyệt"
        mail_message = f"Chào Trưởng phòng,\nNhân viên {slip.nguoi_de_xuat} vừa gửi yêu cầu mua hàng.\nLý do: {slip.ly_do}"
        
        users = User.objects.filter(groups__name='TruongPhong')
        mail_recipients = [u.email for u in users if u.email]

    # --- 2. TRƯỞNG PHÒNG DUYỆT ---
    elif action == 'dept_approve':
        if not check_perm('TruongPhong'):
            messages.error(request, "Bạn không có quyền Trưởng phòng!")
            return redirect('purchase_detail', pk=pk)
            
        slip.status = 'director_pending'
        slip.user_phu_trach = user
        slip.ngay_phu_trach_duyet = timezone.now()
        history_action = "Trưởng phòng đã duyệt"
        
        mail_subject = f"[DUYỆT MUA] Phiếu #{slip.id:04d} chờ Giám đốc duyệt"
        mail_message = f"Chào Giám đốc,\nTrưởng phòng {user.last_name} {user.first_name} đã duyệt phiếu mua hàng #{slip.id:04d}.\nXin vui lòng phê duyệt cuối."
        
        users = User.objects.filter(groups__name='GiamDoc')
        mail_recipients = [u.email for u in users if u.email]

    # --- 3. GIÁM ĐỐC DUYỆT ---
    elif action == 'director_approve':
        if not check_perm('GiamDoc'):
            messages.error(request, "Bạn không có quyền Giám đốc!")
            return redirect('purchase_detail', pk=pk)
            
        slip.status = 'approved'
        slip.user_giam_doc = user
        slip.ngay_giam_doc_duyet = timezone.now()
        history_action = "Giám đốc đã duyệt (Hoàn tất)"
        
        mail_subject = f"[THÀNH CÔNG] Phiếu mua #{slip.id:04d} đã được duyệt"
        mail_message = f"Xin chúc mừng {slip.nguoi_de_xuat},\nYêu cầu mua hàng của bạn đã được Ban Giám Đốc phê duyệt."
        
        if slip.created_by and slip.created_by.email:
            mail_recipients = [slip.created_by.email]

    # --- 4. TỪ CHỐI ---
    elif action == 'reject':
        if not (check_perm('TruongPhong') or check_perm('GiamDoc')):
            messages.error(request, "Bạn không có quyền từ chối!")
            return redirect('purchase_detail', pk=pk)
            
        slip.status = 'rejected'
        slip.ngay_tu_choi = timezone.now()
        history_action = f"Đã từ chối bởi {user.last_name} {user.first_name}"
        
        mail_subject = f"[TỪ CHỐI] Phiếu mua #{slip.id:04d} bị từ chối"
        mail_message = f"Chào {slip.nguoi_de_xuat},\nRất tiếc, phiếu #{slip.id:04d} đã bị từ chối.\nLý do/Ghi chú: {note if note else 'Không có'}"
        
        if slip.created_by and slip.created_by.email:
            mail_recipients = [slip.created_by.email]

    # === LƯU & LOG & GỬI MAIL ===
    slip.save()
    
    if history_action:
        PurchaseHistory.objects.create(slip=slip, user=user, action=history_action, note=note)

    if mail_recipients:
        # Gọi hàm từ utils.py
        send_purchase_email(request, slip, mail_subject, mail_message, mail_recipients)

    messages.success(request, f"Đã cập nhật trạng thái: {slip.get_status_display()}")
    return redirect('purchase_detail', pk=pk)

# --- VIEW DANH SÁCH PHIẾU MUA ---
@login_required
def purchase_list(request):
    # Lấy tất cả phiếu mua, mới nhất lên đầu
    slips = PurchaseSlip.objects.all().order_by('-id')
    return render(request, 'warehouse/purchase_list.html', {'slips': slips})
    
# 3. XUẤT PDF
def export_purchase_pdf(request, pk):
    slip = get_object_or_404(PurchaseSlip, pk=pk)
    html_string = render_to_string('warehouse/pdf/purchase_template.html', {
        'slip': slip, 'items': slip.items.all(), 'request': request
    })
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename=phieu_mua_{pk}.pdf'
    HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)
    return response
