from django.contrib import admin
from loans.models import Frequency, InterestMethod, Allocation, Loan, LoanCalc, PaymentVariation, PaymentVariationType,CalcSched
from loans.models import LoanSched, LoanRoll, LoanBalanceType, RollTransaction, RollTxnType


# Register your models here.
admin.site.register(Frequency)
admin.site.register(InterestMethod)
admin.site.register(Allocation)
admin.site.register(Loan)
admin.site.register(LoanCalc)
admin.site.register(PaymentVariation)
admin.site.register(PaymentVariationType)
admin.site.register(CalcSched)
admin.site.register(LoanSched)
admin.site.register(LoanRoll)
admin.site.register(LoanBalanceType)
admin.site.register(RollTxnType)
admin.site.register(RollTransaction)
