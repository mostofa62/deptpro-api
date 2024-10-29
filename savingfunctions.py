
import os
from flask import Flask,request,jsonify, json
from savingutil import get_single_boost, get_single_breakdown
from app import app
from db import my_col,myclient
from bson.objectid import ObjectId
from bson.json_util import dumps
import re
from util import *
from datetime import datetime,timedelta
from decimal import Decimal

client = myclient
collection = my_col('saving')
contributions = my_col('saving_contributions')
saving_boost = my_col('saving_boost')
saving_boost_contributions = my_col('saving_boost_contributions')

@app.route('/api/contribute-next/<string:id>', methods=['GET'])
def contribute_next(id:str):

    myquery = { "_id" :ObjectId(id)}
    saving = collection.find_one(
        myquery,
        # {"_id":0}
        )
    breakdown = {}
    total_balance = 0
    progress = 0
    next_contribution_date = None
    goal_reached = None
    saving_boost_contribution_data = []    
    result = 0

    #print(saving)
    
    if saving!=None and saving['goal_reached']==None:
        starting_date = saving['next_contribution_date']
        goal_amount = round(saving["goal_amount"],2)
        interest = round(saving["interest"],2)
        starting_amount = round(saving["total_balance"],2)
        contribution = round(saving["contribution"],2)
        repeat = saving['repeat']['value'] if saving['repeat']['value'] > 0 else None
        # Perform the aggregation to find the maximum period value
        pipeline = [
            {
                '$match': {
                    'saving_id': saving['_id']  # Match documents with the specified saving_id
                }
            },
            {
                '$group': {
                    '_id': None,  # Grouping by None to get a single result
                    'max_period': {'$max': '$period'}  # Get the maximum value of the period field
                }
            }
        ]
        # Execute the aggregation
        result = list(contributions.aggregate(pipeline))
        # Extract the maximum period value
        period = result[0]['max_period'] if result else 0

        contribution_breakdown = get_single_breakdown(starting_amount,contribution,interest, goal_amount, starting_date,repeat,period)        
        breakdown = contribution_breakdown['breakdown']
        total_balance = contribution_breakdown['total_balance']
        progress  = contribution_breakdown['progress']
        next_contribution_date = contribution_breakdown['next_contribution_date']
        goal_reached = contribution_breakdown['goal_reached']

        len_breakdown = len(breakdown)

        if len_breakdown > 0:
             breakdown = {
                'saving_id':saving['_id'],
                'deleted_at':None,
                'closed_at':None,
                'goal_reached':None,
                'commit':saving['commit'],
                **breakdown
             }   
    
        if next_contribution_date == None:
                goal_reached = goal_reached if len_breakdown > 0 else None

        
        if goal_reached == None:
            saving_boosts = saving_boost.find(
                {
                     'saving.value':saving['_id'],
                     'deleted_at':None,
                     'closed_at':None
                },
                # {'_id':1}
            )
            for saving_b in saving_boosts:
                starting_date_b = saving_b['next_contribution_date'] if saving_b['next_contribution_date'] != None else saving_b['pay_date_boost'] 
                starting_amount_b = round(saving_b["total_balance"],2)
                saving_boost_amount = round(saving_b["saving_boost"],2)
                repeat_boost = saving_b['repeat_boost']['value'] if saving_b['repeat_boost']['value'] > 0 else None
                period_boost = 0
                op_type = saving_b['boost_operation_type']['value']
                repeat_b = saving_b['repeat_boost']['value']

                # Perform the aggregation to find the maximum period value
                pipeline_boost = [
                    {
                        '$match': {
                            'saving_boost_id': saving_b['_id']  # Match documents with the specified saving_id
                        }
                    },
                    {
                        '$group': {
                            '_id': None,  # Grouping by None to get a single result
                            'max_period': {'$max': '$period'}  # Get the maximum value of the period field
                        }
                    }
                ]
                #print('saving_boost_contributions',saving_boost_contributions)
                # Execute the aggregation                
                result = list(saving_boost_contributions.aggregate(pipeline_boost))
                # Extract the maximum period value
                period_boost = result[0]['max_period'] if result else 0

                contribution_breakdown_b = get_single_boost(starting_amount_b,saving_boost_amount,starting_date_b,repeat_boost,period_boost)
                #breakdown_b = contribution_breakdown_b['breakdown']
                #total_balance_b = contribution_breakdown_b['total_balance']
                #next_contribution_date_b = contribution_breakdown_b['next_contribution_date']

                # s_b_c = {
                #     'breakdown':breakdown_b,
                #     'total_balance':total_balance_b,                    
                #     'next_contribution_date':next_contribution_date_b                   
                # }
                len_c_b = len(contribution_breakdown_b)
                if len_c_b > 0:
                    contribution_breakdown_b = {
                         'saving_id':saving['_id'],
                         'saving_boost_id':saving_b['_id'],
                         'op_type':op_type,
                         'repeat':repeat_b,
                         **contribution_breakdown_b
                    }
                    saving_boost_contribution_data.append(contribution_breakdown_b)

                 
                 
            # saving_boost_list = list(saving_boosts)
            # saving_boost_id_list = [d.pop('_id') for d in saving_boost_list]
    len_boost_breakdown = len(saving_boost_contribution_data)

    change_append_data = {
        "goal_reached":goal_reached,            
        'next_contribution_date':next_contribution_date,
        'total_balance':total_balance, 
        'progress':progress ,
        'updated_at':datetime.now()              

    }
    newvalues = { "$set": change_append_data }
             
    if len_breakdown > 0:
                          
        with client.start_session() as session:
                with session.start_transaction():
                    
                    try:
                        c_data = contributions.insert_one(breakdown,session=session)
                        s_b_c_data = None
                        if len_boost_breakdown > 0:
                            if len_boost_breakdown > 1:
                                s_b_c_data =  saving_boost_contributions.insert_many(saving_boost_contribution_data, session=session)
                            else:
                                s_b_c_data =  saving_boost_contributions.insert_one(saving_boost_contribution_data[0],session=session)

                        s_data = collection.update_one(myquery, newvalues, session=session)

                        result = 1 if c_data.inserted_id and s_data.modified_count else 0
                        if result:
                             session.commit_transaction()
                        else:
                             session.abort_transaction()
                             

                    except Exception as ex:
                        print(ex)
                        result = 0
                        session.abort_transaction()        
    

    breakdown_json = MongoJSONEncoder().encode(breakdown)
    breakdown = json.loads(breakdown_json)

    sbc_json = MongoJSONEncoder().encode(saving_boost_contribution_data)
    saving_boost_contribution_data = json.loads(sbc_json)
               

    return({
        'result':result,
        'breakdown':breakdown,
        'total_balance':total_balance,
        'progress':progress,
        'next_contribution_date':next_contribution_date,
        'goal_reached':goal_reached,
        'saving_boost_contributions':saving_boost_contribution_data
    })