import sqlalchemy
import pandas as pd
import calendar
import datetime
import pdb
from dateutil.relativedelta import relativedelta
    
def tbl_to_df(enginetxt,tblname):
    engine = sqlalchemy.create_engine(enginetxt)
    con = engine.connect()
    df = pd.read_sql(tblname, con)
    
    return df

def calculate_loan_roll(loan_id,df_ls,loan_calc):
    #think about adding logic to delete whats already in the db and replace with the out of this process
    #but actually, let's take care of db read/writes in a separate function - maybe even must be called from the view (visible)
    df_ls = df_ls.sort_values(by=['pmt_date'])
    df_ls = df_ls.reset_index(drop=True)
    df_txns = calculate_transactions(df_ls,loan_calc)
    maturity = df_ls['pmt_date'][df_ls.index[-1]]
    months = processing_months(loan_calc.loan_date, maturity)
    #pdb.set_trace() 
    df_roll = pd.DataFrame()
    mydate = get_monthend(loan_calc.loan_date)
    mydict = {'loan_id':loan_id}
    for i in range(months):
        mydict['roll_year'] = mydate.year
        mydict['roll_month'] = mydate.month
        
        df_roll = df_roll.append(mydict, ignore_index=True)
        mydate = get_monthend(mydate + datetime.timedelta(days=1))
    
    df_roll['loan_balance_type_id'] = 1
    df_temp = df_roll.copy()
    df_temp['loan_balance_type_id'] = 2
    df_roll = df_roll.append(df_temp, ignore_index=True)
    
    df_adds = df_txns[df_txns['roll_txn_type_id'] == 1].groupby(['txn_year','txn_month','loan_balance_type_id']).sum()
    df_reduce = df_txns[df_txns['roll_txn_type_id'] == 2].groupby(['txn_year','txn_month','loan_balance_type_id']).sum()
    #txn_sum = df_drop_cols_safe(txn_sum,['loansched_id'])
    
    #bring in the additions
    df_roll = pd.merge(df_roll, df_adds, how='left',
                       left_on=['roll_year','roll_month','loan_balance_type_id'], 
                       right_on=['txn_year','txn_month','loan_balance_type_id'])
    #pdb.set_trace()
    df_roll = df_roll.rename(columns={'amount':'add'})
    df_roll = df_drop_cols_safe(df_roll,['loansched_id','roll_txn_type_id'])
    
    #bring in the reductions
    df_roll = pd.merge(df_roll, df_reduce, how='left',
                       left_on=['roll_year','roll_month','loan_balance_type_id'], 
                       right_on=['txn_year','txn_month','loan_balance_type_id'])
    
    df_roll = df_roll.rename(columns={'amount':'reduce'})
    df_roll = df_drop_cols_safe(df_roll,['loansched_id','roll_txn_type_id'])
    
    df_roll = df_roll.fillna(0)
    
    df_roll['begin'] = 0.0
    df_roll['end'] = 0.0
    prior_bal = 0
    prior_type = 1
    
    for i, row in df_roll.iterrows():
        #pdb.set_trace()
        if prior_type != row.at['loan_balance_type_id']:
            prior_bal = 0
        df_roll.at[i,'begin'] = prior_bal
        end_bal = prior_bal + row.at['add'] - row.at['reduce']
        df_roll.at[i,'end'] = end_bal
        prior_bal = end_bal
        prior_type = row.at['loan_balance_type_id']
            
    #pdb.set_trace()
    #print(df_roll.shape)
    return df_roll, df_txns 

def calculate_transactions(df_ls,loan_calc):
    df_txns = pd.DataFrame()
    #pdb.set_trace()
    row_id = df_ls.at[0,'id']
    
    df_prin_pmts = get_txns(df_ls,'prin_pmt',1,2)
    df_int_pmts = get_txns(df_ls,'int_pmt',2,2)
    df_prin_add = get_add_prin(df_ls,loan_calc,row_id)
    df_int_add = get_add_int(df_ls,loan_calc)
    #pdb.set_trace()
    
    #append
    df_txns = df_txns.append(df_prin_pmts,ignore_index=True)
    df_txns = df_txns.append(df_int_pmts,ignore_index=True)
    df_txns = df_txns.append(df_prin_add,ignore_index=True)
    df_txns = df_txns.append(df_int_add,ignore_index=True)
    
    return df_txns

def get_txns(df,amt_col,bal_code,roll_txn_type_id):
    df = df.copy()
    df = df.rename(columns={'id':'loansched_id',amt_col:'amount'})
    df['txn_year'] = pd.DatetimeIndex(df['pmt_date']).year
    df['txn_month'] = pd.DatetimeIndex(df['pmt_date']).month
    df['roll_txn_type_id'] = roll_txn_type_id
    df['loan_balance_type_id'] = bal_code
    keep_cols = ['loansched_id','txn_year','txn_month','roll_txn_type_id','loan_balance_type_id','amount']
    drop_cols = [col for col in list(df.columns) if col not in keep_cols]
    df = df_drop_cols_safe(df,drop_cols)
    df = whole_cents(df,'amount')
    if bal_code == 1 and roll_txn_type_id == 1:
        df = df[df.index == 0]
    else:
        df = df[df['amount'] != 0]
    
    return df

def get_add_prin(df,loan_calc,row_id):
    df_txns = pd.DataFrame()
    mydict = {}
    mydict['loansched_id'] = row_id
    mydict['amount'] = loan_calc.loan_amt
    mydict['txn_year'] = loan_calc.loan_date.year
    mydict['txn_month'] = loan_calc.loan_date.month
    mydict['roll_txn_type_id'] = 1
    mydict['loan_balance_type_id'] = 1
    
    df_txns = df_txns.append(mydict, ignore_index=True)
    
    return df_txns

def get_add_int(df,loan_calc):
    df_txns = pd.DataFrame()
    end_pmt_date = loan_calc.loan_date-datetime.timedelta(days=1)
    for i, row in df.iterrows():
        begin_pmt_date = end_pmt_date+datetime.timedelta(days=1)
        end_pmt_date = row.pmt_date
        days_in_pmt = (end_pmt_date-begin_pmt_date).days + 1
        months = processing_months(begin_pmt_date,end_pmt_date)
        for x in range(months):
            mydict = {}
            mydate = begin_pmt_date+relativedelta(months=+x)
            begin_month_date = datetime.date(mydate.year, mydate.month, 1)
            end_month_date = get_monthend(mydate)
            overlap = days_overlap(end_month_date, end_pmt_date, begin_month_date, begin_pmt_date)
            int_ratio = overlap / days_in_pmt
            mydict['loansched_id'] = row.id
            mydict['amount'] = row.add_int * int_ratio
            mydict['txn_year'] = mydate.year
            mydict['txn_month'] = mydate.month
            mydict['roll_txn_type_id'] = 1
            mydict['loan_balance_type_id'] = 2
            
            df_txns = df_txns.append(mydict, ignore_index=True)
    
    df_txns = whole_cents(df_txns,'amount')
    
    return df_txns

def whole_cents(df,col):
    diff = 0
    
    for i, row in df.iterrows():
        orig_val = row[col] + diff
        rnd_val = round(orig_val,2)
        diff = orig_val-rnd_val
        df.at[i,col] = rnd_val
    
    return df

def get_monthend(dt):
    end_day = calendar.monthrange(dt.year, dt.month)[1]
    monthend = datetime.date(dt.year, dt.month, end_day)
    
    return monthend

def processing_months(begin_date,end_date):
    nbr_months = (end_date.year-begin_date.year)*12+end_date.month-begin_date.month+1
    #pdb.set_trace()
    return nbr_months

def is_same_month(dt1,dt2):
    result = dt1.year == dt2.year and dt1.month == dt2.month
    #pdb.set_trace()
    return result

def days_overlap(end1,end2,begin1,begin2):
    result = max((min(end1,end2)-max(begin1,begin2)).days + 1,0)
    
    return result

def add_record_prin(df, prior_prin_bal, begin_date, end_date, loan_calc, baseprin, df_row_nbr, row, proc_mo):
    #pdb.set_trace()
    currprin = baseprin.copy()
    currprin['roll_year'] = end_date.year
    currprin['roll_month'] = end_date.month
    
    if df_row_nbr == 0 and proc_mo == 0:
        currprin['begin'] = 0
        currprin['add'] = loan_calc.loan_amt
    else:
        currprin['begin'] = prior_prin_bal
        currprin['add'] = 0
        
    if is_same_month(row.pmt_date,end_date):
        currprin['loan_sched_id'] = row.id
        currprin['reduce'] = row.prin_pmt
    else:
        currprin['reduce'] = 0
        
    currprin['end'] = currprin['begin'] + currprin['add'] - currprin['reduce']
    
    df = df.append(currprin, ignore_index=True) #append record
    prior_bal_end = currprin['end']   
    begin_date = end_date+datetime.timedelta(days=1)
    end_date = get_monthend(begin_date)
    
    return df, begin_date, end_date, prior_bal_end

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

if __name__ == '__main__':
    def setup_test_data(loan_id):
        loan_id = str(loan_id)
        enginetxt = "postgresql://postgres:C4r0l1n3!@localhost/finance"
        ls = 'SELECT * FROM public.loans_loansched WHERE loan_id = ' + loan_id
        ls = tbl_to_df(enginetxt,ls)
        ls = ls.sort_values(by=['pmt_date'])
        ls = ls.reset_index(drop=True)
        loan_calc = 'SELECT * FROM public.loans_loancalc WHERE sequence = 1 AND loan_id = ' + loan_id
        loan_calc = tbl_to_df(enginetxt,loan_calc)
        loan_calc = loan_calc.iloc[0]
        
        return ls, loan_calc
    
    loan_id = 5
    df_ls, loan_calc = setup_test_data(loan_id)
    df_roll, df_txns = calculate_loan_roll(loan_id)