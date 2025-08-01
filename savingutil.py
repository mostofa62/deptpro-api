import calendar
from datetime import date, datetime, timedelta
import math
from dateutil.relativedelta import relativedelta

from itertools import groupby
from operator import itemgetter

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

def get_next_contribution_date(current_date, frequency):
    delta = get_delta(frequency)
    next_contribution_date = current_date + delta
    return next_contribution_date


def get_single_boost(initial_amount, contribution, start_date,frequency,period,op_type):
  
    balance = initial_amount
    month = period
    next_contribution_date =  None
    current_date = start_date
    if frequency!=None:
        delta = get_delta(frequency)
        next_contribution_date = current_date + delta

    contribution = -contribution if op_type > 1 else contribution

    balance +=  contribution



    month+=1

    months_breakdown = {
                "period": month,
                "month": current_date.strftime('%Y-%m'),
                "month_word": current_date.strftime('%b, %Y'),                
                "contribution": contribution,
                "total_balance": round(balance, 2),                
                "contribution_date":current_date,
                "next_contribution_date": next_contribution_date           
    }
    total_balance = balance

    return ({
        'breakdown':months_breakdown,
        'next_contribution_date':next_contribution_date,        
        'total_balance':round(total_balance, 2)        
    })

    # return months_breakdown


def get_single_breakdown(initial_amount, contribution, annual_interest_rate, goal_amount, start_date, frequency,period, i_contribution=0,initial_amount_boost=0):

    total_balance = 0
    goal_reached = None

    
    delta = get_delta(frequency)
    
    months_breakdown = {}
    balance = initial_amount
    balance_xyz = initial_amount_boost
    
    
    current_date = start_date
    
    
    interest_rate = annual_interest_rate / 100

    # Adjust interest calculation for non-monthly contributions
    daily_rate = interest_rate / 365  # Daily interest rate based on the annual rate

    # Get the current date to stop if the current month is exceeded
    #current_month_end = datetime.now().replace(day=1) + relativedelta(months=1) - relativedelta(days=1)

    next_contribution_date = current_date + delta
    progress = 0
    progress_xyz = 0

    if balance < goal_amount:
        next_contribution_date = current_date + delta

        days_in_period = (next_contribution_date - current_date).days
        interest = balance * (daily_rate * days_in_period)  # Interest calculated based on the days between contributions
        interest_xyz = balance_xyz * (daily_rate * days_in_period)

        balance += interest + contribution
        balance_xyz += interest_xyz + contribution

        period += 1
        #increase contribution by periodically
        inc_contri = period * i_contribution
        balance += inc_contri
        balance_xyz += inc_contri
        #increase contribution end

        #contribution_with_increse
        contribution_i =  contribution + inc_contri
        #end contribution_with_increase

        contribution_i_intrs = interest + contribution_i
        contribution_i_intrs_xyz = interest_xyz + contribution_i
                
        # Calculate progress towards the goal
        progress = (balance / goal_amount) * 100
        progress_xyz = (balance_xyz / goal_amount) * 100

        month = int(current_date.strftime("%Y%m"))
        
        months_breakdown = {
                "period": period,
                "month": month,                
                "interest": round(interest, 2),
                'interest_xyz':round(interest_xyz,2),
                "contribution": contribution,
                "contribution_i":contribution_i,
                "increase_contribution":i_contribution,
                "increase_contribution_prd":inc_contri,
                'contribution_i_intrs':round(contribution_i_intrs,2),
                'contribution_i_intrs_xyz':round(contribution_i_intrs_xyz,2),                                
                "total_balance": round(balance, 2),
                'total_balance_xyz':round(balance_xyz,2),
                "progress": round(progress, 2),
                'progress_xyz':round(progress_xyz,2),
                "contribution_date":current_date,
                "next_contribution_date": next_contribution_date           
        }

    total_balance = balance
    total_balance_xyz = balance_xyz

    if total_balance >= goal_amount or total_balance_xyz>= goal_amount:
        progress = round(100,2)
        goal_reached = next_contribution_date
        next_contribution_date = None
    
    return ({
        'breakdown':months_breakdown,
        'next_contribution_date':next_contribution_date,
        'progress':math.floor(progress_xyz) if math.floor(progress_xyz) > math.floor(progress) else math.floor(progress),
        'total_balance':round(total_balance, 2),
        'total_balance_xyz':round(total_balance_xyz,2),
        'goal_reached':goal_reached,
        'period':period
    })

FREQUENCY_MAP = {
    1: 365,
    7: 52,
    14: 26,     # every 2 weeks
    30: 12,
    90: 4,     # every 3 months
    365:1
}

def calculate_intial_balance(
        contribution, 
                        annual_interest_rate,  
                        start_date,                                                 
                        period=0,
                        interest_type=1
):
    periods_per_year = FREQUENCY_MAP[1]
    
    total_balance = 0
    total_balance_xyz = 0

    total_monthly_balance_xyz = 0
    current_date = start_date        
    interest_rate = annual_interest_rate / 100
    rate_per_period = (interest_rate / 100) / periods_per_year

    months_breakdown = [] 

    progress = 0
    inc_contri=0
    contribution_i=contribution
    contribution_i_intrs=0
    interest=0.0
    next_contribution_date = None
    balance = 0
    
    #less then current date
    current_datetime_now = datetime.now()

    if interest_type > 1:

        balance += contribution
        contribution_i_intrs = contribution
        interest = (balance * rate_per_period)
        balance += interest

    else:

        interest = (contribution * rate_per_period)
        contribution_i_intrs = interest + contribution
        balance += contribution_i_intrs

    month = int(current_date.strftime("%Y%m"))

    months_breakdown = {
            "period": period,
            "month": month,            
            "interest": interest,
            'interest_xyz':interest,
            "contribution": contribution,
            "contribution_i":contribution_i,
            "contribution_i_intrs":contribution_i_intrs,
            'contribution_i_intrs_xyz':contribution_i_intrs,
            "increase_contribution":0,
            "increase_contribution_prd":inc_contri,
            "total_balance": balance,
            "total_balance_xyz": balance,
            "progress": progress,
            "progress_xyz": progress,
            "contribution_date":current_date,
            "next_contribution_date": next_contribution_date           
        }
    
    if month == int(current_datetime_now.strftime('%Y%m')):
            total_monthly_balance_xyz+= contribution_i_intrs

    total_balance = balance
    total_balance_xyz = balance
    
    
    return ({
        'breakdown':months_breakdown,
        'progress':math.floor(progress),
        'total_balance':total_balance,
        'total_balance_xyz':total_balance_xyz,        
        'period':period,
        'total_monthly_balance_xyz':total_monthly_balance_xyz        
    })

def calculate_breakdown_ontime(initial_amount, 
                        contribution, 
                        annual_interest_rate, 
                        goal_amount, 
                        start_date,                                                 
                        period=0,
                        interest_type=1,
                        savings_strategy=2,
                        op_type=1,
                        initial_amount_boost=0
                        ):
    
    periods_per_year = FREQUENCY_MAP[1]
    
    total_balance = 0
    total_balance_xyz = 0
    total_balance_boost = 0
    goal_reached = None
    contribution = -contribution if op_type > 1 else contribution
    total_monthly_balance_xyz = 0
    total_monthly_balance_boost = 0
    months_breakdown = []
    balance = initial_amount #start with starting amount
    balance_boost = initial_amount_boost 
    current_date = start_date        
    interest_rate = annual_interest_rate / 100
    rate_per_period = interest_rate / periods_per_year 

    progress = 0
    inc_contri=0
    contribution_i=contribution
    contribution_i_intrs=0
    interest=0.0
    
    #less then current date
    current_datetime_now = datetime.now()
    is_single = 1

    if current_date > current_datetime_now:
        return ({
        'breakdown':months_breakdown,
        'next_contribution_date':None,
        'progress':progress,
        'total_balance':total_balance,
        'total_balance_xyz':total_balance_xyz,
        'goal_reached':goal_reached,
        'period':period,
        'is_single':is_single,
        'total_monthly_balance_xyz':total_monthly_balance_xyz,
        'total_balance_boost':total_balance_boost,
        'total_monthly_balance_boost':total_monthly_balance_boost
    })

    period += 1
    next_contribution_date = None
    if interest_type > 1:

        balance += contribution
        balance_boost+= contribution
        contribution_i_intrs = contribution
        interest = (balance * rate_per_period)
        balance += interest
        balance_boost+= interest
        contribution_i_intrs+=interest

    else:

        interest = (contribution * rate_per_period)
        contribution_i_intrs = interest + contribution
        balance += contribution_i_intrs
        balance_boost+= contribution_i_intrs

    progress = ((balance / goal_amount) * 100) if savings_strategy > 1 else 100

    month = int(current_date.strftime("%Y%m"))

    months_breakdown = {
            "period": period,
            "month": month,            
            "interest": interest,
            'interest_xyz':interest,
            "contribution": contribution,
            "contribution_i":contribution_i,
            "contribution_i_intrs":contribution_i_intrs,
            'contribution_i_intrs_xyz':contribution_i_intrs,
            "increase_contribution":0,
            "increase_contribution_prd":inc_contri,
            "total_balance": balance,
            "total_balance_xyz": balance,
            "progress": progress,
            "progress_xyz": progress,
            "contribution_date":current_date,
            "next_contribution_date": next_contribution_date           
        }
    
    if month == int(current_datetime_now.strftime('%Y%m')):
            total_monthly_balance_xyz+= contribution_i_intrs
            total_monthly_balance_boost+= contribution_i_intrs

    total_balance = balance
    total_balance_xyz = balance
    total_balance_boost = balance_boost

    if savings_strategy > 1 and balance >= goal_amount:
        progress = round(100,2)
        goal_reached = current_date
        next_contribution_date = None

    return ({
        'breakdown':months_breakdown,
        'next_contribution_date':next_contribution_date,
        'progress':math.floor(progress),
        'total_balance':total_balance,
        'total_balance_xyz':total_balance_xyz,
        'goal_reached':goal_reached,
        'period':period,
        'is_single':is_single,
        'total_monthly_balance_xyz':total_monthly_balance_xyz,
        'total_balance_boost':total_balance_boost,
        'total_monthly_balance_boost':total_monthly_balance_boost
    })
    
    


#compount breakdown
# Function to calculate breakdown based on frequency
def calculate_breakdown(initial_amount, 
                        contribution, 
                        annual_interest_rate, 
                        goal_amount, 
                        start_date, 
                        frequency, 
                        i_contribution=0,
                        period=0,
                        interest_type=1,
                        savings_strategy=2,
                        op_type=1,
                        initial_amount_boost=0,
                        total_monthly_balance_xyz=0
                        ):
   
    periods_per_year = FREQUENCY_MAP[frequency]

    total_balance = 0
    total_balance_xyz = 0
    total_balance_boost = 0
    goal_reached = None

    contribution = -contribution if op_type > 1 else contribution
    
    
    total_monthly_balance_boost = 0
    
    delta = get_delta(frequency)
    
    months_breakdown = []
    balance = initial_amount #start with starting amount
    balance_boost = initial_amount_boost
    current_date = start_date
        
    interest_rate = annual_interest_rate / 100    
    rate_per_period = interest_rate  / periods_per_year    

    next_contribution_date = current_date + delta
    progress = 0
    inc_contri=0
    contribution_i=0
    contribution_i_intrs=0    
    interest=0.0
    
    #less then current date
    current_datetime_now = datetime.now()
    is_single = 0

    if current_date > current_datetime_now:
        return ({
        'breakdown':months_breakdown,
        'next_contribution_date':None,
        'progress':progress,
        'total_balance':total_balance,
        'total_balance_xyz':total_balance_xyz,
        'goal_reached':goal_reached,
        'period':period,
        'is_single':is_single,
        'total_monthly_balance_xyz':total_monthly_balance_xyz,
        'total_balance_boost':total_balance_boost,
        'total_monthly_balance_boost':total_monthly_balance_boost
    })

    if current_datetime_now <= next_contribution_date:
        is_single = 1

        # Calculate next contribution date
        next_contribution_date = current_date + delta
                        
        period += 1
        #increase contribution by periodically
        inc_contri = period * i_contribution        
        #increase contribution end

        #contribution_with_increse
        contribution_i +=  contribution + inc_contri
        #end contribution_with_increase
        if interest_type > 1:

            balance += contribution_i
            balance_boost+= contribution_i
            contribution_i_intrs = contribution_i
            interest = (balance * rate_per_period)
            balance += interest
            balance_boost+= interest
            contribution_i_intrs+=interest

        else:

            interest = (contribution_i * rate_per_period)
            contribution_i_intrs = interest + contribution_i
            balance += contribution_i_intrs
            balance_boost+= contribution_i_intrs            

        
        # Calculate progress towards the goal
        progress = (balance / goal_amount) * 100

        month = int(current_date.strftime("%Y%m"))

        # Append the current breakdown data
        months_breakdown = {
            "period": period,
            "month": month,            
            "interest": interest,
            'interest_xyz':interest,
            "contribution": contribution,
            "contribution_i":contribution_i,
            "contribution_i_intrs":contribution_i_intrs,
            'contribution_i_intrs_xyz':contribution_i_intrs,
            "increase_contribution":i_contribution,
            "increase_contribution_prd":inc_contri,
            "total_balance": balance,
            "total_balance_xyz": balance,
            "progress": round(progress, 2),
            "progress_xyz": round(progress, 2),
            "contribution_date":current_date,
            "next_contribution_date": next_contribution_date           
        }

        if month == int(current_datetime_now.strftime('%Y%m')):            
            total_monthly_balance_xyz+= contribution_i_intrs
            total_monthly_balance_boost+= contribution_i_intrs
            
        


    # Calculate a date 10 years from the original current date
    limit_years = current_date + relativedelta(years=10)

    if next_contribution_date <= current_datetime_now:
        is_single = 0
        if savings_strategy > 1:
            while balance < goal_amount:            
                # Calculate next contribution date
                next_contribution_date = current_date + delta                                   
                period += 1
                #increase contribution by periodically
                inc_contri = period * i_contribution            
                #increase contribution end
                #contribution_with_increse
                contribution_i =  contribution + inc_contri
                #end contribution_with_increase
                if interest_type > 1:

                    balance += contribution_i
                    balance_boost+= contribution_i
                    contribution_i_intrs = contribution_i
                    interest = (balance * rate_per_period)
                    balance += interest
                    balance_boost+= interest
                    contribution_i_intrs+=interest

                else:

                    interest = (contribution_i * rate_per_period)
                    contribution_i_intrs = interest + contribution_i
                    balance += contribution_i_intrs
                    balance_boost+= contribution_i_intrs       
                
                # Calculate progress towards the goal
                progress = (balance / goal_amount) * 100

                if balance < 0:
                    break

                month = int(current_date.strftime("%Y%m"))
                
                # Append the current breakdown data
                months_breakdown.append({
                    "period": period,
                    "month": month,                
                    "interest": interest,
                    'interest_xyz':interest,
                    "contribution": contribution,
                    "contribution_i":contribution_i,
                    "contribution_i_intrs":contribution_i_intrs,
                    'contribution_i_intrs_xyz':contribution_i_intrs,
                    "increase_contribution":i_contribution,
                    "increase_contribution_prd":inc_contri,
                    "total_balance": balance,
                    "total_balance_xyz": balance,
                    "progress": round(progress, 2),
                    "progress_xyz": round(progress, 2),
                    "contribution_date":current_date,
                    "next_contribution_date": next_contribution_date           
                })
                if month == int(current_datetime_now.strftime('%Y%m')):                    
                    total_monthly_balance_xyz+= contribution_i_intrs
                    total_monthly_balance_boost+= contribution_i_intrs

                # Stop if the next contribution date exceeds the current date
                if next_contribution_date > current_datetime_now:
                    break

                if current_date > limit_years:
                    break
                
                # Move to the next period based on the contribution frequency
                current_date += delta

                #print(balance,'balance in loop')


            total_balance = balance
            total_balance_xyz = balance
            total_balance_boost = balance_boost

            

            if balance >= goal_amount:
                progress = round(100,2)
                goal_reached = next_contribution_date
                next_contribution_date = None
                
        else:

            while next_contribution_date <= current_datetime_now:            
                # Calculate next contribution date
                next_contribution_date = current_date + delta                                   
                period += 1
                #increase contribution by periodically
                inc_contri = period * i_contribution            
                #increase contribution end
                #contribution_with_increse
                contribution_i =  contribution + inc_contri
                #end contribution_with_increase
                if interest_type > 1:

                    balance += contribution_i
                    balance_boost+= contribution_i
                    contribution_i_intrs = contribution_i
                    interest = (balance * rate_per_period)
                    balance += interest
                    balance_boost+= interest
                    contribution_i_intrs+=interest

                else:

                    interest = (contribution * rate_per_period)
                    contribution_i_intrs = interest + contribution_i
                    balance += contribution_i_intrs
                    balance_boost+= contribution_i_intrs         
                
                # Calculate progress towards the goal
                progress = 100                
                month = int(current_date.strftime("%Y%m"))            
                # Append the current breakdown data
                months_breakdown.append({
                    "period": period,
                    "month": month,                
                    "interest": interest,
                    'interest_xyz':interest,
                    "contribution": contribution,
                    "contribution_i":contribution_i,
                    "contribution_i_intrs":contribution_i_intrs,
                    'contribution_i_intrs_xyz':contribution_i_intrs,
                    "increase_contribution":i_contribution,
                    "increase_contribution_prd":inc_contri,
                    "total_balance": balance,
                    "total_balance_xyz": balance,
                    "progress": round(progress, 2),
                    "progress_xyz": round(progress, 2),
                    "contribution_date":current_date,
                    "next_contribution_date": next_contribution_date           
                })
                if month == int(current_datetime_now.strftime('%Y%m')):                    
                    total_monthly_balance_xyz+= contribution_i_intrs
                    total_monthly_balance_boost+= contribution_i_intrs                

                if current_date > limit_years:
                    break

                # Move to the next period based on the contribution frequency
                current_date += delta

            total_balance = balance
            total_balance_xyz = balance
            total_balance_boost = balance_boost
            goal_reached = None

    
    return ({
        'breakdown':months_breakdown,
        'next_contribution_date':next_contribution_date,
        'progress':math.floor(progress),
        'total_balance':total_balance,
        'total_balance_xyz':total_balance_xyz,
        'goal_reached':goal_reached,
        'period':period,
        'is_single':is_single,
        'total_monthly_balance_xyz':total_monthly_balance_xyz,
        'total_balance_boost':total_balance_boost,
        'total_monthly_balance_boost':total_monthly_balance_boost
    })


def get_freq_month(balance,
                   contribution, 
                   interest_rate,
                   frequency,
                   start_date:date,
                   i_contribution=0,
                   interest_type=1 
                   ):
    
    if frequency < 1:
        raise ValueError("Frequency must be a positive integer.")
    
    periods_per_year = FREQUENCY_MAP[frequency]
    
    year, month = start_date.year, start_date.month
    last_day = calendar.monthrange(year, month)[1]
    end_of_month = date(year, month, last_day)
    

    days_remaining = (end_of_month - start_date).days + 1
    in_month_count = 1 + (days_remaining - 1) // frequency

    #print('year, month, last_day, end_of_month, days_remaining, in_month_count',year, month,last_day,end_of_month, days_remaining,in_month_count,(end_of_month - start_date).days, start_date)

    interest_rate = interest_rate / 100
    rate_per_period = interest_rate  / periods_per_year

    next_pay_date = start_date + timedelta(days=in_month_count * frequency)

    total_contribution = in_month_count * contribution    
    total_interest = in_month_count * rate_per_period
    total_i_contribution = in_month_count * i_contribution
    if interest_type > 1:
        balance += total_contribution + total_i_contribution
        interest = (balance * rate_per_period)
        balance += interest
    else:
        balance += total_contribution + total_interest + total_i_contribution

    #balance += total_contribution + total_interest + total_i_contribution
    return {
        #"count": in_month_count,
        "next_pay_date": next_pay_date,
        'balance':balance,
        'total_contribution':total_contribution,
        'interest_rate':interest_rate,
        'total_interest':total_interest,
        'i_contribution':i_contribution,
        'total_i_contribution':total_i_contribution,
        'period':in_month_count
    }

# Function to calculate breakdown based on frequency
def calculate_breakdown_future(initial_amount, contribution, annual_interest_rate, goal_amount, start_date, frequency,saving_boost=0,
                               saving_boost_date=None, i_contribution=0, period=0,repeat_saving_boost=None
):
    # n = 12  # Compounded monthly (for interest)
    # monthly_rate = annual_interest_rate / n  # Monthly interest rate (same across frequencies)

    total_balance = 0
    goal_reached = None
    
    delta = get_delta(frequency)
    
    months_breakdown = []
    balance = initial_amount
    
    current_date = start_date
    
    interest_rate = annual_interest_rate / 100

    # Adjust interest calculation for non-monthly contributions
    daily_rate = interest_rate / 365  # Daily interest rate based on the annual rate

    # Get the current date to stop if the current month is exceeded
    #current_month_end = datetime.now().replace(day=1) + relativedelta(months=1) - relativedelta(days=1)

    next_contribution_date = current_date + delta
    progress = 0
    inc_contri = 0
    
    #less then current date
    current_datetime_now = datetime.now()

    #print('balance check',balance)

    if next_contribution_date >= current_datetime_now and balance:

        #print('next and current and goal_amount',next_contribution_date,current_datetime_now, goal_amount)
    
        while balance < goal_amount:            
            

            # print('contribution',contribution)
            month_string = current_date.strftime('%Y-%m')

            #print('month string',month_string,saving_boost_date)
            
           
            saving_boost_contribution = None 
            if month_string == saving_boost_date:
                 #print('month==saving_boost',month_string,saving_boost_date)
                 #print(contribution, balance)
                 saving_boost_contribution = saving_boost + contribution
            #     #balance += saving_boost
                 #print('saving_boost_contribution',saving_boost_contribution)
            else:
                saving_boost_contribution = None
           

            #print('repeat_saving_boost',repeat_saving_boost)
            
            # Calculate next contribution date
            next_contribution_date = current_date + delta
            
            
            days_in_period = (next_contribution_date - current_date).days
            #print('days_in_period',days_in_period)
            interest = balance * (daily_rate * days_in_period)  # Interest calculated based on the days between contributions
            if saving_boost_contribution !=None:
                balance += interest + saving_boost_contribution
                # print('balance', balance)
            else:
                balance += interest + contribution
            period += 1

            if repeat_saving_boost!=None:
                balance += repeat_saving_boost
            
            #increase contribution by periodically
            #print('before i_contribution',i_contribution)
            inc_contri = period * i_contribution
            #print('i_contribution',inc_contri)
            balance += inc_contri
            #increase contribution end
            
            # Calculate progress towards the goal
            progress = (balance / goal_amount) * 100

            #print('balance, month',balance, month_string)

            if balance < 0:
                break
            
            # Append the current breakdown data
            months_breakdown.append({
                "period": period,
                "month": month_string,
                "month_word": current_date.strftime('%b, %Y'),
                "interest": round(interest, 2),
                "contribution": saving_boost_contribution+inc_contri if saving_boost_contribution !=None else contribution+inc_contri,
                "increase_contribution":i_contribution,
                "total_balance": round(balance, 2),
                "progress": round(progress, 2),
                "contribution_date":current_date,
                "next_contribution_date": next_contribution_date           
            })
            
            # Move to the next period based on the contribution frequency
            current_date = next_contribution_date

    total_balance = balance

    if balance >= goal_amount:
        goal_reached = next_contribution_date
        next_contribution_date = None
    if len(months_breakdown) > 0:
        # First, we need to sort the months_breakdown array by the 'month' key to use groupby
        months_breakdown_sorted = sorted(months_breakdown, key=itemgetter('month'))

        # Group the entries by 'month' and find the max 'total_balance' in each group
        max_balance_per_month = []

        for month, group in groupby(months_breakdown_sorted, key=itemgetter('month')):
            # Convert group to a list
            group_list = list(group)
            
            # Find the entry with the max total_balance in this group
            max_entry = max(group_list, key=lambda x: x['total_balance'])
            
            # Append the max entry for this month to the result array
            max_balance_per_month.append(max_entry)

        # Output the result
        if len(max_balance_per_month)> 0:
            months_breakdown  = max_balance_per_month
            #print(max_balance_per_month)
    
    return ({
        'breakdown':months_breakdown,
        'next_contribution_date':next_contribution_date,
        'progress':math.floor(progress),
        'total_balance':round(total_balance, 2),
        'goal_reached':goal_reached,
        'period':period
    })
