from collections import defaultdict
import os
from flask import Flask,request,jsonify, json
from sqlalchemy import Integer, case, cast, func
#from flask_cors import CORS, cross_origin
from models import Income, IncomeBoost
from incomeutil import calculate_breakdown_future
from app import app
from util import *
from datetime import datetime
from dbpg import db
from sqlalchemy.orm import aliased




def process_projections(todo, initial_gross_input:float=0, initial_net_input:float=0):

    frequency_boost = todo['frequency_boost']
    onetime_boost = todo['onetime_boost']
    income_boost_date = convertDateTostring(todo['next_pay_date'],'%Y-%m') if onetime_boost < 1 else None
    print('income_boost_date',income_boost_date)
    total_gross_income = todo['total_gross_income']+initial_gross_input
    total_net_income = todo['total_net_income']+initial_net_input
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
    gross_total = income_contribution_data['gross_total']
    net_total = income_contribution_data['net_total']

    return (
        income_contribution,
        gross_total,
        net_total
    )

def get_projection_list(projection_list,single:int=1):

    # Optimized dictionary to store merged results
    merged_data = defaultdict(lambda: {
        "base_gross_income": 0,
        "base_net_income": 0,
        "month_word": "",
        "earners": []
    })

    # Merging logic with optimization
    if single:
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
    else:
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

    projection_list = process_projections(data)[0]
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

    projection_list = []
    #initial_gross_input = 0
    #initial_net_input = 0
    for row in results:
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
        projections = process_projections(data)
        projection = projections[0]
        #initial_gross_input = projections[1]
        #initial_net_input = projections[2]
         
        projection_list.append(projection)
    

    result = get_projection_list(projection_list,0) if len(projection_list) > 0 else []

    return jsonify({
        "payLoads":{                        
               'projection_list':result

        }        
    })
    
