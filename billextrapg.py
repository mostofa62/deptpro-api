import os
from flask import Flask,request,jsonify, json
#from flask_cors import CORS, cross_origin
from models import BillAccounts
from app import app
from util import *
from pgutils import ExtraType
from dbpg import db


@app.route('/api/bill-amount-validationpg',methods=['POST'])
def save_amount_validation_pg():
    if request.method == 'POST':
        data = json.loads(request.data)
        bill_account_id = data['bill_acc_id']
        amount = float(data.get("amount", 0)) 

        op_type  = int(data['op_type'])

        if op_type < ExtraType[1]['value']:
            

            return({
            "isValid":True,
            #"message":bill_acc_data['current_amount']
            }),200

        
        bill_acc_data = (
            db.session.query(BillAccounts.current_amount)
            .filter(BillAccounts.id == bill_account_id)            
            .first()
        )

        isValid = False  if amount > bill_acc_data.current_amount else True

        if isValid:

            return({
            "isValid":isValid,
            #"message":bill_acc_data['current_amount']
        }),200
        else:
            return({
            "isValid":isValid,
            "current_amount":bill_acc_data.current_amount
        }),400

        

@app.route('/api/bill-extra-dropdownpg/<int:user_id>', methods=['GET'])
def bill_extra_dropdown_pg(user_id:int):
    # Query the BillAccounts model with filters for deleted_at and closed_at
    bill_accounts_query = (
        db.session.query(BillAccounts.id, BillAccounts.name, BillAccounts.next_due_date)
        .filter(BillAccounts.user_id == user_id)
        .filter(BillAccounts.deleted_at.is_(None))
        .filter(BillAccounts.closed_at.is_(None))
        .all()
    )
    
    bill_accounts_list = []
    for account in bill_accounts_query:
        bill_accounts_list.append({
            'value': account.id,
            'label': account.name,
            'pay_date_boost': convertDateTostring(account.next_due_date,"%Y-%m-%d")
        })
    
    return jsonify({
        'extra_type': ExtraType,  # Replace this with the actual value
        'bill_accounts_list': bill_accounts_list
    })

