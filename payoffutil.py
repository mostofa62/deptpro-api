from dateutil.relativedelta import relativedelta  # This handles month increments correctly

def calculate_amortization(balance, interest_rate, monthly_payment, credit_limit, current_date, monthly_budget):
    amortization_schedule = []
    
    # Convert interest rate to decimal
    interest_rate_decimal = interest_rate / 100
    
    # Calculate a date max 50 years from the original current date
    limit_years = current_date + relativedelta(years=100)
    
    while balance > 0:
        balance = min(balance, credit_limit)
        
        # Calculate interest for the current balance
        interest = balance * interest_rate_decimal / 12
        
        # Calculate the maximum payment we can make considering the monthly budget
        payment = min(monthly_payment, monthly_budget)
        
        # Calculate snowball amount
        snowball_amount = min(payment, balance + interest) - interest
        
        # Calculate principal payment
        principle = snowball_amount
        principle = min(principle, balance)
        balance -= principle
        
        if balance < 0:
            balance = 0
        
        # Calculate total payment (principle + interest)
        total_payment = principle + interest
        
        # Record this month's data
        amortization_schedule.append({
            'month': current_date.strftime("%b %Y"),
            'month_debt_free': current_date,
            'balance': round(balance, 2),
            'total_payment': round(total_payment, 2),
            'snowball_amount': round(snowball_amount, 2),
            'interest': round(interest, 2),
            'principle': round(principle, 2)
        })

        #print('current_date',current_date)
        if current_date > limit_years:
            break
        
        # Move to the next month using relativedelta to increment by one month
        current_date += relativedelta(months=1)
        
        
    
    return amortization_schedule


# Define sorting method (for example, Debt Snowball - lowest balance first)
def sort_debts_payoff(debts, method):
    if method == 1:  # Debt Snowball - lowest balance first
        return sorted(debts, key=lambda x: x['balance'])
    elif method == 2:  # Debt Avalanche - highest interest rate first
        return sorted(debts, key=lambda x: x['interest_rate'], reverse=True)
    elif method == 11:  # Hybrid (Debt Ratio)
        return sorted(debts, key=lambda x: x['balance'] / (x['interest_rate'] + 1))
    elif method == 13:  # Cash Flow Index (CFI)
        return sorted(debts, key=lambda x: x['balance'] / (x['monthly_payment'] + 1))
    elif method == 3:  # Custom - highest sort number first
        return sorted(debts, key=lambda x: x['balance'], reverse=True)
    elif method == 4:  # Custom - lowest sort number first
        return sorted(debts, key=lambda x: x['balance'])
    elif method == 5:  # Highest monthly payment first
        return sorted(debts, key=lambda x: x['monthly_payment'], reverse=True)
    elif method == 8:  # Highest credit utilization first
        return sorted(debts, key=lambda x: x['balance'] / (x['credit_limit'] + 1), reverse=True)
    elif method == 10:  # Highest monthly interest paid first
        return sorted(debts, key=lambda x: x['monthly_interest'], reverse=True)
    elif method == 12:  # Lowest interest rate paid first
        return sorted(debts, key=lambda x: x['interest_rate'])
    else:
        raise ValueError("Unknown debt payoff method")