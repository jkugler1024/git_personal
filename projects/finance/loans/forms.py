from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Row, Column
from .models import Loan, LoanCalc, PaymentVariation, LoanRoll
    
#Desired self checking for this form
    #no overlapping pmt_variation ranges
    #first payment date must not be prior to the loan date

class LoanModelForm(forms.ModelForm):
    class Meta:
        model = Loan
        fields = ['loan_name']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('caculate_loan', 'Calculate Loan'))
        self.helper.add_input(Submit('save_loan', 'Save Loan'))
        
class LoanCalcModelForm(forms.ModelForm):
    class Meta:
        model = LoanCalc
        fields = ['loan','sequence','loan_amt','rewritten_int','loan_date','first_pmt_date','nbr_of_pmts','int_rate','int_method','pmt_frequency','allocation']
        widgets = {'loan': forms.HiddenInput(), #submitted by the view
                   'sequence': forms.HiddenInput(), #submitted by the view
                   'rewritten_int': forms.HiddenInput()} #submitted by the view
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('save_calc', 'Save Calculation'))
        
class LoanCalcModelRewriteForm(forms.ModelForm):
    class Meta:
        model = LoanCalc
        fields = ['loan','sequence','loan_amt','rewritten_int','loan_date','first_pmt_date','nbr_of_pmts','int_rate','int_method','pmt_frequency','allocation']
        widgets = {'loan': forms.HiddenInput(), #submitted by the view
                   'sequence': forms.HiddenInput(), #submitted by the view
                   'rewritten_int': forms.HiddenInput(), #submitted by the view
                   'loan_amt': forms.HiddenInput()} #submitted by the view
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('save_calc', 'Save Calculation'))

class PaymentVariationModelForm(forms.ModelForm):
    class Meta:
        model = PaymentVariation
        fields = ['loan_calc','pmt_nbr_from','pmt_nbr_to','variation_type','variation_value']
        widgets = {'loan_calc': forms.HiddenInput()}
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('save_var', 'Save Variation'))
        
class LoanRollModelForm(forms.ModelForm):
    class Meta:
        model = LoanRoll
        fields = ['loan','loan_balance_type','roll_year','roll_month'] 
        widgets = {'loan': forms.HiddenInput(),
                   'roll_year': forms.HiddenInput(),
                   'roll_month': forms.HiddenInput(),
                   }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('run_qry', 'Run Report'))