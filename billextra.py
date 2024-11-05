import os
from flask import Flask,request,jsonify, json
#from flask_cors import CORS, cross_origin
from app import app
from db import my_col,myclient
from bson.objectid import ObjectId
from bson.json_util import dumps
import re
from util import *
from datetime import datetime,timedelta
from decimal import Decimal


client = myclient
collection = my_col('bill_extra')
bill_accounts = my_col('bill_accounts')

extra_type = [
    # {'value':1, 'label':'Paydown Boost'},
    # {'value':2, 'label':'Debt Purchase'},
    {'value':1, 'label':'Bill Purchase'},
    {'value':2, 'label':'Withdrawl'},
    

]

@app.route('/api/bill-extra-dropdown', methods=['GET'])
def bill_extra_dropdown():

    

    bill_account = bill_accounts.find(
        {

            "deleted_at":None,
            #"user_id": ObjectId(user_id),            
            "closed_at":None,
        },
        {
            '_id': 1, 
            'name': 1, 
            'next_due_date':1,
            'user_id': 1, 
            'repeat':1
        }
        )
    bill_accounts_list  = []
    for todo in bill_account:
        name  =  todo['name']
        bill_accounts_list.append({
            'value':str(todo['_id']),
            'label':name,
            'pay_date_boost':convertDateTostring(todo['next_due_date'],"%Y-%m-%d")
        })
    return jsonify({
        'extra_type': extra_type,
        'bill_accounts_list':bill_accounts_list        
        
    })
