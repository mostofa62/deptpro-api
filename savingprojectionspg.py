from collections import defaultdict
import os
from flask import Flask,request,jsonify, json
from sqlalchemy import Integer, case, cast, func
#from flask_cors import CORS, cross_origin

from savingutil import calculate_breakdown_future
from app import app
from db import my_col,myclient
from bson.objectid import ObjectId
from bson.json_util import dumps
import re
from util import *
from datetime import datetime,timedelta
from decimal import Decimal

from models import Saving, SavingBoost
from dbpg import db
from sqlalchemy.orm import aliased
# Aliasing the SavingBoost table to avoid conflict in the joins
saving_boosts_1 = aliased(SavingBoost)
saving_boosts_2 = aliased(SavingBoost)

def process_projections(todo, total_balance:float=0,goal_amount:float=0):
    frequency_boost = todo['frequency_boost']
    onetime_boost = todo['onetime_boost']
    saving_boost_date = convertDateTostring(todo['next_contribution_date'],'%Y-%m') if onetime_boost < 1 else None
    total_balance += todo['total_balance']
    contribution = todo['contribution']
    

    saving_contribution_data = calculate_breakdown_future(
            initial_amount=total_balance,
            contribution=contribution,
            annual_interest_rate=todo['interest'],
            start_date = todo['next_contribution_date'],
            goal_amount = goal_amount,
            frequency=todo['repeat']['value'],
            saving_boost=onetime_boost,
            saving_boost_date=saving_boost_date,
            i_contribution=todo['increase_contribution_by'],
            period=todo['period'],
            repeat_saving_boost = frequency_boost
        )
    
    saving_contribution = saving_contribution_data['breakdown']
    total_balance = saving_contribution_data['total_balance']

    return(
        saving_contribution,
        total_balance
    )

def get_projection_list(projection_list,single:int=1):
    # Dictionary to store merged results
    merged_data = defaultdict(lambda: {
        "total_balance": 0,
        "contribution": 0,       
        "month_word": ""
    })

    if single:
        for entry in projection_list:             
            month = entry['month']                
            merged_data[month]['total_balance'] += round(entry['total_balance'],2)
            merged_data[month]['contribution'] += round(entry['contribution'],2)
            merged_data[month]['month_word'] = entry['month_word']
            merged_data[month]['total_balance'] = round(merged_data[month]['total_balance'],2)
            merged_data[month]['contribution']  = round(merged_data[month]['contribution'] ,2)

    else:        
        for sublist in projection_list:
            for entry in sublist:                
                month = entry['month']                
                merged_data[month]['total_balance'] += round(entry['total_balance'],2)
                merged_data[month]['contribution'] += round(entry['contribution'],2)
                merged_data[month]['month_word'] = entry['month_word']
                merged_data[month]['total_balance'] = round(merged_data[month]['total_balance'],2)
                merged_data[month]['contribution']  = round(merged_data[month]['contribution'] ,2)


     # Round values during final conversion to avoid redundant operations
    result = sorted(
        [
            {
                "month": month,
                "total_balance": round(data['total_balance'], 2),
                "contribution": round(data['contribution'], 2),
                "month_word": data['month_word']                
            }
            for month, data in merged_data.items()
        ],
        key=lambda x: datetime.strptime(x['month'], "%Y-%m")
    )
    #result = [{"month": month, **data} for month, data in merged_data.items()]

    return result
    

@app.route('/api/saving-contributions-nextpgu/<int:user_id>', methods=['GET'])
def saving_contributions_next_pgu(user_id:int):

    # Subquery for frequency_boost with conditional subtraction
    frequency_boost_subquery = db.session.query(
        func.sum(
            case(
                (cast(saving_boosts_1.boost_operation_type['value'].astext, Integer) > 1, -saving_boosts_1.saving_boost),  # Subtract if value is 1
                else_=saving_boosts_1.saving_boost  # Otherwise, add
            )
        ).label('frequency_boost')
    ).filter(
        saving_boosts_1.user_id == user_id,
        saving_boosts_1.saving_id == Saving.id,
        saving_boosts_1.deleted_at == None,
        saving_boosts_1.closed_at == None,
        cast(saving_boosts_1.repeat_boost['value'].astext, Integer) > 0
    ).scalar_subquery()

    # Subquery for onetime_boost
    onetime_boost_subquery = db.session.query(
        func.sum(
            case(
                (cast(saving_boosts_2.boost_operation_type['value'].astext, Integer) > 1, -saving_boosts_2.saving_boost),  # Subtract if value is 1
                else_=saving_boosts_2.saving_boost  # Otherwise, add
            )
            
        ).label('onetime_boost')
    ).filter(
        saving_boosts_2.user_id == user_id,
        saving_boosts_2.saving_id == Saving.id,
        saving_boosts_2.deleted_at == None,
        saving_boosts_2.closed_at == None,
        cast(saving_boosts_2.repeat_boost['value'].astext, Integer) < 1
    ).scalar_subquery()

    goal_amount = db.session.query(
        func.sum(Saving.goal_amount)).filter(
            Saving.closed_at == None, 
           Saving.deleted_at == None, 
           Saving.goal_reached == None, 
           Saving.next_contribution_date != None, 
           Saving.user_id == user_id).scalar()


    # Main query
    query = db.session.query(
        Saving.id,
        Saving.total_balance,
        Saving.starting_amount,
        Saving.interest,
        Saving.contribution,
        Saving.increase_contribution_by,
        Saving.goal_amount,
        Saving.goal_reached,
        Saving.next_contribution_date,
        Saving.period,
        Saving.repeat,
        Saving.user_id,
        func.coalesce(frequency_boost_subquery, 0).label('frequency_boost'),
        func.coalesce(onetime_boost_subquery, 0).label('onetime_boost')
    ).filter(
        Saving.user_id == user_id,
        Saving.deleted_at == None,
        Saving.closed_at == None
    )

   

    total_balance = 0    

    results = query.all()    

    
    projection_list = []

    for row in results:
        data= {
            "id": row.id,           
            "total_balance": row.total_balance,
            "starting_amount": row.starting_amount,
            "interest": row.interest,
            "contribution": row.contribution,
            "increase_contribution_by": row.increase_contribution_by,
            "goal_amount": row.goal_amount,
            "goal_reached": row.goal_reached,
            "next_contribution_date": row.next_contribution_date,
            "repeat": row.repeat,
            "period":row.period,
            "frequency_boost": row.frequency_boost,
            "onetime_boost": row.onetime_boost
        }
        projections = process_projections(data,total_balance, goal_amount)
        projection = projections[0]
        total_balance = projections[1]
        projection_list.append(projection)

    result = get_projection_list(projection_list,0) if len(projection_list) > 0 else []

    return jsonify({
        "payLoads":{                                     
            'projection_list':result
        }        
    })



@app.route('/api/saving-contributions-nextpg/<int:saving_id>', methods=['GET'])
def saving_contributions_next_pg(saving_id:int):

    # Subquery for frequency_boost with conditional subtraction
    frequency_boost_subquery = db.session.query(
        func.sum(
            case(
                (cast(saving_boosts_1.boost_operation_type['value'].astext, Integer) > 1, -saving_boosts_1.saving_boost),  # Subtract if value is 1
                else_=saving_boosts_1.saving_boost  # Otherwise, add
            )
        ).label('frequency_boost')
    ).filter(        
        saving_boosts_1.saving_id == saving_id,
        saving_boosts_1.deleted_at == None,
        saving_boosts_1.closed_at == None,
        cast(saving_boosts_1.repeat_boost['value'].astext, Integer) > 0
    ).scalar_subquery()

    # Subquery for onetime_boost
    onetime_boost_subquery = db.session.query(
        func.sum(
            case(
                (cast(saving_boosts_2.boost_operation_type['value'].astext, Integer) > 1, -saving_boosts_2.saving_boost),  # Subtract if value is 1
                else_=saving_boosts_2.saving_boost  # Otherwise, add
            )
            
        ).label('onetime_boost')
    ).filter(        
        saving_boosts_2.saving_id == saving_id,
        saving_boosts_2.deleted_at == None,
        saving_boosts_2.closed_at == None,
        cast(saving_boosts_2.repeat_boost['value'].astext, Integer) < 1
    ).scalar_subquery()



    # Main query
    row = db.session.query(
        Saving.id,
        Saving.total_balance,
        Saving.starting_amount,
        Saving.interest,
        Saving.contribution,
        Saving.increase_contribution_by,
        Saving.goal_amount,
        Saving.goal_reached,
        Saving.next_contribution_date,
        Saving.period,
        Saving.repeat,
        Saving.user_id,
        func.coalesce(frequency_boost_subquery, 0).label('frequency_boost'),
        func.coalesce(onetime_boost_subquery, 0).label('onetime_boost')
    ).filter(
        Saving.id == saving_id,
        Saving.deleted_at == None,
        Saving.closed_at == None
    ).first() 

    goal_amount = row.goal_amount
    total_balance = 0    
        
    
    data= {
        "id": row.id,           
        "total_balance": row.total_balance,
        "starting_amount": row.starting_amount,
        "interest": row.interest,
        "contribution": row.contribution,
        "increase_contribution_by": row.increase_contribution_by,
        "goal_amount": row.goal_amount,
        "goal_reached": row.goal_reached,
        "next_contribution_date": row.next_contribution_date,
        "repeat": row.repeat,
        "period":row.period,
        "frequency_boost": row.frequency_boost,
        "onetime_boost": row.onetime_boost
    }
    projection_list = process_projections(data)[0]

    result = get_projection_list(projection_list,total_balance, goal_amount)

    return jsonify({
        "payLoads":{                                     
            'projection_list':result
        }        
    })