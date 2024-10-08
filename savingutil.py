from datetime import datetime
import math
from dateutil.relativedelta import relativedelta

#compount breakdown
# Function to calculate breakdown based on frequency
def calculate_breakdown(initial_amount, contribution, annual_interest_rate, goal_amount, start_date, frequency):
    # n = 12  # Compounded monthly (for interest)
    # monthly_rate = annual_interest_rate / n  # Monthly interest rate (same across frequencies)

    total_balance = 0
    goal_reached = None
    
    # Determine the time interval for the contributions
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
    
    months_breakdown = []
    balance = initial_amount
    month = 0
    current_date = start_date
    
    interest_rate = annual_interest_rate / 100

    # Adjust interest calculation for non-monthly contributions
    daily_rate = interest_rate / 365  # Daily interest rate based on the annual rate

    # Get the current date to stop if the current month is exceeded
    #current_month_end = datetime.now().replace(day=1) + relativedelta(months=1) - relativedelta(days=1)

    next_contribution_date = current_date + delta
    progress = 0
    
    #less then current date
    current_datetime_now = datetime.now()

    if next_contribution_date <= current_datetime_now:
    
        while balance < goal_amount:
            
            # Calculate next contribution date
            next_contribution_date = current_date + delta
            
            
            days_in_period = (next_contribution_date - current_date).days
            interest = balance * (daily_rate * days_in_period)  # Interest calculated based on the days between contributions
            
            balance += interest + contribution
            month += 1
            
            # Calculate progress towards the goal
            progress = (balance / goal_amount) * 100
            
            # Append the current breakdown data
            months_breakdown.append({
                "period": month,
                "month": current_date.strftime('%Y-%m'),
                "month_word": current_date.strftime('%b, %Y'),
                "interest": round(interest, 2),
                "contribution": contribution,
                "total_balance": round(balance, 2),
                "progress": round(progress, 2),
                "contribution_date":current_date,
                "next_contribution_date": next_contribution_date           
            })

            # Stop if the next contribution date exceeds the current date
            if next_contribution_date > current_datetime_now:
                break
            
            # Move to the next period based on the contribution frequency
            current_date += delta


    total_balance = balance

    if balance >= goal_amount:
        goal_reached = next_contribution_date
        next_contribution_date = None
    
    return ({
        'breakdown':months_breakdown,
        'next_contribution_date':next_contribution_date,
        'progress':math.floor(progress),
        'total_balance':round(total_balance, 2),
        'goal_reached':goal_reached
    })




# Function to calculate breakdown based on frequency
def calculate_breakdown_future(initial_amount, contribution, annual_interest_rate, goal_amount, start_date, frequency):
    # n = 12  # Compounded monthly (for interest)
    # monthly_rate = annual_interest_rate / n  # Monthly interest rate (same across frequencies)

    total_balance = 0
    goal_reached = None
    
    # Determine the time interval for the contributions
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
    
    months_breakdown = []
    balance = initial_amount
    month = 0
    current_date = start_date
    
    interest_rate = annual_interest_rate / 100

    # Adjust interest calculation for non-monthly contributions
    daily_rate = interest_rate / 365  # Daily interest rate based on the annual rate

    # Get the current date to stop if the current month is exceeded
    #current_month_end = datetime.now().replace(day=1) + relativedelta(months=1) - relativedelta(days=1)

    next_contribution_date = current_date + delta
    progress = 0
    
    #less then current date
    current_datetime_now = datetime.now()

    if next_contribution_date >= current_datetime_now:
    
        while balance < goal_amount:
            
            # Calculate next contribution date
            next_contribution_date = current_date + delta
            
            
            days_in_period = (next_contribution_date - current_date).days
            interest = balance * (daily_rate * days_in_period)  # Interest calculated based on the days between contributions
            
            balance += interest + contribution
            month += 1
            
            # Calculate progress towards the goal
            progress = (balance / goal_amount) * 100
            
            # Append the current breakdown data
            months_breakdown.append({
                "period": month,
                "month": current_date.strftime('%Y-%m'),
                "month_word": current_date.strftime('%b, %Y'),
                "interest": round(interest, 2),
                "contribution": contribution,
                "total_balance": round(balance, 2),
                "progress": round(progress, 2),
                "contribution_date":current_date,
                "next_contribution_date": next_contribution_date           
            })
            
            # Move to the next period based on the contribution frequency
            current_date += delta

    total_balance = balance

    if balance >= goal_amount:
        goal_reached = next_contribution_date
        next_contribution_date = None
    
    return ({
        'breakdown':months_breakdown,
        'next_contribution_date':next_contribution_date,
        'progress':math.floor(progress),
        'total_balance':round(total_balance, 2),
        'goal_reached':goal_reached
    })
