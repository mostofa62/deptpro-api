from collections import defaultdict
import os
from flask import Flask,request,jsonify, json
from sqlalchemy import Integer, case, cast, func
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
from sqlalchemy.orm import aliased

client = myclient
collection = my_col('income_transactions')
income = my_col('income')
income_boost = my_col('income_boost')
income_boost_transaction = my_col('income_boost_transactions')
income_monthly_log = my_col('income_monthly_log')
income_boost_monthly_log = my_col('income_boost_monthly_log')
app_data = my_col('app_data')

'''
def income_transactions_next_function(todo):

        
        pipeline_boost = [
        {
            '$match': {
                'income.value': todo['_id'],
                'deleted_at':None,
                'closed_at':None,
                'repeat_boost.value': {'$gt': 0}
            }
            },
            {
                '$group': {
                    '_id': None,
                    'total_repeat_boost': {'$sum': '$repeat_boost.value'},
                    'total_income_boost': {
                        '$sum': '$income_boost'
                    }
                }
            }
        ]

        # Execute the aggregation
        result_boost = list(income_boost.aggregate(pipeline_boost))

        # Get the sums if any results found
        total_repeat_boost = result_boost[0]['total_repeat_boost'] if result_boost else 0
        total_income_boost = result_boost[0]['total_income_boost'] if result_boost else 0

        #print('total_repeat_boost, total_income_boost',total_repeat_boost, total_income_boost)

        total_gross_income = todo['total_gross_income']
        total_net_income = todo['total_net_income']

        gross_income = todo['gross_income']
        net_income = todo['net_income']


        pipeline_boost_onetime = [
            {
                '$match': {
                    'income.value': todo['_id'],
                    'deleted_at': None,
                    'closed_at':None,
                    'repeat_boost.value': {'$lt': 1}
                }
            },
            {
                '$group': {
                    '_id': None,
                    'total_income_boost': {
                        '$sum': '$income_boost'
                    }
                }
            }
        ]


        # Execute the aggregation
        result_boost_onetime = list(income_boost.aggregate(pipeline_boost_onetime))

        total_income_boost_onetime = result_boost_onetime[0]['total_income_boost'] if result_boost_onetime else None

        #print('total_income_boost_onetime',total_income_boost_onetime)
        #print(total_balance, contribution)

        #total_balance = todo['total_balance']
        #contribution = todo['contribution']
        income_boost_date = todo['next_pay_date'].strftime('%Y-%m') if total_income_boost_onetime !=None else None

        income_contribution_data = calculate_breakdown_future(

            initial_gross_input=total_gross_income,
            initial_net_input=total_net_income,
            gross_input=gross_income,
            net_input=net_income,            
            pay_date = todo['next_pay_date'],            
            frequency=todo['repeat']['value'],
            income_boost=total_income_boost_onetime,
            income_boost_date=income_boost_date,                        
            repeat_income_boost = total_income_boost,
            earner=todo.get('earner'),
            earner_id=str(todo['_id'])
        )

        income_contribution = income_contribution_data['breakdown']

        
               

    
        


        return income_contribution



'''
def process_projections(todo):

    frequency_boost = todo['frequency_boost']
    onetime_boost = todo['onetime_boost']
    income_boost_date = convertDateTostring(todo['next_pay_date'],'%Y-%m') if onetime_boost < 1 else None
    print('income_boost_date',income_boost_date)
    total_gross_income = todo['total_gross_income']
    total_net_income = todo['total_net_income']
    gross_income = todo['gross_income']
    net_income = todo['net_income']

    income_contribution_data = calculate_breakdown_future(

            initial_gross_input=total_gross_income,
            initial_net_input=total_net_income,
            gross_input=gross_income,
            net_input=net_income,            
            pay_date = todo['next_pay_date'],            
            frequency=todo['repeat']['value'],
            income_boost=onetime_boost,
            income_boost_date=income_boost_date,                        
            repeat_income_boost = frequency_boost,
            earner=todo.get('earner'),
            earner_id=todo['id']
        )

    income_contribution = income_contribution_data['breakdown']

    return income_contribution

def get_projection_list(projection_list):

    # Optimized dictionary to store merged results
    merged_data = defaultdict(lambda: {
        "base_gross_income": 0,
        "base_net_income": 0,
        "month_word": "",
        "earners": []
    })

    # Merging logic with optimization
    for entry in projection_list:        
            month = entry['month']
            merged_entry = merged_data[month]

            # Accumulate income values directly
            merged_entry['base_gross_income'] += entry['base_gross_income']
            merged_entry['base_net_income'] += entry['base_net_income']
            # Append earner-specific data
            merged_entry['earners'].append({
                'earner': entry['earner'],
                'earner_id': entry['earner_id'],
                'gross_income': entry['base_gross_income'],
                'net_income': entry['base_net_income']
            })

            # Store the month word (assumes it's consistent for the same month)
            if not merged_entry['month_word']:
                merged_entry['month_word'] = entry['month_word']

    # Round values during final conversion to avoid redundant operations
    result = sorted(
        [
            {
                "month": month,
                "base_gross_income": round(data['base_gross_income'], 2),
                "base_net_income": round(data['base_net_income'], 2),
                "month_word": data['month_word'],
                "earners": data['earners']
            }
            for month, data in merged_data.items()
        ],
        key=lambda x: datetime.strptime(x['month'], "%Y-%m")
    )

    return result


        
    

# Aliasing the IncomeBoost table to avoid conflict in the joins
income_boosts_1 = aliased(IncomeBoost)
income_boosts_2 = aliased(IncomeBoost)

@app.route('/api/income-transactions-nextpg/<int:income_id>', methods=['GET'])
def income_transactions_next_pg(income_id:int):

    # Subquery for frequency_boost
    frequency_boost_subquery = db.session.query(
        func.sum(income_boosts_1.income_boost).label('frequency_boost')
    ).filter(
        income_boosts_1.income_id == Income.id,
        income_boosts_1.deleted_at == None,
        income_boosts_1.closed_at == None,
        cast(income_boosts_1.repeat_boost['value'].astext, Integer) > 0
    ).scalar_subquery()

    # Subquery for onetime_boost
    onetime_boost_subquery = db.session.query(
        func.sum(income_boosts_2.income_boost).label('onetime_boost')
    ).filter(
        income_boosts_2.income_id == Income.id,
        income_boosts_2.deleted_at == None,
        income_boosts_2.closed_at == None,
        cast(income_boosts_2.repeat_boost['value'].astext, Integer) < 1
    ).scalar_subquery()

    # Main query
    row = db.session.query(
        Income.id,
        Income.earner,
        Income.gross_income,
        Income.net_income,
        Income.total_gross_income,
        Income.total_net_income,
        Income.pay_date,
        Income.next_pay_date,
        Income.repeat,
        func.coalesce(frequency_boost_subquery, 0).label('frequency_boost'),
        func.coalesce(onetime_boost_subquery, 0).label('onetime_boost')
    ).filter(
        Income.id == income_id,
        Income.deleted_at == None,
        Income.closed_at == None
    ).first()    
   
    data= {
        "id": row.id,
        "earner":row.earner,
        "gross_income": row.gross_income,
        "net_income": row.net_income,
        "total_gross_income": row.total_gross_income,
        "total_net_income": row.total_net_income,
        "pay_date": row.pay_date,
        "next_pay_date": row.next_pay_date,
        "repeat": row.repeat,
        "frequency_boost": row.frequency_boost,
        "onetime_boost": row.onetime_boost
    }

    projection_list = process_projections(data)
    result = get_projection_list(projection_list)

    return jsonify({
        "payLoads":{                        
               'projection_list':result

        }        
    })


@app.route('/api/income-transactions-nextpgu/<int:user_id>', methods=['GET'])
def income_transactions_next_pgu(user_id:int):

    # Subquery for frequency_boost
    frequency_boost_subquery = db.session.query(
        func.sum(income_boosts_1.income_boost).label('frequency_boost')
    ).filter(
        income_boosts_1.user_id == user_id,
        income_boosts_1.income_id == Income.id,
        income_boosts_1.deleted_at == None,
        income_boosts_1.closed_at == None,
        cast(income_boosts_1.repeat_boost['value'].astext, Integer) > 0
    ).scalar_subquery()

    # Subquery for onetime_boost
    onetime_boost_subquery = db.session.query(
        func.sum(income_boosts_2.income_boost).label('onetime_boost')
    ).filter(
        income_boosts_2.user_id == user_id,
        income_boosts_2.income_id == Income.id,
        income_boosts_2.deleted_at == None,
        income_boosts_2.closed_at == None,
        cast(income_boosts_2.repeat_boost['value'].astext, Integer) < 1
    ).scalar_subquery()

    # Main query
    query = db.session.query(
        Income.id,
        Income.earner,
        Income.gross_income,
        Income.net_income,
        Income.total_gross_income,
        Income.total_net_income,
        Income.pay_date,
        Income.next_pay_date,
        Income.repeat,
        Income.user_id,
        func.coalesce(frequency_boost_subquery, 0).label('frequency_boost'),
        func.coalesce(onetime_boost_subquery, 0).label('onetime_boost')
    ).filter(
        Income.user_id == user_id,
        Income.deleted_at == None,
        Income.closed_at == None
    )
    

  

    # # Get the raw SQL statement
    # raw_sql = str(query.statement.compile(dialect=db.engine.dialect))

    # # Print the raw SQL query
    # print(raw_sql)

    results = query.all()

    data = []
    for row in results:
        data.append({
            "id": row.id,
            "earner":row.earner,
            "gross_income": row.gross_income,
            "net_income": row.net_income,
            "total_gross_income": row.total_gross_income,
            "total_net_income": row.total_net_income,
            "pay_date": row.pay_date,
            "next_pay_date": row.next_pay_date,
            "repeat": row.repeat,
            "frequency_boost": row.frequency_boost,
            "onetime_boost": row.onetime_boost
        })

    return jsonify(data)
    
'''

@app.route('/api/income-transactions-nextpgu/<int:user_id>', methods=['GET'])
def income_transactions_next_pgu(user_id:int):

@app.route('/api/income-transactions-next/<income_id>', methods=['GET'])
@app.route('/api/income-transactions-next', methods=['GET'])
def income_transactions_next_pg(income_id=None):
    
    cursor = None
    
    if income_id!=None:

        cursor = income.find_one({
            'closed_at':None,
            'deleted_at':None,
            '_id':ObjectId(income_id)
        },{
            'earner':1,
            'gross_income':1,
            'net_income':1,
            'total_gross_income':1,
            'total_net_income':1,
            'pay_date':1,
            'next_pay_date':1,
            'repeat':1
            })


    else:

        cursor = income.find({
            'closed_at':None,
            'deleted_at':None
        },{
            'earner':1,
            'gross_income':1,
            'net_income':1,
            'total_gross_income':1,
            'total_net_income':1,
            'pay_date':1,
            'next_pay_date':1,
            'repeat':1
            })
    
    projection_list = []

    if income_id!=None:
        
        todo = cursor
        income_contribution = income_transactions_next_function(todo)
        projection_list.append(income_contribution)
    else:
        
        for todo in cursor:
            income_contribution = income_transactions_next_function(todo)
            projection_list.append(income_contribution)

    
    #print('projection_list',projection_list)

    

    # Optimized dictionary to store merged results
    merged_data = defaultdict(lambda: {
        "base_gross_income": 0,
        "base_net_income": 0,
        "month_word": "",
        "earners": []
    })

    # Merging logic with optimization
    for sublist in projection_list:
        for entry in sublist:
            month = entry['month']
            merged_entry = merged_data[month]

            # Accumulate income values directly
            merged_entry['base_gross_income'] += entry['base_gross_income']
            merged_entry['base_net_income'] += entry['base_net_income']
            # Append earner-specific data
            merged_entry['earners'].append({
                'earner': entry['earner'],
                'earner_id': entry['earner_id'],
                'gross_income': entry['base_gross_income'],
                'net_income': entry['base_net_income']
            })

            # Store the month word (assumes it's consistent for the same month)
            if not merged_entry['month_word']:
                merged_entry['month_word'] = entry['month_word']

    # Round values during final conversion to avoid redundant operations
    result = sorted(
        [
            {
                "month": month,
                "base_gross_income": round(data['base_gross_income'], 2),
                "base_net_income": round(data['base_net_income'], 2),
                "month_word": data['month_word'],
                "earners": data['earners']
            }
            for month, data in merged_data.items()
        ],
        key=lambda x: datetime.strptime(x['month'], "%Y-%m")
    )


        


    
    
    
    return jsonify({
        "payLoads":{            
            
               #'projection_list':result,
               #'projection_list_boost':result_boost,
               'projection_list':result
                     


        }        
    })



    
'''









