from dateutil.relativedelta import relativedelta  # This handles month increments correctly


def calculate_amortization(balance, interest_rate, monthly_payment, credit_limit, current_date, cashflow_amount):
    amortization_schedule = []

    # Convert interest rate to decimal
    interest_rate_decimal = interest_rate / 100

    # Set a maximum date limit (100 years from the current date)
    #limit_date = current_date.replace(year=current_date.year + 100)
    limit_years = current_date + relativedelta(years=100)

    while balance > 0 and current_date <= limit_years:
        # Ensure balance doesn't exceed the credit limit
        if credit_limit is not None:
            balance = min(balance, credit_limit)

        # Calculate interest for the current balance
        interest = balance * interest_rate_decimal / 12

        # Calculate the payment this month (principal + interest)
        payment = monthly_payment + min(cashflow_amount, balance)

        # Calculate the snowball amount (portion going to principal after interest)
        snowball_amount = payment - interest

        # If cashflow is greater than the balance, we apply it entirely to the balance
        if cashflow_amount >= balance:
            snowball_amount = balance  # Paying off the balance
            balance = 0  # Debt is fully paid off
        else:
            balance -= snowball_amount  # Decrease balance by snowball amount

        total_payment = snowball_amount + interest

        if balance <0:
            balance = 0

        # Record this month's data
        amortization_schedule.append({
            'month': current_date.strftime("%b %Y"),
            'month_debt_free': current_date,
            'balance': round(balance, 2),
            'total_payment': round(total_payment, 2),
            'snowball_amount': round(snowball_amount, 2),
            'interest': round(interest, 2),
            'principal': round(snowball_amount, 2)
        })

        # Decrease cashflow for the current month after usage
        cashflow_used = min(cashflow_amount, balance)
        cashflow_amount -= cashflow_used       
        
        current_date += relativedelta(months=1)
        # # Manually increment the date by 1 month
        # if current_date.month == 12:
        #     current_date = current_date.replace(year=current_date.year + 1, month=1)
        # else:
        #     current_date = current_date.replace(month=current_date.month + 1)

    return amortization_schedule, cashflow_amount



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