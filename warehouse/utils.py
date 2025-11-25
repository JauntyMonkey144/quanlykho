from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.conf import settings
from weasyprint import HTML
from django.contrib.auth.models import User, Group
from django.urls import reverse # <--- Import thêm
# --- HÀM MỚI: LẤY EMAIL CỦA MỘT NHÓM ---
def get_emails_by_group(group_name):
    """
    Trả về danh sách email của tất cả user thuộc nhóm group_name
    """
    users = User.objects.filter(groups__name=group_name)
    emails = [u.email for u in users if u.email]
    return emails


def send_loan_email(request, loan, subject, message, recipients):
    """
    Gửi email đính kèm PDF và Link duyệt
    """
    # 1. Tạo Link chi tiết phiếu
    # build_absolute_uri sẽ tự động lấy domain (localhost hoặc railway)
    relative_link = reverse('loan_detail', args=[loan.id])
    full_link = request.build_absolute_uri(relative_link)

    # 2. Bổ sung Link vào nội dung thư
    full_message = f"{message}\n\n👉 Bấm vào đây để xem chi tiết và duyệt: {full_link}"

    # 3. Tạo PDF
    html_string = render_to_string('warehouse/pdf/loan_template.html', {
        'loan': loan,
        'items': loan.items.all(),
        'request': request
    })
    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()

    # 4. Gửi Email
    if not recipients:
        print("⚠️ Không có người nhận email!")
        return False

    email = EmailMessage(
        subject=subject,
        body=full_message, # Dùng nội dung đã có link
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
    )
    
    # Đính kèm PDF
    filename = f"Phieu_Muon_{loan.id}.pdf"
    email.attach(filename, pdf_file, 'application/pdf')

    try:
        email.send()
        print(f"✅ Đã gửi email tới: {recipients}")
        return True
    except Exception as e:
        print(f"❌ Lỗi gửi mail: {e}")
        return False