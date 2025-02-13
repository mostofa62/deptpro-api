from collections import defaultdict
import os
from flask import Flask,request,jsonify, json
from sqlalchemy import func
#from flask_cors import CORS, cross_origin
from models import Income, IncomeBoost, IncomeMonthlyLog, IncomeSourceType, IncomeTransaction
from incomeutil import calculate_breakdown_future,generate_new_transaction_data_for_future_income_boost, generate_new_transaction_data_for_future_income_v1, generate_new_transaction_data_for_income, generate_unique_id
from app import app
from db import my_col,myclient
from bson.objectid import ObjectId
from bson.json_util import dumps
import re
from util import *
from datetime import datetime,timedelta
from decimal import Decimal
from dbpg import db

def transaction_previous(id: int, column: str = 'income_id'):
    twelve_months_ago = datetime.now() - timedelta(days=365)

    # If column is 'user_id', we need to get income_id-wise maximum total_net_for_period, and then sum it by month
    if column == 'user_id':
        # Get the max total_net_for_period for each income_id and month, and then sum those by month
        subquery = db.session.query(
            IncomeTransaction.month,
            IncomeTransaction.income_id,
            func.max(IncomeTransaction.total_net_for_period).label('max_total_net_for_period'),
            func.min(IncomeTransaction.month_word).label('month_word')
        ).filter(
            IncomeTransaction.pay_date >= twelve_months_ago,
            IncomeTransaction.deleted_at == None,
            IncomeTransaction.closed_at == None,
            IncomeTransaction.user_id == id  # Here we filter by user_id
        ).group_by(
            IncomeTransaction.month,
            IncomeTransaction.income_id
        ).subquery()

        # Now sum those max_total_net_for_periods by month
        result = db.session.query(
            subquery.c.month,
            func.sum(subquery.c.max_total_net_for_period).label('total_balance_net'),
            func.min(subquery.c.month_word).label('month_word')
        ).group_by(
            subquery.c.month
        ).order_by(
            subquery.c.month.asc()
        ).limit(12)

    else:
        # Get the max total_net_for_period for each month and income_id
        subquery = db.session.query(
            IncomeTransaction.month,
            IncomeTransaction.income_id,
            func.max(IncomeTransaction.total_net_for_period).label('total_balance_net'),
            func.min(IncomeTransaction.month_word).label('month_word')
        ).filter(
            IncomeTransaction.pay_date >= twelve_months_ago,
            IncomeTransaction.deleted_at == None,
            IncomeTransaction.closed_at == None,
            IncomeTransaction.income_id == id  # Filter dynamically by income_id
        ).group_by(
            IncomeTransaction.month,
            IncomeTransaction.income_id
        ).subquery()

        # Now, we just return the results directly without summing
        result = db.session.query(
            subquery.c.month,
            subquery.c.total_balance_net,
            subquery.c.month_word
        ).order_by(
            subquery.c.month.asc()
        ).limit(12)


    # Prepare the result
    year_month_wise_counts = []
    for row in result:
        year_month_wise_counts.append({
            'year_month_word': row.month_word,
            'total_balance_net': row.total_balance_net
        })

    return year_month_wise_counts


    
    


@app.route('/api/income-transactions-previouspgu/<int:user_id>', methods=['GET'])
def income_transactions_previous_pgu(user_id:int):

    year_month_wise_counts = transaction_previous(user_id,'user_id')

    # 7. Get the total monthly balance
    total_monthly_balance = 0    
   

    return jsonify({
        "payLoads":{                        
            "year_month_wise_counts":year_month_wise_counts,            
            "total_monthly_balance":total_monthly_balance

        }        
    })

@app.route('/api/income-transactions-previouspg/<int:income_id>', methods=['GET'])
def income_transactions_previous_pg(income_id:int):

    year_month_wise_counts = transaction_previous(income_id)

    # 7. Get the total monthly balance
    total_monthly_balance = 0
    if income_id is not None:
        income_monthly_log_data = db.session.query(IncomeMonthlyLog).filter_by(income_id=income_id).first()
        if income_monthly_log_data is not None:
            total_monthly_balance = income_monthly_log_data.total_monthly_net_income
   

    return jsonify({
        "payLoads":{                        
            "year_month_wise_counts":year_month_wise_counts,            
            "total_monthly_balance":total_monthly_balance

        }        
    })




@app.route('/api/income-transactionspg/<int:income_id>', methods=['POST'])
def list_income_transactions_pg(income_id: int):
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)

    # Create a base query for IncomeTransaction model
    query = db.session.query(IncomeTransaction).filter(
        IncomeTransaction.income_id == income_id,
        IncomeTransaction.income_boost_id == None,
        IncomeTransaction.deleted_at == None,
        IncomeTransaction.closed_at == None
    )

    # Get the total count of records matching the query
    total_count = query.count()

    # Sorting parameters: Here we're sorting by 'pay_date' in descending order
    query = query.order_by(IncomeTransaction.pay_date.desc())

    # Pagination
    query = query.offset(page_index * page_size).limit(page_size)

    

    # Execute the query and get the results
    data_list = query.all()

    # Process the result to format dates
    formatted_data = []
    for todo in data_list:
        formatted_todo = {
            'id':todo.id,            
            'total_gross_for_period':todo.total_gross_for_period,
            'total_net_for_period':todo.total_net_for_period,
            'month_word':todo.month_word,
            'pay_date_word': convertDateTostring(todo.pay_date),
            #'pay_date': convertDateTostring(todo.pay_date, "%Y-%m-%d"),
            'next_pay_date_word': convertDateTostring(todo.next_pay_date),
            #'next_pay_date': convertDateTostring(todo.next_pay_date, "%Y-%m-%d"),
           
        }
        formatted_data.append(formatted_todo)

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size

    return jsonify({
        'rows': formatted_data,
        'pageCount': total_pages,
        'totalRows': total_count,
    })



@app.route('/api/income-boost-transactionspg/<int:income_id>', methods=['POST'])
def list_income_boost_transactions_pg(income_id:int):
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)
       

    # Create a base query for IncomeTransaction model
    query = db.session.query(
        IncomeTransaction.id,
        IncomeTransaction.gross_income,
        IncomeTransaction.total_gross_for_period,
        IncomeTransaction.pay_date,
        IncomeTransaction.next_pay_date,
        IncomeTransaction.month_word,
        IncomeBoost.earner.label('income_boost')
        ).filter(
        IncomeTransaction.income_id == income_id,
        IncomeTransaction.income_boost_id != None,
        IncomeTransaction.deleted_at == None,
        IncomeTransaction.closed_at == None
    ).join(IncomeBoost, IncomeTransaction.income_boost_id == IncomeBoost.id, isouter=True)

    # Get the total count of records matching the query
    total_count = query.count()

    # Sorting parameters: Here we're sorting by 'pay_date' in descending order
    query = query.order_by(IncomeTransaction.pay_date.desc())

    # Pagination
    query = query.offset(page_index * page_size).limit(page_size)

    

    # Execute the query and get the results
    data_list = query.all()

    # Process the result to format dates
    formatted_data = []
    for todo in data_list:
        formatted_todo = {
            'id':todo.id,
            'income_boost':todo.income_boost if todo.income_boost else None,            
            'contribution':todo.gross_income,
            'total_balance':todo.total_gross_for_period,
            'month_word':todo.month_word,
            'contribution_date_word': convertDateTostring(todo.pay_date),
            'contribution_date': convertDateTostring(todo.pay_date, "%Y-%m-%d"),
            'next_pay_date_word': convertDateTostring(todo.next_pay_date),
            'next_pay_date_boost': convertDateTostring(todo.next_pay_date, "%Y-%m-%d"),
           
        }
        formatted_data.append(formatted_todo)

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size
   
    
    return jsonify({
        'rows': formatted_data,
        'pageCount': total_pages,
        'totalRows': total_count,
    })




@app.route('/api/income-typewise-infopg/<int:user_id>', methods=['GET'])
def get_typewise_income_info_pg(user_id:int):

    # Get current month in 'YYYY-MM' format
    current_month_str = datetime.now().strftime("%Y-%m")

    #print('current_month_str',current_month_str)

    query = db.session.query(
        Income.income_source_id.label('id'),
        IncomeSourceType.name.label("name"),
        func.sum(IncomeTransaction.net_income).label("balance"),
        func.count(Income.income_source_id).label('count'),
    ).join(Income, IncomeTransaction.income_id == Income.id) \
     .join(IncomeSourceType, Income.income_source_id == IncomeSourceType.id) \
     .filter(
         IncomeTransaction.month == current_month_str,
         Income.user_id == user_id  # Filter by user_id
     ) \
     .group_by(
         Income.income_source_id,
         IncomeSourceType.name
     )
    
    #print('query',query)


    results = query.all()

   

    income_source_type_counts = [
        {"_id": row.id, "name": row.name, "balance": row.balance, "count": row.count}
        for row in results
    ]

    # Get total net_income sum
    total_balance = sum(row.balance for row in results)

    # Count of unique IncomeSourceTypes
    total_income_source_type = len(results)

    # List of IncomeSourceType names
    income_source_type_names = {row.id: row.name for row in results}

    

    return jsonify({
        "payLoads":{            
            "income_source_type_counts":income_source_type_counts,
            "total_income_source_type":total_income_source_type,
            "total_balance":total_balance,
            "income_source_type_names":income_source_type_names


        }        
    })

