
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

    myquery = { 
        "_id" :ObjectId(id),
        "goal_reached":None
    }
    saving = collection.find_one(
        myquery,
        # {"_id":0}
        )
    breakdown = {}
    total_balance = 0
    progress = 0
    next_contribution_date = None
    goal_reached = None
    period = 0
    saving_boost_contribution_data = []    
    result = 0    

    boost_status = [] # will update boost next payment date and closed issue
    total_balance_xyz  = 0
    len_breakdown = 0
    # print('saving',saving)
    
    if saving != None:
        starting_date = saving['next_contribution_date']
        goal_amount = round(saving["goal_amount"],2)
        interest = round(saving["interest"],2)
        starting_amount = round(saving["total_balance"],2)
        contribution = round(saving["contribution"],2)
        repeat = saving['repeat']['value'] if saving['repeat']['value'] > 0 else None
        i_contribution=saving['increase_contribution_by']
        period = saving['period']

        total_balance_xyz = starting_amount


        ### we will check any boost here
        counted_saving_boost = saving_boost.count_documents(
            {
                     'saving.value':saving['_id'],
                     'deleted_at':None,
                     'closed_at':None
            }
        )

        if counted_saving_boost > 0:
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

                total_balance_xyz  = total_balance_xyz - saving_boost_amount if  op_type > 1 else total_balance_xyz + saving_boost_amount


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

                contribution_breakdown_b = get_single_boost(starting_amount_b,saving_boost_amount,starting_date_b,repeat_boost,period_boost,op_type)
                breakdown_b = contribution_breakdown_b['breakdown']
                total_balance_b = contribution_breakdown_b['total_balance']
                next_contribution_date_b = contribution_breakdown_b['next_contribution_date']


                len_c_b = len(breakdown_b)
                if len_c_b > 0:
                    breakdown_b = {
                         'saving_id':saving['_id'],
                         'saving_boost_id':saving_b['_id'],
                         'op_type':op_type,
                         'repeat':repeat_b,
                         **breakdown_b
                    }
                    saving_boost_contribution_data.append(breakdown_b)

                boost_status_data = {
                    '_id':saving_b['_id'],
                    'next_contribution_date':next_contribution_date_b,
                    'total_balance':total_balance_b,
                    'closed_at':datetime.now() if repeat_b < 1 else None
                }
                boost_status.append(boost_status_data)


       
        

        contribution_breakdown = get_single_breakdown(total_balance_xyz,contribution,interest, goal_amount, starting_date,repeat,period,i_contribution)        
        breakdown = contribution_breakdown['breakdown']
        total_balance = contribution_breakdown['total_balance']
        progress  = contribution_breakdown['progress']
        next_contribution_date = contribution_breakdown['next_contribution_date']
        goal_reached = contribution_breakdown['goal_reached']
        period = contribution_breakdown['period']

        #print('goal_reached',goal_reached)

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
    
        # if next_contribution_date == None:
        #         goal_reached = goal_reached if len_breakdown > 0 else None
        
       
    len_boost_breakdown = len(saving_boost_contribution_data)

    len_boost_status =  len(boost_status)

    change_append_data = {
        "goal_reached":goal_reached,            
        'next_contribution_date':next_contribution_date,
        'total_balance':total_balance, 
        'progress':progress,
        'period':period,
        'updated_at':datetime.now()              

    }
    newvalues = { "$set": change_append_data }
             
    if len_breakdown > 0:
        # breakdown = {
        #     'total_balance_xyz':total_balance_xyz,
        #     **breakdown
        # }
                          
        with client.start_session() as session:
                with session.start_transaction():

                    del myquery['goal_reached']
                    
                    try:
                        c_data = contributions.insert_one(breakdown,session=session)                        
                        s_b_ack = 0
                        if len_boost_breakdown > 0:
                            if len_boost_breakdown > 1:
                                s_b_c_data =  saving_boost_contributions.insert_many(saving_boost_contribution_data, session=session)
                                s_b_ack = 1 if s_b_c_data.inserted_ids else 0
                            else:
                                s_b_c_data =  saving_boost_contributions.insert_one(saving_boost_contribution_data[0],session=session)
                                s_b_ack = 1 if s_b_c_data.inserted_id else 0

                        s_b_k = 0
                        if len_boost_status > 0:

                            for b_s in  boost_status:
                                sb_data = saving_boost.update_many({
                                     '_id':b_s['_id']
                                     }, 
                                     { "$set":{
                                         'next_contribution_date':b_s['next_contribution_date'],
                                         'total_balance':b_s['total_balance'],
                                         'closed_at':b_s['closed_at']
                                        
                                        } 
                                    },
                                    session=session
                                )
                                s_b_k = 1 if sb_data.modified_count else 0 


                        s_data = collection.update_one(myquery, newvalues, session=session)
                        if len_boost_breakdown > 0:
                            result = 1 if c_data.inserted_id and s_data.modified_count  and s_b_ack else 0
                        else:
                            result = 1 if c_data.inserted_id and s_data.modified_count  else 0
                        
                        
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