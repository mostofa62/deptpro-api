
import math
from typing import Any
from bson.objectid import ObjectId
import json
from datetime import datetime, timedelta
import os
#import enum
import jwt
import calendar

JWT_SECRET = os.environ["JWT_SECRET"]
key = JWT_SECRET
TOKEN_EXPIRATION = os.environ["TOKEN_EXPIRATION"]

class MongoJSONEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, datetime):
            return str(o)
        return json.JSONEncoder.default(self, o)
    
    def is_json(self,myjson:Any)->Any:
        
        try:
            myjson = json.loads(myjson)
        except ValueError as e:
            return False
        return myjson


def JWT_ENCODE(data):
    token = jwt.encode(data, key, algorithm="HS256")
    return token

def JWT_DECODE(token):    
    decoded = jwt.decode(token, key, algorithms="HS256")
    return decoded


def get_token_and_expiration(data):
    token = JWT_ENCODE(data)
    token_expired_at = datetime.now()+timedelta(minutes=datetime.now().minute+int(TOKEN_EXPIRATION))

    return (token, token_expired_at)

def decode_token(data):
    return JWT_DECODE(data)

# Enum for size units
'''
class SIZE_UNIT(enum.Enum):
   BYTES = 1
   KB = 2
   MB = 3
   GB = 4


def convert_unit(size_in_bytes, unit):
   """ Convert the size from bytes to other units like KB, MB or GB"""
   if unit == SIZE_UNIT.KB:
       return size_in_bytes/1024
   elif unit == SIZE_UNIT.MB:
       return size_in_bytes/(1024*1024)
   elif unit == SIZE_UNIT.GB:
       return size_in_bytes/(1024*1024*1024)
   else:
       return size_in_bytes
'''


def calculate_monthly_interest(balance, interest_rate):
    return round((balance * (interest_rate / 100)) / 12,2)


def calculate_paid_off_percentage(highest_balance, current_balance):
    if highest_balance == 0:
        return 0.0  # To handle division by zero if highest_balance is zero
    
    paid_off_percentage = ((highest_balance - current_balance) / highest_balance) * 100
    return paid_off_percentage

def are_floats_equal(a,b):
    return math.isclose(a, b, rel_tol=1e-9)


def convertStringTodate(date_string:str, format:str="%Y-%m-%d"):
    date_timestamp = None
    if date_string!=None and date_string!='':
        date_timestamp = datetime.strptime(date_string,format)

    return date_timestamp

def convertDateTostring(date_obj, format:str="%d %b, %Y"):
    date_string = None
    if date_obj!=None:
        date_string = date_obj.strftime(format)

    return date_string


def convertNumberToDate(num,format:str="%b, %Y"):
    year = int(str(num)[:4])
    month = int(str(num)[4:])
    date_obj = datetime(year, month, 1)
    return date_obj.strftime(format)  # "Feb 2025"


#income modules related
# Define a mapping from labels to the number of days per interval
REPEAT_INTERVALS = {
    'Daily': 1,
    'Weekly': 7,
    'BiWeekly': 14,
    'Monthly': 30,
    'Quarterly': 90,
    'Annually': 365,
    'None': float('inf')  # One-time payments
}



def calculate_total_monthly_gross_income(gross_input, boost, frequency, boost_frequency):
    """
    Calculate total monthly gross income based on the gross income, income boost, and their frequency.
    
    Parameters:
    - gross_input: Base income amount (e.g., $2000)
    - boost: Income boost amount (e.g., $500)
    - frequency: The interval between base income payments (e.g., 'weekly', 'monthly', 'quarterly', 'annually')
    - boost_frequency: The interval between boost payments (e.g., 'weekly', 'monthly', 'quarterly', 'annually')
    
    Returns:
    - Total monthly gross income normalized to 30 days.
    """
    
    """ # Frequency to day mapping
    frequency_to_days = {
        'daily': 1,
        'weekly': 7,
        'biweekly': 14,
        'monthly': 30,
        'quarterly': 90,
        'annually': 365
    } """
    
    # Convert frequency to days
    frequency_days = REPEAT_INTERVALS.get(frequency)
    boost_frequency_days = REPEAT_INTERVALS.get(boost_frequency)

    print(frequency_days, boost_frequency_days)
    
    # Raise an error if the frequency is not recognized
    if not frequency_days:
        raise ValueError(f"Invalid frequency in gross: {frequency}")
    if not boost_frequency_days:
        raise ValueError(f"Invalid boost frequency in gross: {boost_frequency}")
    
    # Normalize base income to a 30-day period
    normalized_gross_income = gross_input * (30 / frequency_days)
    
    # Normalize boost income to a 30-day period
    normalized_boost_income = boost * (30 / boost_frequency_days)
    
    # Total monthly gross income
    total_monthly_gross_income = normalized_gross_income + normalized_boost_income
    
    return total_monthly_gross_income

def calculate_total_monthly_net_income(net_input, boost, frequency, boost_frequency):
    """
    Calculate total monthly net income based on the net income, income boost, and their frequency.
    
    Parameters:
    - net_input: Base net income amount (e.g., $2000 after taxes/deductions)
    - boost: Income boost amount (e.g., $500 as a bonus or extra payment)
    - frequency: The interval between base net income payments (e.g., 'weekly', 'monthly', 'quarterly', 'annually')
    - boost_frequency: The interval between boost payments (e.g., 'weekly', 'monthly', 'quarterly', 'annually')
    
    Returns:
    - Total monthly net income normalized to 30 days.
    """
    
    # Frequency to day mapping
    """ frequency_to_days = {
        'daily': 1,
        'weekly': 7,
        'biweekly': 14,
        'monthly': 30,
        'quarterly': 90,
        'annually': 365
    } """
    
    # Convert frequency to days
    frequency_days = REPEAT_INTERVALS.get(frequency)
    boost_frequency_days = REPEAT_INTERVALS.get(boost_frequency)
    
    # Raise an error if the frequency is not recognized
    if not frequency_days:
        raise ValueError(f"Invalid frequency in net: {frequency}")
    if not boost_frequency_days:
        raise ValueError(f"Invalid boost frequency in net: {boost_frequency}")
    
    # Normalize base net income to a 30-day period
    normalized_net_income = net_input * (30 / frequency_days)
    
    # Normalize boost income to a 30-day period
    normalized_boost_income = boost * (30 / boost_frequency_days)
    
    # Total monthly net income
    total_monthly_net_income = normalized_net_income + normalized_boost_income
    
    return total_monthly_net_income





def calculate_total_income_with_repeat(monthly_gross_income, income_boost, repeat, repeat_boost, days=30):
    """
    Calculate total income considering repeat and repeat_boost values.
    - days: The number of days over which to calculate income (e.g., 30 for a month, 365 for a year).
    """
    total_gross_income = 0
    
    # Get the repeat interval in days for base income and income boost
    base_repeat_interval = REPEAT_INTERVALS.get(repeat['label'], float('inf'))
    boost_repeat_interval = REPEAT_INTERVALS.get(repeat_boost['label'], float('inf'))
    
    # Apply the base income based on its repeat value
    if base_repeat_interval < float('inf'):
        # Recurring income, calculate how many times it repeats in the given period
        repeat_times = days // base_repeat_interval
        total_gross_income = monthly_gross_income * repeat_times
    else:
        # One-time income, only apply once
        total_gross_income = monthly_gross_income

    # Apply the income boost based on its repeat_boost value
    if boost_repeat_interval < float('inf'):
        # Recurring boost, calculate how many times it repeats in the given period
        repeat_boost_times = days // boost_repeat_interval
        total_gross_income += income_boost * repeat_boost_times
    else:
        # One-time boost, only apply once
        total_gross_income += income_boost

    return total_gross_income



def calculate_income_month_count(pay_date):
    today = datetime.today()
    first_pay_date = pay_date

    month_count = (today.year - first_pay_date.year) * 12 + today.month - first_pay_date.month

    return month_count+1


# Helper function to calculate the boost based on frequency


def calculate_boost(current_date, first_pay_date, boost_frequency, boost_amount):
    if boost_frequency == 7:
        # Calculate if the current date is a multiple of 7 days from the first pay date
        if (current_date - first_pay_date).days % 7 == 0:
            return boost_amount
    elif boost_frequency == 14:
        # Calculate if the current date is a multiple of 14 days from the first pay date
        if (current_date - first_pay_date).days % 14 == 0:
            return boost_amount
    elif boost_frequency == 30:
        # Apply boost each month (ignore first month if needed by specific logic)
        if (current_date.month - first_pay_date.month) % 1 == 0:  # Ensure it's after the first month
            return boost_amount
    elif boost_frequency == 90:        
        # Apply boost every 3 months but skip the first month
        if (current_date.month - first_pay_date.month) % 3 == 0:            
            return boost_amount
    elif boost_frequency == 365:
        # Apply boost annually, skipping the first year if necessary
        if (current_date.year - first_pay_date.year) % 1 == 0:
            return boost_amount
    return 0


# Function to calculate the next payment date based on frequency
def add_time(current_date, frequency, repeat_count=1):
    if frequency == 30:
        month = current_date.month - 1 + repeat_count
        year = current_date.year + month // 12
        month = month % 12 + 1
        day = min(current_date.day, calendar.monthrange(year, month)[1])
        return current_date.replace(year=year, month=month, day=day)
    elif frequency == 90:
        return add_time(current_date, "monthly", 3 * repeat_count)
    elif frequency == 365:
        return current_date.replace(year=current_date.year + repeat_count)
    elif frequency == 7:
        return current_date + timedelta(weeks=repeat_count)
    elif frequency == 14:
        return current_date + timedelta(weeks=2 * repeat_count)