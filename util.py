
import math
from typing import Any
from bson.objectid import ObjectId
import json
from datetime import datetime
import os
#import enum
import jwt

JWT_SECRET = os.environ["JWT_SECRET"]
key = JWT_SECRET

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
    date_string = ''
    if date_obj!=None:
        date_string = date_obj.strftime(format)

    return date_string

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
