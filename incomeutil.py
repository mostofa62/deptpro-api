import calendar
from datetime import datetime,timedelta
from itertools import groupby
from operator import itemgetter

from bson import ObjectId

import hashlib
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
    if frequency == 30:
        month = current_date.month - 1 + repeat_count
        year = current_date.year + month // 12
        month = month % 12 + 1
        day = min(current_date.day, calendar.monthrange(year, month)[1])        
        return current_date.replace(year=year, month=month, day=day)
    elif frequency == 90:
        return move_next_time(current_date, 30, 3 * repeat_count)
    elif frequency == 365:
        return current_date.replace(year=current_date.year + repeat_count)
    elif frequency <= 14:
        # Move by 28 days for weekly frequency
        new_date = current_date + timedelta(days=28)  # 4 weeks
        return new_date
    """ elif frequency == 14:
        return current_date + timedelta(weeks=2 * repeat_count) """


def calculate_prorated_income(pay_date, input, frequency):
    # Get the last day of the current month
    last_day_of_month = calendar.monthrange(pay_date.year, pay_date.month)[1]    
    # Calculate the number of days left in the month after the pay date
    days_remaining_in_month = last_day_of_month - pay_date.day + 1    
    # Calculate daily income rate based on the gross input and frequency

    if frequency in [7,14]:
        if days_remaining_in_month > 7 and days_remaining_in_month < 14:
                days_remaining_in_month = 7
                
        if days_remaining_in_month > 14 and days_remaining_in_month < 21:
                days_remaining_in_month = 14
                
        if days_remaining_in_month > 21 and days_remaining_in_month < 28:
                days_remaining_in_month = 21
            
        if days_remaining_in_month > 28:
            days_remaining_in_month = 28


    daily_rate = input / frequency    
    # Calculate the prorated gross income for the remaining days in the month
    prorated_income = daily_rate * days_remaining_in_month    
    return prorated_income

def get_single_boost(initial_amount, 
                     contribution, 
                     start_date,
                     frequency, 
                     initial_gross_input,
                     initial_net_input
                     ):
  
    balance = initial_amount
    total_gross_for_period = initial_gross_input
    total_net_for_period = initial_net_input

    
    
    next_pay_date =  None
    current_date = start_date
    if frequency!=None:
        delta = get_delta(frequency)
        next_pay_date = current_date + delta

    balance += contribution

    balance = round(balance,2)

    total_gross_for_period +=  contribution
    total_net_for_period += contribution


    total_gross_for_period = round(total_gross_for_period,2)
    total_net_for_period = round(total_net_for_period,2)



    month = current_date.strftime("%Y-%m")
    month_word = current_date.strftime("%b, %Y")
    

    income_transaction = {                
                'month_word':month_word,
                'month':month,
                'pay_date':current_date,
                "next_pay_date":next_pay_date,
                'gross_income':contribution,
                'net_income':contribution,   
                "total_gross_for_period": total_gross_for_period,
                'total_net_for_period':total_net_for_period,
                "deleted_at":None,
                "closed_at":None            
                      
    }
    

    return ({
               
        
        'income_transaction':income_transaction,
        'total_gross_for_period':total_gross_for_period,
        'total_net_for_period':total_net_for_period,
        'next_pay_date':next_pay_date,
        'total_boost_for_period': balance       
    })

def get_single_income(
        initial_gross_input,
        initial_net_input,
        gross_input,
        net_input,
        pay_date,
        frequency,
        commit,
        income_id,
        user_id  
):
    
    delta = get_delta(frequency)    
    current_date = pay_date
    
    

    next_pay_date = current_date + delta
    
    
    total_gross_for_period = initial_gross_input
    total_net_for_period = initial_net_input

    total_gross_for_period +=  gross_input
    total_net_for_period += net_input

    total_gross_for_period = round(total_gross_for_period,2)
    total_net_for_period = round(total_net_for_period,2)

    

    month = current_date.strftime("%Y-%m")
    month_word = current_date.strftime("%b, %Y")



    income_transaction = {
        'month_word':month_word,
        'month':month,
        'pay_date':current_date,
        "next_pay_date":next_pay_date,
        'gross_income':gross_input,
        'net_income':net_input,               
        "total_gross_for_period": total_gross_for_period,
        'total_net_for_period':total_net_for_period,            
        "income_id":income_id,
        "income_boost_id":None,
        'user_id':user_id,
        'commit':commit,
        "deleted_at":None,
        "closed_at":None            
        
    }


    
    return ({
        'income_transaction':income_transaction,
        'total_gross_for_period':total_gross_for_period,
        'total_net_for_period':total_net_for_period,
        'next_pay_date':next_pay_date
    })

    

#now we will need a function which will 
## generate new transaction data for first_pay_date month to current month
def generate_new_transaction_data_for_income(
        gross_input,
        net_input,
        pay_date,
        frequency,
        commit,
        income_id,
        user_id

):
    
    delta = get_delta(frequency)
    
    income_transaction = []
    
    current_date = pay_date    
    
   

    total_gross_for_period = 0
    total_net_for_period = 0


    
    next_pay_date = current_date + delta

    current_datetime_now = datetime.now()



    

    if next_pay_date <= current_datetime_now:
        while next_pay_date <= current_datetime_now:

            total_gross_for_period +=  gross_input
            total_net_for_period += net_input                        

            total_gross_for_period = round(total_gross_for_period,2)
            total_net_for_period = round(total_net_for_period,2)

           

            
            next_pay_date = current_date + delta

            month = current_date.strftime("%Y-%m")
            month_word = current_date.strftime("%b, %Y")
            


            income_transaction.append({
                'month_word':month_word,
                'month':month,
                'pay_date':current_date,
                "next_pay_date":next_pay_date,
                'gross_income':gross_input,                
                'net_income':net_input,                         
                "total_gross_for_period": total_gross_for_period,
                'total_net_for_period':total_net_for_period,           
                "income_id":income_id,
                "income_boost_id":None,
                'user_id':user_id,
                'commit':commit,
                "deleted_at":None,
                "closed_at":None            
                
            })

             # Move to the next period based on base income frequency
            current_date = next_pay_date


   
        

    return ({
        'income_transaction':income_transaction,
        'total_gross_for_period':total_gross_for_period,
        'total_net_for_period':total_net_for_period,         
        'next_pay_date':next_pay_date
    })


def generate_new_transaction_data_for_future_income_v1(
        initial_gross_input,
        initial_net_input,
        gross_input,
        net_input,
        pay_date,
        frequency
    ):

    income_transaction = []
    current_date = pay_date
    end_date = pay_date.replace(year=pay_date.year + 1)

    # Initialize counters for monthly totals
    current_month = current_date.month
    monthly_gross_total = initial_gross_input
    monthly_net_total = initial_net_input

    

    while current_date < end_date:
        # Get the last day of the current month
        last_day_of_month = calendar.monthrange(current_date.year, current_month)[1]
        end_of_month = current_date.replace(day=last_day_of_month)
        
       
        days_left_in_month = (end_of_month - current_date).days + 1
        num_periods = days_left_in_month // frequency

        print('days_left_in_month',end_of_month.strftime("%Y-%m"),days_left_in_month)

        # Add recurring income for each period within the current month
        monthly_gross_total += gross_input * num_periods
        monthly_net_total += net_input * num_periods
        
        # Record the monthly totals
        income_transaction.append({
            'month_word': end_of_month.strftime("%b, %Y"),
            'month': end_of_month.strftime("%Y-%m"),
            'base_gross_income': monthly_gross_total,
            'base_net_income': monthly_net_total,
        })
        
        # Move to the first pay date of the next month
        current_date = end_of_month + timedelta(days=1)
        current_month = current_date.month


    return ({
        'income_transaction':income_transaction
    })



def calculate_breakdown_future( 
        initial_gross_input,
        initial_net_input,       
        gross_input,
        net_input,
        pay_date,
        frequency,
        income_boost=0,
        income_boost_date=None,         
        repeat_income_boost=None               
):
    
    

    delta = get_delta(frequency)
    
    months_breakdown = []
    gross_income = initial_gross_input
    net_income = initial_net_input

    current_date = pay_date

    next_contribution_date = current_date + delta

    current_datetime_now = datetime.now() + timedelta(days=365)

    while next_contribution_date <= current_datetime_now:
        month_string = current_date.strftime('%Y-%m')

        income_boost_gross = None 
        income_boost_net = None
        if month_string == income_boost_date:
                print('month==saving_boost',month_string,income_boost_date)
                #print(contribution, balance)
                income_boost_gross = income_boost + gross_input
                income_boost_net = income_boost + net_input
        #     #balance += saving_boost
                print('income_boost_gross, income_boost_net',income_boost_gross,income_boost_net)
        else:
            income_boost_gross = None 
            income_boost_net = None

        # Calculate next contribution date
            next_contribution_date = current_date + delta

        if income_boost_gross!=None and income_boost_net!=None:
            gross_income +=income_boost_gross
            net_income +=income_boost_net
        else:
            gross_income += gross_input
            net_income += net_input

        if repeat_income_boost!=None:
            gross_income += repeat_income_boost
            net_income += repeat_income_boost

        
        if gross_income < 0 or net_income < 0:
                break
        
        months_breakdown.append({
            'month_word':current_date.strftime("%b, %Y"),
            'month':current_date.strftime("%Y-%m"),
            #'pay_date':current_date,
            #"next_pay_date":next_pay_date,
            #'gross_income':gross_input,
            #'net_income':net_input,
            'base_gross_income':gross_income,
            'base_net_income':net_income,
            # "total_gross_for_period": gross_income,
            # 'total_net_for_period':net_input                      
            
        })

        # Move to the next period based on the contribution frequency
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
            max_entry = max(group_list, key=lambda x: x['base_gross_income'])
            
            # Append the max entry for this month to the result array
            max_balance_per_month.append(max_entry)

        # Output the result
        if len(max_balance_per_month)> 0:
            months_breakdown  = max_balance_per_month

    return ({
        'breakdown':months_breakdown
    })

def generate_unique_id(month):
    # Use hashlib to generate a hash string from the month
    return hashlib.md5(month.encode()).hexdigest()






def generate_new_transaction_data_for_income_boost(
        initial_amount,
        contribution,
        start_date,
        frequency,
        commit,
        income_id,
        income_boost_id,
        user_id,
        initial_gross_input,
        initial_net_input        
):

    delta = get_delta(frequency)
    
    income_transaction = []

    current_date = start_date
    
    balance = initial_amount
    total_gross_for_period = initial_gross_input
    total_net_for_period = initial_net_input

    next_pay_date = current_date + delta

    current_datetime_now = datetime.now()

    

    if next_pay_date <= current_datetime_now:
        while next_pay_date <= current_datetime_now:

            balance += contribution
            balance = round(balance,2)

            total_gross_for_period +=  contribution
            total_net_for_period += contribution


            total_gross_for_period = round(total_gross_for_period,2)
            total_net_for_period = round(total_net_for_period,2)

            

            next_pay_date = current_date + delta

            month = current_date.strftime("%Y-%m")
            month_word = current_date.strftime("%b, %Y")
            


            income_transaction.append({
                'month_word':month_word,
                'month':month,
                'pay_date':current_date,
                "next_pay_date":next_pay_date,
                'gross_income':contribution,                
                'net_income':contribution,                         
                "total_gross_for_period": total_gross_for_period,
                'total_net_for_period':total_net_for_period,           
                "income_id":income_id,
                "income_boost_id":income_boost_id,
                'user_id':user_id,
                'commit':commit,
                "deleted_at":None,
                "closed_at":None            
                
            })

             # Move to the next period based on base income frequency
            current_date = next_pay_date


   
        

    return ({                       
        'income_transaction':income_transaction,
        'total_gross_for_period':total_gross_for_period,
        'total_net_for_period':total_net_for_period,
        'next_pay_date':next_pay_date,
        'total_boost_for_period': balance       
    })



def generate_new_transaction_data_for_future_income_boost(
        input_boost,
        pay_date,
        frequency               
):
    
    income_transaction = []

    current_date = pay_date
    first_pay_date = current_date
    today = datetime.now() + timedelta(days=365)
    
    #print(current_date, today)

    total_input_boost_for_period = 0
   

    next_pay_date_boost = None

    while current_date <= today:

        base_input_boost = input_boost
        
        if frequency < 90:
            
            if frequency < 30 and current_date == first_pay_date:
                base_input_boost = calculate_prorated_income(first_pay_date, input_boost, frequency)
                
            else:
                base_input_boost = calcuate_frequncey_wise_income(input_boost, frequency)
                


        base_input_boost = round(input_boost,2)
        

        total_input_boost_for_period += base_input_boost
        
        
        next_pay_date_boost = move_next_time(current_date, frequency)

        total_input_boost_for_period = round(total_input_boost_for_period,2)
        
        
        
        income_transaction.append({
            'month_word':current_date.strftime("%b, %Y"),
            'month':current_date.strftime("%Y-%m"),
            'base_input_boost':base_input_boost,        
            "total_input_boost_for_period": total_input_boost_for_period                            
            
        })

        # Move to the next period based on base income frequency
        current_date = next_pay_date_boost


        
   
        

    return ({
        'income_transaction':income_transaction,
        'total_input_boost_for_period':total_input_boost_for_period,
        'next_pay_date_boost':next_pay_date_boost
    })




def calculate_total_income_for_sepecific_month(data, target_month, key='base_net_income',keyg='base_gross_income'):
    # Sum gross_income and net_income for documents where the month matches target_month    
    total_monthly_gross_income = sum(doc[keyg] for doc in data if doc["month"] == target_month)
    total_monthly_net_income = sum(doc[key] for doc in data if doc["month"] == target_month)
    return total_monthly_net_income,total_monthly_gross_income