from django.core.management.base import BaseCommand
from django.utils import timezone
from warehouse.models import LoanSlip
from django.core.mail import send_mail

class Command(BaseCommand):
    help = 'Gửi mail nhắc trả hàng lúc 9h sáng'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()
        # Tìm phiếu đến hạn hôm nay và chưa trả
        due_loans = LoanSlip.objects.filter(
            ngay_tra_du_kien=today, 
            status='borrowing'
        )

        for loan in due_loans:
            # Gửi mail (Cấu hình mail trong settings.py sau)
            print(f"Gửi mail nhắc cho: {loan.email}")
            # send_mail(...)
            
        self.stdout.write(f"Đã kiểm tra và nhắc nhở {due_loans.count()} phiếu.")