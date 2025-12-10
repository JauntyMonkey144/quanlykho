import os
import resend
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.core.mail import EmailMessage
from django.conf import settings
from weasyprint import HTML
from django.contrib.auth.models import User, Group
from django.urls import reverse # <--- Import thêm
# --- HÀM MỚI: LẤY EMAIL CỦA MỘT NHÓM ---
resend.api_key = os.environ.get('RESEND_API_KEY')

def get_emails_by_group(group_name):
    """Lấy danh sách email của nhóm"""
    users = User.objects.filter(groups__name=group_name)
    # Lưu ý: Nếu dùng gói Free, chỉ gửi được về email chính chủ đã đăng ký Resend
    return [u.email for u in users if u.email]

def send_loan_email(request, loan, subject, message, recipients):
    """
    Gửi email bằng Resend API (Nhanh hơn SMTP)
    """
    # 1. Tạo Link chi tiết
    relative_link = reverse('loan_detail', args=[loan.id])
    full_link = request.build_absolute_uri(relative_link)

    # 2. Nội dung Email (Chuyển text sang HTML đơn giản)
    # Vì API gửi HTML nên ta cần format lại dòng xuống dòng
    formatted_message = message.replace("\n", "<br>")
    html_content = f"""
    <p>{formatted_message}</p>
    <p>👉 <a href="{full_link}">Bấm vào đây để xem chi tiết và duyệt phiếu</a></p>
    <hr>
    <small>Đây là email tự động từ Hệ thống Quản lý Kho.</small>
    """

    # 3. Tạo PDF (WeasyPrint)
    html_string = render_to_string('warehouse/pdf/loan_template.html', {
        'loan': loan,
        'items': loan.items.all(),
        'request': request
    })
    # Tạo file PDF dưới dạng bytes
    pdf_bytes = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()

    # 4. Gửi qua RESEND API
    if not recipients:
        print("⚠️ Không có người nhận email!")
        return False

    params = {
        "from": "system@sun-automation.id.vn", # Bắt buộc dùng mail này nếu chưa add domain
        "to": recipients,
        "subject": subject,
        "html": html_content,
        "attachments": [
            {
                "filename": f"Phieu_Muon_{loan.id}.pdf",
                "content": list(pdf_bytes) # Resend API yêu cầu convert bytes sang list số nguyên
            }
        ]
    }

    try:
        r = resend.Emails.send(params)
        print(f"✅ Gửi mail thành công! ID: {r.get('id')}")
        return True
    except Exception as e:
        # Chỉ in lỗi, không làm sập web
        print(f"❌ Lỗi gửi mail API: {e}")
        return False


def send_purchase_email(request, slip, subject, message, recipients):
    """
    Gửi email thông báo Phiếu Mua Hàng kèm PDF qua Resend API
    (Cấu trúc giống hệt send_loan_email)
    """
    # 0. Cấu hình API Key
    resend.api_key = settings.RESEND_API_KEY

    # 1. Tạo Link chi tiết
    relative_link = reverse('purchase_detail', args=[slip.id])
    full_link = request.build_absolute_uri(relative_link)

    # 2. Nội dung Email (Format HTML)
    formatted_message = message.replace("\n", "<br>")
    html_content = f"""
    <p>{formatted_message}</p>
    <p>👉 <a href="{full_link}" style="font-weight:bold; color:#198754;">Bấm vào đây để xem chi tiết và duyệt phiếu</a></p>
    <hr>
    <small style="color: gray;">Đây là email tự động từ Hệ thống Quản lý Kho (Sun Automation).</small>
    """

    # 3. Tạo PDF (WeasyPrint) 
    # Lưu ý: Cần có file template 'warehouse/pdf/purchase_template.html'
    try:
        html_string = render_to_string('warehouse/pdf/purchase_template.html', {
            'slip': slip,
            'items': slip.items.all(),
            'request': request
        })
        pdf_bytes = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()
        has_pdf = True
    except Exception as e:
        print(f"⚠️ Lỗi tạo PDF Purchase: {e}")
        pdf_bytes = None
        has_pdf = False

    # 4. Gửi qua RESEND API
    if not recipients:
        print("⚠️ Không có người nhận email!")
        return False

    params = {
        "from": "system@sun-automation.id.vn", 
        "to": recipients,
        "subject": subject,
        "html": html_content,
        "attachments": []
    }

    # Đính kèm PDF nếu tạo thành công
    if has_pdf:
        params["attachments"].append({
            "filename": f"Phieu_Mua_{slip.id}.pdf",
            "content": list(pdf_bytes) 
        })

    try:
        r = resend.Emails.send(params)
        print(f"✅ Gửi mail Purchase thành công! ID: {r.get('id')}")
        return True
    except Exception as e:
        print(f"❌ Lỗi gửi mail API: {e}")
        return False

def send_export_email(request, slip, subject, message, recipients):
    """
    Gửi email thông báo Phiếu Xuất Kho kèm PDF
    """
    resend.api_key = settings.RESEND_API_KEY
    relative_link = reverse('export_detail', args=[slip.id])
    full_link = request.build_absolute_uri(relative_link)

    formatted_message = message.replace("\n", "<br>")
    html_content = f"""
    <p>{formatted_message}</p>
    <p>👉 <a href="{full_link}" style="font-weight:bold; color:#ffc107;">Bấm vào đây để xem chi tiết</a></p>
    <hr><small>Hệ thống Quản lý Kho - Phiếu Xuất.</small>
    """

    try:
        html_string = render_to_string('warehouse/pdf/export_template.html', {
            'slip': slip, 'items': slip.items.all(), 'request': request
        })
        pdf_bytes = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()
        has_pdf = True
    except Exception as e:
        print(f"⚠️ Lỗi PDF Export: {e}")
        pdf_bytes = None; has_pdf = False

    if not recipients: return False

    params = {
        "from": "system@sun-automation.id.vn", "to": recipients,
        "subject": subject, "html": html_content, "attachments": []
    }
    if has_pdf:
        params["attachments"].append({"filename": f"Phieu_Xuat_{slip.id}.pdf", "content": list(pdf_bytes)})

    try:
        resend.Emails.send(params)
        return True
    except Exception as e:
        print(f"❌ Lỗi gửi mail API: {e}")
        return False