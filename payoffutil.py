from dateutil.relativedelta import relativedelta  # This handles month increments correctly


def calculate_amortization(balance, interest_rate, monthly_payment, credit_limit, current_date, cashflow_amount):
    amortization_schedule = []

    # Convert interest rate to decimal
    interest_rate_decimal = interest_rate / 100
    limit_years = current_date + relativedelta(years=100)
    is_first_month = True

    while balance > 0 and current_date <= limit_years:
        # Cap balance by credit limit
        if credit_limit is not None:
            balance = min(balance, credit_limit)

        # Calculate interest for the month
        interest = balance * interest_rate_decimal / 12

        # Apply cashflow only in the first month
        extra_payment = 0
        if is_first_month:
            extra_payment = min(cashflow_amount, ((balance+ interest) - monthly_payment))
            print('extra_payment',extra_payment)
            cashflow_amount -= extra_payment
        payment = monthly_payment + extra_payment

        # Cap payment to total due (avoid overpaying)
        total_due = balance + interest
        if payment > total_due:
            payment = total_due

        # Principal = payment - interest
        principal_payment = max(payment - interest, 0)
        balance = max(balance - principal_payment, 0)

        amortization_schedule.append({
            'month': current_date.strftime("%b %Y"),
            'month_debt_free': current_date,
            'balance': round(balance, 2),
            'total_payment': round(payment, 2),
            'snowball_amount': round(principal_payment, 2),
            'interest': round(interest, 2),
            'principal': round(principal_payment, 2)
        })

        is_first_month = False
        current_date += relativedelta(months=1)

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