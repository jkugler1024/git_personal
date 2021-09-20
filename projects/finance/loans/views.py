from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from . import manual_load as ml, roll
import re
from .forms import LoanModelForm, LoanCalcModelForm, LoanCalcModelRewriteForm, PaymentVariationModelForm, LoanRollModelForm
from .models import Loan, LoanCalc, Frequency, InterestMethod, Allocation, PaymentVariation, CalcSched, LoanSched, LoanRoll, RollTransaction
import pdb
import datetime
import pandas as pd
from pandas.api.types import is_datetime64_any_dtype as is_datetime, is_integer_dtype, is_float_dtype
import xlsxwriter as xl
import io
import calendar

@login_required
def home(request):
    return render(request, 'loans/home.html')

@login_required
def loan_create_view(request):
    print(request)
    form = LoanModelForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect(loan_list_view)
    context = {
        'form': form
        }
    return render(request, 'loans/loan_create.html', context)

@login_required
def loancalc_create_view(request, loan_id=None):
    print(request.POST)
    loan = Loan.objects.get(id=loan_id)
    existing_calcs = LoanCalc.objects.filter(loan=loan).count()

    if existing_calcs >= 1: #loan already has 1+ LaonCalcs, so we need to use a different form and do some other logic
        if request.POST: #form submitted; need to populate form's hidden fields before saving to db
            prior_calc = LoanCalc.objects.get(loan=loan, sequence=existing_calcs)           
            rewrite_date = request.POST.copy()['loan_date']
            rewrite_date = datetime.datetime.strptime(rewrite_date, '%m/%d/%Y').date()
            rewritten_principal, rewritten_interest = stub_a_sched(prior_calc, rewrite_date)[1:]
            form = fill_hidden_fields(request,LoanCalcModelRewriteForm,loan=loan,sequence=existing_calcs+1, 
                                      rewritten_int=rewritten_interest, loan_amt=rewritten_principal)
            
        else: #there are existing calcs but form not yet submitted
            form = LoanCalcModelRewriteForm(None)
    else: #this is the first calc for the loan
        if request.POST: #form submitted; need to populate form's hidden fields before saving to db
            form = fill_hidden_fields(request,LoanCalcModelForm,loan=loan,sequence=existing_calcs+1, rewritten_int=0)
        else:
            form = LoanCalcModelForm(None)
    if form.is_valid():
        form.save()
        calcs = LoanCalc.objects.filter(loan=loan_id)
        calc_count = calcs.count()
        calc = calcs.get(sequence=calc_count)
        db_schedule_update(calc,loan_calc_action='create')
        
        accounting_updates(loan_id)
        
        return redirect(loan_detail_view, loan_id=loan_id)
    
    context = {
        'form': form
        }
    return render(request, 'loans/loancalc_create.html', context)

@login_required
def pmtvariation_create_view(request, calc_id=None):
    form = PaymentVariationModelForm(request.POST or None)
    if request.POST:
        post = request.POST.copy()
        post['loan_calc'] = calc_id
        form = PaymentVariationModelForm(post)
    if form.is_valid():
        form.save()
        calc = LoanCalc.objects.get(id=calc_id)
        db_schedule_update(calc, loan_calc_action='update')
        
        accounting_updates(calc.loan_id)
        
        return redirect(pmtvariation_list_view,calc_id=calc_id)
    
    context = {
        'form': form
        }
    return render(request, 'loans/payment_variation_create.html', context)

@login_required
def loan_list_view(request):
    context = {
        'loans': Loan.objects.all()
        }
    return render(request, 'loans/loan_list.html', context)

@login_required
def loancalc_list_view(request):
    calcs = LoanCalc.objects.all()
    context = {
        'calcs': calcs
        }
    return render(request, 'loans/loancalc_list.html', context)

@login_required
def pmtvariation_list_view(request, calc_id=None):
    calc = LoanCalc.objects.get(id=calc_id)
    variations = PaymentVariation.objects.filter(loan_calc=calc_id)
    context = {
        'variations': variations,
        'calc': calc,
        }
    return render(request, 'loans/pmtvariation_list.html', context)

@login_required
def loan_detail_view(request, loan_id=None):
    loan = Loan.objects.get(id=loan_id)
    calcs = LoanCalc.objects.filter(loan=loan_id).order_by('sequence')
    sched = get_df_LoanSched(loan_id)
    maturity, total_payments, total_principal, total_interest = schedule_summary_formatted(sched)
    html_tbl = htmlize_df(sched)
    context = {'loan':loan,
               'calcs':calcs,   
               'schedule':html_tbl,
               'maturity':maturity,
               'payments':total_payments,
               'principal':total_principal,
               'interest':total_interest}
    return render(request, 'loans/loan_detail.html', context)

@login_required
def loan_accounting_view(request, loan_id=None):
    form = LoanRollModelForm(request.POST or None)
    df_roll = get_df_LoanRoll(loan_id)
    html_tbl = htmlize_df(df_roll)
    loan = Loan.objects.get(id=loan_id)
    balance_type = 1 #defaulting this for sake of passing to the context
    
    if request.POST:
        post = request.POST.copy()
        balance_type = int(post['loan_balance_type']) or None
        df_roll = get_df_LoanRoll(loan_id,loan_balance_type=balance_type)
        html_tbl = htmlize_df(df_roll)
        
    context = {'loan':loan,
               'schedule':html_tbl,
               'form':form,
               'type':balance_type}
    return render(request, 'loans/loan_accounting.html', context)

@login_required
def loancalc_detail_view(request, calc_id=None):
    calc = LoanCalc.objects.get(id=calc_id)
    prev_loan_date = calc.loan_date
    loan = Loan.objects.get(id=calc.loan_id)
    nbr_variations = PaymentVariation.objects.filter(loan_calc=calc_id).count()
    sequence = calc.sequence
    if sequence > 1:
        form = LoanCalcModelRewriteForm(request.POST or None, instance=calc)
    else:
        form = LoanCalcModelForm(request.POST or None, instance=calc)
    
    sched = pd.DataFrame.from_records(CalcSched.objects.filter(loan_calc=calc_id).values())
    sched = df_drop_cols_safe(sched,['id', 'loan_calc_id'])
    
    if form.is_valid():
        loan_date = form.cleaned_data['loan_date']
        loan_date_was_updated = loan_date != prev_loan_date
        #check if we need to update beginning balances
        if form.cleaned_data['loan_date'] != prev_loan_date and sequence > 1:
            prior_calc = get_prior_calc(calc)
            rewritten_principal, rewritten_interest = stub_a_sched(prior_calc, calc.loan_date)[1:]
            form = fill_hidden_fields(request,LoanCalcModelRewriteForm,instance=calc,loan_amt=rewritten_principal,
                                      rewritten_int=rewritten_interest)
        form.save()   
        # x= need to have a way to update all subsequent loan calcs
        calc = LoanCalc.objects.get(id=calc_id) #refresh the calc object based on newly saved data
        db_schedule_update(calc, loan_calc_action='update', loan_date_was_updated=loan_date_was_updated)
        sched = pd.DataFrame.from_records(CalcSched.objects.filter(loan_calc=calc_id).values())
        sched = sched.drop(['id', 'loan_calc_id'], axis=1)
        update_all_subsequent_LoanCalcs(calc)
        
        accounting_updates(calc.loan_id)
        
    html_tbl = htmlize_df(sched)
    
    maturity, total_payments, total_principal, total_interest = schedule_summary_formatted(sched)
    
    context = {'calc':calc,
               'loan':loan,
               'nbr_variations': nbr_variations,
               'form': form,
               'schedule':html_tbl,
               'maturity':maturity,
               'payments':total_payments,
               'principal':total_principal,
               'interest':total_interest
               }
    
    return render(request, 'loans/loancalc_detail.html', context)

@login_required
def loan_update_view(request, loan_id=None):
    loan = Loan.objects.get(id=loan_id)
    form = LoanModelForm(request.POST or None, instance=loan)
    if form.is_valid():
        form.save()
        return redirect(loan_list_view)
    context = {
        'form': form
        }
    return render(request, 'loans/loan_create.html', context)

@login_required
def pmtvar_update_view(request, pmtvar_id=None):
    pmtvar = PaymentVariation.objects.get(id=pmtvar_id)
    form = PaymentVariationModelForm(request.POST or None, instance=pmtvar)
    if form.is_valid():
        form.save()
        calc = pmtvar.loan_calc
        db_schedule_update(calc,loan_calc_action='update')
        
        accounting_updates(calc.loan_id)
        
        return redirect(pmtvariation_list_view,calc_id=calc.id)
    
    context = {
        'form': form
        }
    return render(request, 'loans/payment_variation_create.html', context)
        

@login_required
def loan_delete_view(request, loan_id=None):
    loan = Loan.objects.get(id=loan_id)
    loan.delete()    
    return redirect(loan_list_view)

@login_required
def loancalc_delete_view(request, loan_id=None, calc_id=None):
    calc = LoanCalc.objects.get(id=calc_id)
    db_schedule_update(calc,loan_calc_action='delete') #schedule update needs to happen before the loan_calc instance is deleted
    calc.delete()    
    
    accounting_updates(calc.loan_id)
    
    return redirect(loan_detail_view, loan_id=loan_id)

@login_required
def pmtvar_delete_view(request, pmtvar_id=None):
    pmtvar = PaymentVariation.objects.get(id=pmtvar_id)
    calc = pmtvar.loan_calc
    pmtvar.delete()    
    db_schedule_update(calc,loan_calc_action='update') #this is not a delete action because the calc is not getting deleted
    
    accounting_updates(calc.loan_id)
    
    return redirect(pmtvariation_list_view,calc_id=calc.id)

@login_required
def xlsx(request,loan_id=None, calc_id=None):
    if loan_id != None:
        loan = Loan.objects.get(id=loan_id)
        name = loan.__str__()
        df = get_df_LoanSched(loan_id)
    else:
        calc_id != None
        loan_calc = LoanCalc.objects.get(id=calc_id)
        #loan = Loan.objects.get(id=loan_calc.loan_id)
        #name = loan.loan_name + ' - ' + loan_calc.sequence
        name = loan_calc.__str__()
        df = get_df_CalcSched(calc_id)

    output = io.BytesIO()
    workbook = xl.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet(name)
    
    #define formats
    bold_cell = workbook.add_format({'bold': True})
    date_cell = workbook.add_format({'num_format': 'yyyy-mm-dd'})
    float_cell = workbook.add_format({'num_format': '#,##0.00'})

    #write the headers
    for idx_col, col in enumerate(df.columns):
        try:
            worksheet.write(0, idx_col, col, bold_cell)
        except:
            pass
    
    #write the data
    for idx_row, row in df.iterrows():
        for idx_col, col in enumerate(df.columns):
            try:
                if is_datetime(df[col]):
                    worksheet.write(idx_row+1, idx_col, row[col], date_cell)
                elif is_float_dtype(df[col]):
                    worksheet.write(idx_row+1, idx_col, row[col], float_cell)
                else:
                    worksheet.write(idx_row+1, idx_col, row[col])
            except:
                pass
            
    worksheet.freeze_panes(1, 0)

    workbook.close()
    
    filename = 'Amortization Schedule - ' + name
    
    output.seek(0)
    response = HttpResponse(output.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response['Content-Disposition'] = "attachment; filename="+filename+".xlsx"

    return response

@login_required
def xlsx_roll(request,loan_id=None, bal_type=None):
    loan = Loan.objects.get(id=loan_id)
    name = loan.__str__()
    df = get_df_LoanRoll(loan_id,bal_type)
    if bal_type == '1':
        sheet_name = 'Principal'
    else:
        sheet_name = 'Interest'

    output = io.BytesIO()
    workbook = xl.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet(sheet_name)
    
    #define formats
    bold_cell = workbook.add_format({'bold': True})
    date_cell = workbook.add_format({'num_format': 'yyyy-mm-dd'})
    float_cell = workbook.add_format({'num_format': '#,##0.00'})

    #write the headers
    for idx_col, col in enumerate(df.columns):
        try:
            worksheet.write(0, idx_col, col, bold_cell)
        except:
            pass
    
    #write the data
    for idx_row, row in df.iterrows():
        for idx_col, col in enumerate(df.columns):
            try:
                if is_datetime(df[col]):
                    worksheet.write(idx_row+1, idx_col, row[col], date_cell)
                elif is_float_dtype(df[col]):
                    worksheet.write(idx_row+1, idx_col, row[col], float_cell)
                else:
                    worksheet.write(idx_row+1, idx_col, row[col])
            except:
                pass
            
    worksheet.freeze_panes(1, 0)

    workbook.close()
    
    filename = 'Accounting Roll - ' + name
    
    output.seek(0)
    response = HttpResponse(output.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response['Content-Disposition'] = "attachment; filename="+filename+".xlsx"

    return response

@login_required
def accounting_view(request):
    # at some point we'll update this to be the view we want
    context = {
        'loans': Loan.objects.all()
        }
    return render(request, 'loans/loan_list.html', context)

def htmlize_df(df):
    html_tbl = df.to_html(index=False, float_format='{:>,.2f}'.format, 
                             classes=['w-auto','table table-hover','table table-sm'], justify='center')
    html_tbl = re.sub(
        r'<thead([^>]*)>',
        r'<thead\1 class="thead-dark">',
        html_tbl)
    html_tbl = re.sub(
        r'<td>',
        r'<td><nobr>',
        html_tbl)
    html_tbl = re.sub(
        r'</td>',
        r'</nobr></td>',
        html_tbl)
    
    return html_tbl

def schedule_summary_formatted(sched):
    try:
        maturity = sched['pmt_date'][sched.index[-1]]
        total_payments = sched['payment'].sum()
        total_principal = sched['prin_pmt'].sum()
        total_interest = sched['int_pmt'].sum()
        
        maturity = maturity.strftime("%Y-%m-%d")
        total_payments = '{:>,.2f}'.format(total_payments)
        total_principal = '{:>,.2f}'.format(total_principal)
        total_interest = '{:>,.2f}'.format(total_interest)
    except:
        maturity = None
        total_payments = None
        total_principal = None
        total_interest = None
    
    return maturity, total_payments, total_principal, total_interest

#entirely possible that we should not be amortizing prior LoanCalc; can likely 
def db_schedule_update(loan_calc,loan_calc_action=None,loan_date_was_updated=False):
    if loan_calc_action in ['create','update']:
        #we're going to need the amoritization schedule of this loan_calc
        loan_calc.amortize()
        new_schedule = loan_calc.schedule
    else:
        new_schedule = None
    
    #always update CalcSched for the current loan_calc
    loan_calc_sched_update(loan_calc,new_schedule)
    
    #always update LoanSched for the current loan_calc
    loan_sched_update(loan_calc,new_schedule)
    
    if loan_calc_action == 'create' and loan_calc.sequence > 1:
        prior_loan_calc = get_prior_calc(loan_calc)
        new_schedule = stub_a_sched(prior_loan_calc, loan_calc.loan_date)[0]
        loan_sched_update(prior_loan_calc,new_schedule) 
        
    if loan_calc_action == 'update'  and loan_calc.sequence > 1 and loan_date_was_updated:
        prior_loan_calc = get_prior_calc(loan_calc)
        new_schedule = stub_a_sched(prior_loan_calc, loan_calc.loan_date)[0]        
        loan_sched_update(prior_loan_calc,new_schedule) 
        
    if loan_calc_action == 'delete'  and loan_calc.sequence > 1:
        prior_loan_calc = get_prior_calc(loan_calc)
        new_schedule = pd.DataFrame.from_records(CalcSched.objects.filter(loan_calc=prior_loan_calc.id).values())
        new_schedule['loan_id'] = prior_loan_calc.loan_id
        loan_sched_update(prior_loan_calc,new_schedule)
    
    #maybe we can put the call to calculate_loan_roll here

def loan_calc_sched_update(loan_calc,new_schedule=None):
    old_cs = CalcSched.objects.filter(loan_calc_id = loan_calc.id)
    old_cs.delete()
    if isinstance(new_schedule, pd.DataFrame):
        df_cs = new_schedule.copy()
        df_cs['loan_calc_id'] = loan_calc.id
        ml.LoadToLocal(df_cs,'loans_calcsched', schema='public')

def loan_sched_update(loan_calc,new_schedule):
    old_ls = LoanSched.objects.filter(loan_calc_id = loan_calc.id)
    old_ls.delete()
    if isinstance(new_schedule, pd.DataFrame):
        df_ls = new_schedule.copy()
        df_ls['loan_id'] = loan_calc.loan_id
        df_ls['loan_calc_id'] = loan_calc.id
        ml.LoadToLocal(df_ls,'loans_loansched', schema='public')
        
def loan_roll_update(loan_id,new_df):
    old_roll = LoanRoll.objects.filter(loan_id = loan_id)
    old_roll.delete()
    if isinstance(new_df, pd.DataFrame):
        new_roll = new_df.copy()
        ml.LoadToLocal(new_roll,'loans_loanroll', schema='public')

def roll_txn_update(loan_id,new_df):
    old_txns = RollTransaction.objects.filter(loan_id = loan_id)
    old_txns.delete()
    if isinstance(new_df, pd.DataFrame):
        new_roll = new_df.copy()
        new_roll['loan_id'] = loan_id
        ml.LoadToLocal(new_roll,'loans_rolltransaction', schema='public')
        
def accounting_updates(loan_id):
    #update the accounting roll and roll txns
    df_ls = pd.DataFrame.from_records(LoanSched.objects.filter(loan_id=loan_id).values())
    loan_calc = LoanCalc.objects.get(loan_id=loan_id, sequence=1)
    df_roll, df_txns = roll.calculate_loan_roll(loan_id,df_ls,loan_calc)
    loan_roll_update(loan_id,df_roll)
    roll_txn_update(loan_id,df_txns)

def df_drop_cols_safe(df,col_list):
    try:
        df = df.drop(col_list, axis=1)
    except:
        for col in col_list:
            try:
                df = df.drop(col, axis=1)
            except:
                df = df
    
    return df

def get_prior_calc(loan_calc):
    prior_calc = LoanCalc.objects.get(loan=loan_calc.loan_id, sequence=loan_calc.sequence-1)
    
    return prior_calc

def get_next_calc(loan_calc):
    next_calc = LoanCalc.objects.get(loan=loan_calc.loan_id, sequence=loan_calc.sequence+1)
    
    return next_calc

def stub_a_sched(calc_to_stub, rewrite_date):
    end_date = rewrite_date-datetime.timedelta(days=1)
    df_cs = pd.DataFrame.from_records(CalcSched.objects.filter(loan_calc_id=calc_to_stub.id).values())
    df_stub = df_cs.loc[df_cs['pmt_date'] <= end_date]
    idx = df_stub.index.max()
    myseries = df_stub.loc[idx]
    ending_prin = myseries['end_prin']
    if myseries['pmt_date'] == end_date:
        ending_int = myseries['end_int']
    else:
        acc_start_date = myseries['pmt_date']+datetime.timedelta(days=1)
        mydict = {}
        mydict['pmt_date'] = end_date
        mydict['payment'] = 0
        mydict['begin_prin'] = myseries['end_prin']
        mydict['add_prin'] = 0
        mydict['prin_pmt'] = 0
        mydict['end_prin'] = mydict['begin_prin'] + mydict['add_prin'] - mydict['prin_pmt']
        mydict['begin_int'] = myseries['end_int']
        mydict['add_int'] = calc_to_stub.interest_methods(myseries['end_prin'],acc_start_date,end_date,1) #want this to have the behavior of counting actual days
        mydict['int_pmt'] = 0
        mydict['end_int'] = mydict['begin_int'] + mydict['add_int'] - mydict['int_pmt']
        ending_int = mydict['end_int']
        df_stub = df_stub.append(mydict, ignore_index=True)
    
    df_stub = df_drop_cols_safe(df_stub,['id', 'loan_calc_id'])
    
    return df_stub, ending_prin, ending_int

def fill_hidden_fields(request,form,**kwargs):
    try:
        instance = kwargs['instance']
    except:
        instance = None
        
    post = request.POST.copy()
    for kwarg in kwargs:
        if kwarg == 'instance':
            continue
        post[kwarg] = kwargs[kwarg]
    form = form(post, instance=instance)
    
    return form

def update_all_subsequent_LoanCalcs(loan_calc):
    #update will begin with calcs subsequent to the given calc (which was already updated using slightly different logic)
    existing_calcs = LoanCalc.objects.filter(loan=loan_calc.loan_id).count()
    if loan_calc.sequence < existing_calcs:
        curr_calc = get_next_calc(loan_calc)
        prior_calc = loan_calc
    else:
        return None
    
    while curr_calc.sequence <= existing_calcs:
        ending_prin, ending_int = stub_a_sched(prior_calc, curr_calc.loan_date)[1:]
        curr_calc.loan_amt = ending_prin
        curr_calc.rewritten_int = ending_int
        curr_calc.save()
        db_schedule_update(curr_calc, loan_calc_action='update', loan_date_was_updated=True)
        
        if curr_calc.sequence < existing_calcs:
            prior_calc = curr_calc
            curr_calc = get_next_calc(curr_calc)
        else:
            break

def get_df_LoanSched(loan_id):
    df = pd.DataFrame.from_records(LoanSched.objects.filter(loan_id=loan_id).values())
    seq_pd = pd.DataFrame.from_records(LoanCalc.objects.filter(loan_id=loan_id).values()) #get sequences - we'll join df's
    try:
        df = pd.merge(seq_pd[['id','sequence']], df, right_on='loan_calc_id', left_on='id')
        df['pmt_date'] = pd.to_datetime(df['pmt_date'])
        #df[['sequence','pmt_nbr']] = df[['sequence','pmt_nbr']].astype('Int32')
        #df[['pmt_nbr']] = df[['pmt_nbr']].astype('str')
        df = df.sort_values(by=['pmt_date'])
    except:
        None
    df = df_drop_cols_safe(df, ['id_x', 'id_y','loan_id', 'loan_calc_id'])
    
    return df

def get_df_CalcSched(calc_id):
    df = pd.DataFrame.from_records(CalcSched.objects.filter(loan_calc_id=calc_id).values())
    df['pmt_date'] = pd.to_datetime(df['pmt_date'])
    df = df_drop_cols_safe(df, ['id','loan_calc_id'])

    return df

def get_df_LoanRoll(loan_id,loan_balance_type=1):
    df = pd.DataFrame.from_records(LoanRoll.objects.filter(loan_id=loan_id).filter(loan_balance_type=loan_balance_type).values())
    df = df_drop_cols_safe(df,['id', 'loan_id','loan_balance_type_id'])
    
    return df

def get_monthend(dt):
    end_day = calendar.monthrange(dt.year, dt.month)[1]
    monthend = datetime.date(dt.year, dt.month, end_day)
    
    return monthend

def processing_months(begin_date,end_date):
    nbr_months = (end_date.year-begin_date.year)*12+end_date.month-begin_date.month+1
    
    return nbr_months

def is_same_month(dt1,dt2):
    result = dt1.year == dt2.year and dt1.month == dt2.month
    
    return result