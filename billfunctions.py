
from datetime import datetime, timedelta
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
        return 0
    
    return delta
def calculate_future_bill(initial_amount, start_date, frequency):

    months_breakdown = []
    current_date = start_date

    delta = get_delta(frequency)

    if frequency < 1:
        delta = get_delta(30)

    next_contribution_date = current_date + delta

    balance  = initial_amount

    current_datetime_now = datetime.now() + timedelta(days=365)
    while next_contribution_date <= current_datetime_now:
        month_string = current_date.strftime('%Y-%m')

        months_breakdown.append({
            'month_word':current_date.strftime("%b, %Y"),
            'month':month_string,
            #'pay_date':current_date,
            "next_due_date":next_contribution_date,
            #'gross_income':gross_input,
            #'net_income':net_input,
            'balance':balance,           
            # "total_gross_for_period": gross_income,
            # 'total_net_for_period':net_input                      
            
        })

        balance += initial_amount

        next_contribution_date = current_date + delta

        current_date = next_contribution_date

    
    if len(months_breakdown) > 0:
        # First, we need to sort the months_breakdown array by the 'month' key to use groupby
        months_breakdown_sorted = sorted(months_breakdown, key=itemgetter('month'))

        # Group the entries by 'month' and find the max 'total_balance' in each group
        max_balance_per_month = []

        for month, group in groupby(months_breakdown_sorted, key=itemgetter('month')):
            # Convert group to a list
            group_list = list(group)
            
            # Find the entry with the max total_balance in this group
            max_entry = max(group_list, key=lambda x: x['balance'])
            
            # Append the max entry for this month to the result array
            max_balance_per_month.append(max_entry)

        # Output the result
        if len(max_balance_per_month)> 0:
            months_breakdown  = max_balance_per_month

    return ({
        'breakdown':months_breakdown
    })


