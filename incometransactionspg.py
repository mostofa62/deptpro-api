from collections import defaultdict
import os
from flask import Flask,request,jsonify, json
from sqlalchemy import String, and_, cast, func
#from flask_cors import CORS, cross_origin
from models import Income, IncomeBoost, IncomeMonthlyLog, IncomeSourceType, IncomeTransaction
from incomeutil import calculate_breakdown_future,generate_new_transaction_data_for_future_income_boost, generate_new_transaction_data_for_future_income_v1, generate_new_transaction_data_for_income, generate_unique_id
from app import app

import re
from util import *
from datetime import datetime,timedelta
from decimal import Decimal
from dbpg import db

def transaction_previous(id: int, column: str = 'income_id'):
    twelve_months_ago = datetime.now() - timedelta(days=365)
    year_month_wise_counts = []
    result = None
    session = db.session
    try:
        # If column is 'user_id', we need to get income_id-wise maximum total_net_for_period, and then sum it by month
        if column == 'user_id':
            # Get the max total_net_for_period for each income_id and month, and then sum those by month
            subquery = session.query(
                IncomeTransaction.month_number,
                IncomeTransaction.income_id,
                func.max(IncomeTransaction.total_net_for_period).label('max_total_net_for_period'),
                func.min(IncomeTransaction.month_number).label('month_min')
            ).join(Income, 
                and_(
                Income.id == IncomeTransaction.income_id,
                Income.commit == IncomeTransaction.commit,
                )
                ).filter(
                IncomeTransaction.pay_date >= twelve_months_ago,            
                Income.deleted_at == None,  # Filter for deleted_at == None
                Income.closed_at == None,
                IncomeTransaction.user_id == id  # Here we filter by user_id
            ).group_by(
                IncomeTransaction.month_number,
                IncomeTransaction.income_id
            ).subquery()

            # Now sum those max_total_net_for_periods by month
            result = session.query(
                subquery.c.month_number,
                func.sum(subquery.c.max_total_net_for_period).label('total_balance_net'),
                #func.min(subquery.c.month_number).label('month_min')
                func.to_char(  # Apply formatting to the minimum month_number
                    func.to_date(cast(func.min(subquery.c.month_min), String), 'YYYYMM'),
                    'Mon, YYYY'
                ).label('year_month_word')
            ).group_by(
                subquery.c.month_number
            ).order_by(
                subquery.c.month_number.asc()
            ).limit(12)

            

        else:
            # Get the max total_net_for_period for each month and income_id
            subquery = session.query(
                IncomeTransaction.month_number,
                IncomeTransaction.income_id,
                func.max(IncomeTransaction.total_net_for_period).label('total_balance_net'),
                func.min(IncomeTransaction.month_number).label('month_min')
            ).join(Income, 
                and_(
                Income.id == IncomeTransaction.income_id,
                Income.commit == IncomeTransaction.commit,
                )
                ).filter(
                IncomeTransaction.pay_date >= twelve_months_ago,            
                Income.deleted_at == None,  # Filter for deleted_at == None
                Income.closed_at == None,
                IncomeTransaction.income_id == id  # Filter dynamically by income_id
            ).group_by(
                IncomeTransaction.month_number,
                IncomeTransaction.income_id
            ).subquery()

            # Now, we just return the results directly without summing
            result = session.query(
                subquery.c.month_number,
                subquery.c.total_balance_net,
                #subquery.c.month_number.label('month_min')
                func.to_char(
                    func.to_date(subquery.c.month_number.cast(String), 'YYYYMM'), 
                    'Mon, YYYY')
                    .label('year_month_word'),

            ).order_by(
                subquery.c.month_number.asc()
            ).limit(12)


            
        for row in result:
            year_month_wise_counts.append({
                'year_month_word': row.year_month_word,
                'total_balance_net': row.total_balance_net
            })
        
        
    except Exception as e:
        #return year_month_wise_counts
        year_month_wise_counts = []

    finally:
        session.close()

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
    session = db.session
    try:
        # Create a base query for IncomeTransaction model
        query = session.query(
            IncomeTransaction.id,
            IncomeTransaction.total_gross_for_period,
            IncomeTransaction.total_net_for_period,
            IncomeTransaction.month_number,
            IncomeTransaction.pay_date,
            IncomeTransaction.next_pay_date            
        )\
        .join(Income, 
                and_(
                Income.id == IncomeTransaction.income_id,
                Income.commit == IncomeTransaction.commit,
                )
                )\
        .filter(
            IncomeTransaction.income_id == income_id,       
            IncomeTransaction.income_boost_id == None,
            Income.deleted_at == None,  # Filter for deleted_at == None
            Income.closed_at == None,
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
                'month_word':convertNumberToDate(todo.month_number),
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
    
    except Exception as e:
        return jsonify({
            'rows': [],
            'pageCount': 0,
            'totalRows': 0,
        })

    finally:
        session.close()



@app.route('/api/income-boost-transactionspg/<int:income_id>', methods=['POST'])
def list_income_boost_transactions_pg(income_id:int):
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)
       
    session = db.session
    try:
        # Create a base query for IncomeTransaction model
        query = session.query(
            IncomeTransaction.id,
            IncomeTransaction.gross_income,
            IncomeTransaction.total_gross_for_period,
            IncomeTransaction.pay_date,
            IncomeTransaction.next_pay_date,
            IncomeTransaction.month_number,
            IncomeBoost.earner.label('income_boost')
            ).join(Income, 
                and_(
                Income.id == IncomeTransaction.income_id,
                Income.commit == IncomeTransaction.commit,
                )
                ).filter(
            IncomeTransaction.income_id == income_id,
            IncomeTransaction.income_boost_id != None,
            Income.deleted_at == None,  # Filter for deleted_at == None
            Income.closed_at == None,
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
                'month_word':convertNumberToDate(todo.month_number),
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

    except Exception as e:
        return jsonify({
            'rows': [],
            'pageCount': 0,
            'totalRows': 0,
        })

    finally:
        session.close()


@app.route('/api/income-typewise-infopg/<int:user_id>', methods=['GET'])
def get_typewise_income_info_pg(user_id:int):

    # Get current month in 'YYYY-MM' format
    #current_month_str = datetime.now().strftime("%Y-%m")
    current_month_number = int(datetime.now().strftime('%Y%m'))
    print('current_month_number',current_month_number)

    session = db.session
    try:

        #print('current_month_str',current_month_str)

        query = db.session.query(
            Income.income_source_id.label('id'),
            IncomeSourceType.name.label("name"),
            func.sum(IncomeTransaction.net_income).label("balance"),
            func.count(Income.income_source_id).label('count'),
        ).join(Income, 
                and_(
                Income.id == IncomeTransaction.income_id,
                Income.commit == IncomeTransaction.commit,
                )
                ) \
        .join(IncomeSourceType, Income.income_source_id == IncomeSourceType.id) \
        .filter(
            IncomeTransaction.month_number == current_month_number,
            Income.user_id == user_id,  # Filter by user_id
            Income.deleted_at == None,
            Income.closed_at == None
        ) \
        .group_by(
            Income.income_source_id,
            IncomeSourceType.name
        )
        
        #print('query',query)


        results = query.all()
        #print(results)

        income_source_type_counts = []
        total_balance = 0
        total_income_source_type = 0
        income_source_type_names = {}

        for row in results:
            total_balance += row.balance
            total_income_source_type += 1
            income_source_type_names[row.id] = row.name
            income_source_type_counts.append({"_id": row.id, "name": row.name, "balance": row.balance, "count": row.count})


        

        
        

        return jsonify({
            "payLoads":{            
                "income_source_type_counts":income_source_type_counts,
                "total_income_source_type":total_income_source_type,
                "total_balance":total_balance,
                "income_source_type_names":income_source_type_names


            }        
        })
    
    except Exception as e:
        return jsonify({
            "payLoads":{            
                "income_source_type_counts":[],
                "total_income_source_type":0,
                "total_balance":0,
                "income_source_type_names":{}


            }        
        })

    finally:
        session.close()

