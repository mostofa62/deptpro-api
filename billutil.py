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

    is_single = 0
    if current_datetime_now <= next_pay_date:
        is_single = 1

        current_amount += amount
        current_amount = round(current_amount,2)

        bill_transaction = {
            'amount':amount,
            'type':type,
            'payor':None,
            'note':None,
            'current_amount':amount,
            'pay_date':current_date,
            'due_date':next_pay_date,
            'created_at':datetime.now(),
            'updated_at':datetime.now(),
            'user_id':user_id,
            'admin_id':admin_id,
            'bill_acc_id':bill_acc_id,
            'payment_status':0,           
            'repeat_frequency':frequency

        }

        return ({
            'bill_transaction':bill_transaction,
            'current_amount':current_amount,
            'next_pay_date':next_pay_date,
            'is_single':is_single

        })


    if next_pay_date <= current_datetime_now:
        is_single = 0
        while next_pay_date <= current_datetime_now:

            current_amount += amount
            next_pay_date = current_date + delta

            bill_transaction.append({
                'amount':amount,
                'type':type,
                'payor':None,
                'note':None,
                'current_amount':amount,
                'pay_date':current_date,
                'due_date':next_pay_date,
                'created_at':datetime.now(),
                'updated_at':datetime.now(),
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
            'is_single':is_single

        })    


