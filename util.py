
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
