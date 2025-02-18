import os
from flask import Flask,request,jsonify, json
from sqlalchemy import func
#from flask_cors import CORS, cross_origin
from app import app

import re
from util import *
from datetime import datetime,timedelta
from decimal import Decimal

from models import DebtAccounts, DebtType, DebtTransactions
from dbpg import db


@app.route("/api/debt-projectionpg/<int:userid>", methods=['GET'])
def debt_projection_pg(userid:int):


    #allocation 
    # Get current month in 'YYYY-MM' format
    current_month_str = datetime.now().strftime("%Y-%m")

    query = db.session.query(
        DebtAccounts.debt_type_id.label('id'),
        DebtType.name.label("name"),
        func.sum(DebtTransactions.amount).label("balance"),
        func.count(DebtAccounts.debt_type_id).label('count'),
    ).join(DebtAccounts, DebtTransactions.debt_acc_id == DebtAccounts.id) \
     .join(DebtType, DebtAccounts.debt_type_id == DebtType.id) \
     .filter(
         func.to_char(DebtTransactions.trans_date, 'YYYY-MM') == current_month_str,
         DebtAccounts.user_id == userid  # Filter by user_id
     ) \
     .group_by(
         DebtAccounts.debt_type_id,
         DebtType.name
     )
    
    results = query.all()

    total_balance = 0
    total_bill_type = 0
    debt_type_names = {}
    bill_type_bill_counts = []

    for row in results:
        total_balance += row.balance
        total_bill_type += 1
        debt_type_names[row.id] = row.name
        bill_type_bill_counts.append({"id": row.id, "name": row.name, "balance": row.balance, "count": row.count})



    return jsonify({
        "payLoads":{

            "debt_type_debt_counts":bill_type_bill_counts,
            "total_dept_type":total_bill_type,
            "total_balance":total_balance,
            "debt_type_names":debt_type_names,            
            
            "debt_type_ammortization":[],
            #"bill_type_ammortization":normalized_data,
            "data":[]            
            
        }        
    })