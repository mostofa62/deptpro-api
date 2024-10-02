import calendar
from datetime import datetime,timedelta

from bson import ObjectId

import hashlib
#this below 2 function will generate the amonunt based on frequency
def calcuate_frequncey_wise_income(input, frequency):
    normalized_income = input * (30 / frequency)
    return normalized_income


#here for each
## if we have fraction for daily-7, biweekly-14 then delete due day amount


#now we need to get next_pay_date based on pay_date and frequnecy
### we dont need day ,week , biweek becuase we all goes to month
## for single entry
def calculate_next_payment(pay_date, repeat_value):
    if repeat_value == 30:  # Monthly
        next_payment = pay_date.replace(month=pay_date.month % 12 + 1) if pay_date.month != 12 else pay_date.replace(year=pay_date.year + 1, month=1)
    elif repeat_value == 90:  # Quarterly
        next_payment = pay_date.replace(month=pay_date.month + 3 if pay_date.month <= 9 else pay_date.month - 9, year=pay_date.year if pay_date.month <= 9 else pay_date.year + 1)
    elif repeat_value == 365:  # Annually
        try:
            next_payment = pay_date.replace(year=pay_date.year + 1)
        except ValueError:
            # Handle leap year case for February 29
            if pay_date.month == 2 and pay_date.day == 29:
                next_payment = pay_date.replace(year=pay_date.year + 1, day=28)
            else:
                raise
    else:
        next_payment = None  # For unsupported repeat values
    return next_payment


# Function to calculate the next payment date based on frequency
def move_next_time(current_date, frequency, repeat_count=1):
    if frequency <= 30:
        month = current_date.month - 1 + repeat_count
        year = current_date.year + month // 12
        month = month % 12 + 1
        day = min(current_date.day, calendar.monthrange(year, month)[1])
        return current_date.replace(year=year, month=month, day=day)
    elif frequency == 90:
        return move_next_time(current_date, 30, 3 * repeat_count)
    elif frequency == 365:
        return current_date.replace(year=current_date.year + repeat_count)    


def calculate_prorated_income(pay_date, input, frequency):
    # Get the last day of the current month
    last_day_of_month = calendar.monthrange(pay_date.year, pay_date.month)[1]    
    # Calculate the number of days left in the month after the pay date
    days_remaining_in_month = last_day_of_month - pay_date.day + 1    
    # Calculate daily income rate based on the gross input and frequency
    daily_rate = input / frequency    
    # Calculate the prorated gross income for the remaining days in the month
    prorated_income = daily_rate * days_remaining_in_month    
    return prorated_income


#now we will need a function which will 
## generate new transaction data for first_pay_date month to current month
def generate_new_transaction_data_for_income(
        gross_input,
        net_input,
        pay_date,
        frequency,
        commit,
        income_id        
):
    
    income_transaction = []

    current_date = pay_date
    first_pay_date = current_date
    today = datetime.today()
    
    #print(current_date, today)

    total_gross_for_period = 0
    total_net_for_period = 0

    next_pay_date = None

    while current_date <= today:

        base_gross_income = gross_input
        base_net_income = net_input
        if frequency < 90:
            
            if frequency < 30 and current_date == first_pay_date:
                base_gross_income = calculate_prorated_income(first_pay_date, gross_input, frequency)
                base_net_income = calculate_prorated_income(first_pay_date, net_input, frequency)
            else:
                base_gross_income = calcuate_frequncey_wise_income(gross_input, frequency)
                base_net_income = calcuate_frequncey_wise_income(net_input, frequency)


        base_gross_income = round(base_gross_income,2)
        base_net_income = round(base_net_income,2)

        total_gross_for_period += base_gross_income
        total_net_for_period += base_net_income
        
        next_pay_date = move_next_time(current_date, frequency)

        total_gross_for_period = round(total_gross_for_period,2)
        total_net_for_period = round(total_net_for_period,2)
        
        
        income_transaction.append({
            'month_word':current_date.strftime("%b, %Y"),
            'month':current_date.strftime("%Y-%m"),
            'pay_date':current_date,
            "next_pay_date":next_pay_date,
            'gross_income':gross_input,
            'net_income':net_input,
            'base_gross_income':base_gross_income,
            'base_net_income':base_net_income,
            "total_gross_for_period": total_gross_for_period,
            'total_net_for_period':total_net_for_period,            
            "income_id":income_id,
            'commit':commit            
            
        })

        # Move to the next period based on base income frequency
        current_date = next_pay_date


        
   
        

    return ({
        'income_transaction':income_transaction,
        'total_gross_for_period':total_gross_for_period,
        'total_net_for_period':total_net_for_period,
        'next_pay_date':next_pay_date
    })




def generate_new_transaction_data_for_future_income(
        gross_input,
        net_input,
        pay_date,
        frequency               
):
    
    income_transaction = []

    current_date = pay_date
    first_pay_date = current_date
    today = datetime.now() + timedelta(days=365)
    
    #print(current_date, today)

    total_gross_for_period = 0
    total_net_for_period = 0

    next_pay_date = None

    while current_date <= today:

        base_gross_income = gross_input
        base_net_income = net_input
        if frequency < 90:
            
            if frequency < 30 and current_date == first_pay_date:
                base_gross_income = calculate_prorated_income(first_pay_date, gross_input, frequency)
                base_net_income = calculate_prorated_income(first_pay_date, net_input, frequency)
            else:
                base_gross_income = calcuate_frequncey_wise_income(gross_input, frequency)
                base_net_income = calcuate_frequncey_wise_income(net_input, frequency)


        base_gross_income = round(base_gross_income,2)
        base_net_income = round(base_net_income,2)

        total_gross_for_period += base_gross_income
        total_net_for_period += base_net_income
        
        next_pay_date = move_next_time(current_date, frequency)

        total_gross_for_period = round(total_gross_for_period,2)
        total_net_for_period = round(total_net_for_period,2)
        
        
        income_transaction.append({
            'month_word':current_date.strftime("%b, %Y"),
            'month':current_date.strftime("%Y-%m"),
            #'pay_date':current_date,
            #"next_pay_date":next_pay_date,
            #'gross_income':gross_input,
            #'net_income':net_input,
            'base_gross_income':base_gross_income,
            'base_net_income':base_net_income,
            "total_gross_for_period": total_gross_for_period,
            'total_net_for_period':total_net_for_period                      
            
        })

        # Move to the next period based on base income frequency
        current_date = next_pay_date


        
   
        

    return ({
        'income_transaction':income_transaction,
        'total_gross_for_period':total_gross_for_period,
        'total_net_for_period':total_net_for_period,
        'next_pay_date':next_pay_date
    })

def generate_unique_id(month):
    # Use hashlib to generate a hash string from the month
    return hashlib.md5(month.encode()).hexdigest()