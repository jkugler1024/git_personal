from django.db import models
import numpy_financial as npf
import pandas as pd
import datetime
import calendar
#from . import amortizing_support as ams #when tests.py imports models.py: ImportError: attempted relative import with no known parent package
#import amortizing_support as ams

class Frequency(models.Model):
    frequency_name = models.CharField(max_length=30)
    months = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return self.frequency_name

class InterestMethod(models.Model):
    interest_method_name = models.CharField(max_length=30)
    month_counting = models.CharField(max_length=30)
    year_counting = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return self.month_counting + '/' + self.year_counting

class Allocation(models.Model):
    allocation_name = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return self.allocation_name
    
class Loan(models.Model):
    loan_name = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return self.loan_name

class LoanCalc(models.Model):
    loan = models.ForeignKey('Loan', on_delete=models.CASCADE)
    sequence = models.IntegerField()
    loan_amt = models.FloatField()
    rewritten_int = models.FloatField()
    loan_date = models.DateField()
    first_pmt_date = models.DateField()
    nbr_of_pmts = models.IntegerField()
    int_rate = models.FloatField()
    int_method = models.ForeignKey('InterestMethod', on_delete=models.CASCADE)
    pmt_frequency = models.ForeignKey('Frequency', on_delete=models.CASCADE)
    allocation = models.ForeignKey('Allocation', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.loan} - {self.sequence}"
    
    @property
    def multiplier(self):
        return self.pmt_frequency.months
    
    @property
    def pmt_variations(self):
        return PaymentVariation.objects.filter(loan_calc=self).values()
    
    @property
    def int_method_digit(self):
        return self.int_method.id
    
    @property
    def allocation_digit(self):
        return self.allocation.id
    
    def amortize(self):
        print('amortize called')
        pmt_guess = -npf.pmt(self.int_rate / (12/self.multiplier),self.nbr_of_pmts, self.loan_amt, 000)
        df, offage = self.amortize_guess(pmt_guess)
        
        while offage > .005 or offage <-.005:
            pmt_guess = pmt_guess + offage/self.nbr_of_pmts*.25
            df, offage = self.amortize_guess(pmt_guess)
            
        #set instance properties related to amortization
        self.schedule = df 
        self.prin_pmts = df['prin_pmt'].sum()
        self.int_pmts = df['int_pmt'].sum()
        self.pmts = df['payment'].sum()
        self.maturity = df['pmt_date'][df.index[-1]]


    def amortize_guess(self,pmt_guess):
        column_names = ['pmt_nbr', 'pmt_date', 'payment', 'begin_prin', 'add_prin', 'prin_pmt', 'end_prin',
                           'begin_int', 'add_int', 'int_pmt', 'end_int']
        df = pd.DataFrame(columns = column_names)
         
        mydict = {}
        
        for pmt_nbr in range(1,self.nbr_of_pmts+1):
            #fill the dictionary up
            if pmt_nbr == 1:
                #pdb.set_trace()
                mydict['begin_prin'] = self.loan_amt                    
                mydict['begin_int'] = self.rewritten_int
                mydict['end_prin'] = self.loan_amt
                acc_start = self.loan_date
            else:
                mydict['begin_prin'] = mydict['end_prin']
                mydict['begin_int'] = mydict['end_int']
                acc_start = mydict['pmt_date'] + datetime.timedelta(days=1)
            
            mydict['pmt_nbr'] = pmt_nbr
            mydict['pmt_date'] = self.get_pmt_date(pmt_nbr-1)
            acc_end = mydict['pmt_date']
            mydict['add_int'] = self.interest_methods(mydict['begin_prin'],acc_start,acc_end,pmt_nbr)
            
            variation = self.pmt_variation(pmt_nbr)
            if variation == None:
                mydict['payment'] = pmt_guess
            else:
                if variation['variation_type_id'] == 1:
                    mydict['payment'] = mydict['add_int']
                elif variation['variation_type_id'] == 2:
                    mydict['payment'] = variation['variation_value']
                    
            mydict['add_prin'] = 0.00
            if self.allocation_digit == 1:   
                mydict['int_pmt'] = minimum(mydict['payment'],mydict['begin_int']+mydict['add_int'])
                mydict['prin_pmt'] = minimum(mydict['payment']-mydict['int_pmt'],mydict['end_prin'])
            else:
                mydict['prin_pmt'] = minimum(mydict['payment'],mydict['begin_prin']+mydict['add_prin'])
                mydict['int_pmt'] = minimum(mydict['payment']-mydict['prin_pmt'],mydict['begin_int']+mydict['add_int'])
            mydict['payment'] = mydict['int_pmt']+mydict['prin_pmt']
            mydict['end_int'] = mydict['begin_int'] + mydict['add_int'] - mydict['int_pmt']
            mydict['end_prin'] = mydict['begin_prin'] + mydict['add_prin'] - mydict['prin_pmt']
            
            df = df.append(mydict, ignore_index=True)
    
        offage = mydict['payment'] - pmt_guess + mydict['end_int'] + mydict['end_prin']
    
        return df, offage
    
    def pmt_variation(self,pmt_nbr):
        #pdb.set_trace()
        if self.pmt_variations == None:
            return None
        
        for variation in self.pmt_variations:
            if variation['pmt_nbr_from'] <= pmt_nbr <= variation['pmt_nbr_to']:
                return variation
        
        return None

    def get_pmt_date(self,interval):
        months = interval*self.multiplier
        
        mydate = self.add_months(months)
        
        return mydate
    
    def add_months(self,months):
        month = self.first_pmt_date.month - 1 + months
        year = self.first_pmt_date.year + month // 12
        month = month % 12 + 1
        if self.first_pmt_date.day == calendar.monthrange(self.first_pmt_date.year,self.first_pmt_date.month)[1]: #asking if the first pmt date is a month end - if so, other due dates should be month end as well
            day = calendar.monthrange(year,month)[1]
        else:
            day = min(self.first_pmt_date.day, calendar.monthrange(year,month)[1])
        
        return datetime.date(year, month, day)
    
    def interest_methods(self,begin_prin,acc_start,acc_end,pmt_nbr):
        month_counting = self.int_method.month_counting
        year_counting = self.int_method.year_counting
        
        if year_counting == 'actual': #otherwise, it would be pre-defined as either 360 or 365
            if calendar.isleap(acc_end.year):
                year_counting = 366
            else:
                year_counting = 365
        else:
            year_counting = int(year_counting)
        if month_counting == '30':
            if pmt_nbr == 1: #testing to see if we need to count actual days or if we have a full period - if it's pmt 1 it might not be a full month
                full_months, residual_days = accrual_range_info(acc_start,acc_end)
                months = full_months + residual_days / 30
            else:
                months = self.multiplier
            years = months*30/year_counting
            accrued_interest = begin_prin*self.int_rate*years
        else: #otherwise, month counting is actual
            delta = acc_end - acc_start
            actual_days = delta.days+1
            accrued_interest = begin_prin*self.int_rate*actual_days/year_counting
            
        return accrued_interest
    
class PaymentVariation(models.Model):
    loan_calc = models.ForeignKey('LoanCalc', on_delete=models.CASCADE)
    pmt_nbr_from = models.IntegerField()
    pmt_nbr_to = models.IntegerField()
    variation_type = models.ForeignKey('PaymentVariationType', on_delete=models.CASCADE)
    variation_value = models.FloatField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
class PaymentVariationType(models.Model):
    type_name = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return self.type_name

class CalcSched(models.Model):
    loan_calc = models.ForeignKey('LoanCalc', on_delete=models.CASCADE)
    pmt_nbr = models.IntegerField()
    pmt_date = models.DateField()
    payment = models.FloatField()
    begin_prin = models.FloatField()
    add_prin = models.FloatField()
    prin_pmt = models.FloatField()
    end_prin = models.FloatField()
    begin_int = models.FloatField()
    add_int = models.FloatField()
    int_pmt = models.FloatField()
    end_int = models.FloatField()
    
class LoanSched(models.Model):
    loan = models.ForeignKey('Loan', on_delete=models.CASCADE)
    loan_calc = models.ForeignKey('LoanCalc', on_delete=models.CASCADE)
    pmt_nbr = models.CharField(max_length=4, blank=True, null=True)
    pmt_date = models.DateField()
    payment = models.FloatField()
    begin_prin = models.FloatField()
    add_prin = models.FloatField()
    prin_pmt = models.FloatField()
    end_prin = models.FloatField()
    begin_int = models.FloatField()
    add_int = models.FloatField()
    int_pmt = models.FloatField()
    end_int = models.FloatField()
    
class LoanBalanceType(models.Model):
    type_name   = models.CharField(max_length=30)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.type_name
    
class RollTxnType(models.Model):
    type_name   = models.CharField(max_length=30)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.type_name
    
class LoanRoll(models.Model):
    loan                = models.ForeignKey('Loan', on_delete=models.CASCADE)
    loan_balance_type   = models.ForeignKey('LoanBalanceType', on_delete=models.CASCADE)
    roll_year           = models.IntegerField(blank=True)
    roll_month          = models.IntegerField(blank=True)
    begin               = models.FloatField()
    add                 = models.FloatField()
    reduce              = models.FloatField()
    end                 = models.FloatField()

class RollTransaction(models.Model):
    loan                = models.ForeignKey('Loan', on_delete=models.CASCADE)
    loansched           = models.ForeignKey('LoanSched', on_delete=models.CASCADE)
    loan_balance_type   = models.ForeignKey('LoanBalanceType', on_delete=models.CASCADE)
    roll_txn_type       = models.ForeignKey('RollTxnType', on_delete=models.CASCADE)
    txn_year            = models.IntegerField(blank=True)
    txn_month           = models.IntegerField(blank=True)
    amount              = models.FloatField()
    
    
#helper functions ----------------------------------------------------------------------------------------------------

def minimum(a, b):
      
    if a <= b:
        return a
    else:
        return b
        
def accrual_range_info(acc_start,acc_end): 
    pmt_on_me = calendar.monthrange(acc_end.year,acc_end.month)[1] == acc_end.day
    start_day_from_next_mo = calendar.monthrange(acc_start.year,acc_start.month)[1] - acc_start.day + 1 
    
    if pmt_on_me: #if end_is_me:
        if acc_start.day == 1:
            full_months = basic_month_count(acc_start,acc_end) + 1
            residual_days = 0
        else:
            full_months = basic_month_count(acc_start,acc_end)
            residual_days = start_day_from_next_mo
    else:
        day_diff = acc_start.day - acc_end.day
        if day_diff <= 1:
            full_months = basic_month_count(acc_start,acc_end)
            if day_diff == 1:
                residual_days = 0
            else:
                residual_days = 1 - day_diff
        else:
            full_months = basic_month_count(acc_start,acc_end) - 1
            residual_days = acc_end.day + start_day_from_next_mo
            
    return full_months, residual_days

def basic_month_count(acc_start,acc_end):
    count = (acc_end.year - acc_start.year)*12 + acc_end.month - acc_start.month
    
    return count