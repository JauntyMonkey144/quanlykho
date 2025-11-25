import os
import resend
from django.template.loader import render_to_string
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
        "from": "onboarding@resend.dev", # Bắt buộc dùng mail này nếu chưa add domain
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
