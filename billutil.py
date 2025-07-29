import calendar
from datetime import date, datetime,timedelta
from itertools import groupby
from operator import itemgetter
from dateutil.relativedelta import relativedelta

def get_delta(frequency):
    if frequency == 1:
        delta = relativedelta(days=1)
    elif frequency == 7:
        delta = relativedelta(weeks=1)
    elif frequency == 14:
        delta = relativedelta(weeks=2)
    elif frequency == 30:
        delta = relativedelta(months=1)
    elif frequency == 90:
        delta = relativedelta(months=3)
    elif frequency == 365:
        delta = relativedelta(years=1)
    else:
        return {'error': 'Invalid contribution frequency'}, 400
    
    return delta

def generate_bill(
        amount,
        pay_date,        
        frequency,
        user_id,
        admin_id,
        bill_acc_id,
        type

):
    delta = get_delta(frequency)

    bill_transaction = []
    
    current_date = pay_date

    next_pay_date = current_date + delta

    current_datetime_now = datetime.now()

    current_amount = 0

    total_monthly_unpaid_bill=0

    is_single = 0
    if current_datetime_now <= next_pay_date:
        is_single = 1

        current_amount += amount
        current_amount = current_amount

        bill_transaction = {
            'amount':amount,
            'type':type,
            'payor':None,
            'note':None,
            'current_amount':amount,
            'pay_date':current_date,
            'due_date':next_pay_date,
            'created_at':current_datetime_now,
            'updated_at':current_datetime_now,
            'user_id':user_id,
            'admin_id':admin_id,
            'bill_acc_id':bill_acc_id,
            'payment_status':0,           
            'repeat_frequency':frequency

        }

        month = int(current_date.strftime("%Y%m"))

        if month == int(current_datetime_now.strftime('%Y%m')):            
            total_monthly_unpaid_bill+=amount

        return ({
            'bill_transaction':bill_transaction,
            'current_amount':current_amount,
            'next_pay_date':next_pay_date,
            'is_single':is_single,
            'total_monthly_unpaid_bill':total_monthly_unpaid_bill

        })


    if next_pay_date <= current_datetime_now:
        is_single = 0
        while next_pay_date <= current_datetime_now:

            current_amount += amount
            next_pay_date = current_date + delta

            month = int(current_date.strftime("%Y%m"))

            if month == int(current_datetime_now.strftime('%Y%m')):            
                total_monthly_unpaid_bill+=amount

            bill_transaction.append({
                'amount':amount,
                'type':type,
                'payor':None,
                'note':None,
                'current_amount':amount,
                'pay_date':current_date,
                'due_date':next_pay_date,
                'created_at':current_datetime_now,
                'updated_at':current_datetime_now,
                'user_id':user_id,
                'admin_id':admin_id,
                'bill_acc_id':bill_acc_id,
                'payment_status':0,               
                'repeat_frequency':frequency

            })
            current_date = next_pay_date

            

        return ({
            'bill_transaction':bill_transaction,
            'current_amount':current_amount,
            'next_pay_date':next_pay_date,
            'is_single':is_single,
            'total_monthly_unpaid_bill':total_monthly_unpaid_bill

        })    


def get_freq_data(start_date: date, frequency_days: int, amount:int):
    if frequency_days < 1:
        raise ValueError("Frequency must be a positive integer.")

    # End of the current calendar month
    year, month = start_date.year, start_date.month
    last_day = calendar.monthrange(year, month)[1]
    end_of_month = date(year, month, last_day)

    # Calculate how many full frequencies fit within current month
    days_remaining = (end_of_month - start_date).days + 1
    in_month_count = 1 + (days_remaining - 1) // frequency_days
    #in_month_count = days_remaining // frequency_days

    # First overflow date beyond end of month
    first_next_month_date = start_date + timedelta(days=in_month_count * frequency_days)
    
    total_amount  = in_month_count * amount
    
    return {
        #"count": in_month_count,
        "next_pay_date": first_next_month_date,
        'amount':total_amount        
    }