from collections import defaultdict
import os
from flask import Flask,request,jsonify, json
#from flask_cors import CORS, cross_origin

from savingutil import calculate_breakdown, calculate_breakdown_future
from app import app
from db import my_col,myclient
from bson.objectid import ObjectId
from bson.json_util import dumps
import re
from util import *
from datetime import datetime,timedelta
from decimal import Decimal

collection = my_col('saving_contributions')
saving = my_col('saving')
saving_boost = my_col('saving_boost')
saving_boost_contribution = my_col('saving_boost_contributions')

@app.route('/api/saving-contributions-next/<string:userid>', methods=['GET'])
def saving_contributions_next(userid:str):



    #twelve_months_next = datetime.now() + timedelta(days=365)

    

    # query = {
    #     "pay_date": {"$eq": pay_date},
    # }

    pipeline_goal_amount = [
        {
            '$match': {
                    'closed_at':None,
                    'deleted_at':None,
                    'goal_reached':None,
                    'next_contribution_date':{'$ne':None},
                    'user_id':ObjectId(userid)
                }
            },
            {
                "$group": {
                    "_id": None,
                    "goal_amount": {"$sum": "$goal_amount"},

                }
            
            }
        ]

    saving_result = list(saving.aggregate(pipeline_goal_amount))
    goal_amount = saving_result[0]['goal_amount'] if saving_result else 0

    total_balance = 0    

    cursor = saving.find({
        'closed_at':None,
        'deleted_at':None,
        'goal_reached':None,
        'next_contribution_date':{'$ne':None},
        'user_id':ObjectId(userid)
    },{
        'total_balance':1,
        'starting_amount':1,
        'interest':1,
        'contribution':1,
        'increase_contribution_by':1,
        'goal_amount':1,
        'goal_reached':1,
        'next_contribution_date':1,
        'repeat':1,
        'period':1
        })
    
    projection_list = []

    # Query to match saving.value and filter repeat_boost.value > 0
    

    for todo in cursor: 
        #for frequncy based
        pipeline_boost = [
        {
            '$match': {
                'saving.value': todo['_id'],
                'deleted_at':None,
                'closed_at':None,
                'repeat_boost.value': {'$gt': 0}
            }
            },
            {
                '$group': {
                    '_id': None,
                    'total_repeat_boost': {'$sum': '$repeat_boost.value'},
                    'total_saving_boost': {
                        '$sum': {
                            '$cond': {
                                'if': {'$eq': ['$boost_operation_type.value', 1]},
                                'then': '$saving_boost',  # Add if value is 1
                                'else': {'$multiply': ['$saving_boost', -1]}  # Subtract if value is 2
                            }
                        }
                    }
                }
            }
        ]

        # Execute the aggregation
        result_boost = list(saving_boost.aggregate(pipeline_boost))

        # Get the sums if any results found
        total_repeat_boost = result_boost[0]['total_repeat_boost'] if result_boost else 0
        total_saving_boost = result_boost[0]['total_saving_boost'] if result_boost else 0

        print('total_repeat_boost, total_saving_boost',total_repeat_boost, total_saving_boost)


        #total_balance = todo['total_balance'] + total_saving_boost if  total_repeat_boost > 0 else todo['total_balance']
        #print(total_balance,todo['total_balance'])
        total_balance += todo['total_balance']

        
        #contribution = todo['contribution'] + total_saving_boost if  total_repeat_boost > 0 else todo['contribution']
        contribution = todo['contribution']

        #for one time boosting
        pipeline_boost_onetime = [
            {
                '$match': {
                    'saving.value': todo['_id'],
                    'deleted_at': None,
                    'closed_at':None,
                    'repeat_boost.value': {'$lt': 1}
                }
            },
            {
                '$group': {
                    '_id': None,
                    'total_saving_boost': {
                        '$sum': {
                            '$cond': {
                                'if': {'$eq': ['$boost_operation_type.value', 1]},
                                'then': '$saving_boost',  # Add if value is 1
                                'else': {'$multiply': ['$saving_boost', -1]}  # Subtract if value is 2
                            }
                        }
                    }
                }
            }
        ]


        # Execute the aggregation
        result_boost_onetime = list(saving_boost.aggregate(pipeline_boost_onetime))

        total_saving_boost_onetime = result_boost_onetime[0]['total_saving_boost'] if result_boost_onetime else None

        print('total_saving_boost_onetime',total_saving_boost_onetime)
        #print(total_balance, contribution)

        #total_balance = todo['total_balance']
        #contribution = todo['contribution']
        saving_boost_date = todo['next_contribution_date'].strftime('%Y-%m') if total_saving_boost_onetime !=None else None
        

        saving_contribution_data = calculate_breakdown_future(

            initial_amount=total_balance,
            contribution=contribution,
            annual_interest_rate=todo['interest'],
            start_date = todo['next_contribution_date'],
            goal_amount = goal_amount,
            frequency=todo['repeat']['value'],
            saving_boost=total_saving_boost_onetime,
            saving_boost_date=saving_boost_date,
            i_contribution=todo['increase_contribution_by'],
            period=todo['period'],
            repeat_saving_boost = total_saving_boost
        )
        saving_contribution = saving_contribution_data['breakdown']
        total_balance = saving_contribution_data['total_balance']

        projection_list.append(saving_contribution)

    
    # Dictionary to store merged results
    merged_data = defaultdict(lambda: {
        "total_balance": 0,
        "contribution": 0,
        #"total_gross_for_period": 0,
        #"total_net_for_period": 0,
        "month_word": ""
    })

    # Merging logic
    for sublist in projection_list:
        for entry in sublist:
            
            month = entry['month']
            #merged_data[month]['id'] = ObjectId()
            merged_data[month]['total_balance'] += round(entry['total_balance'],2)
            merged_data[month]['contribution'] += round(entry['contribution'],2)
            #merged_data[month]['total_gross_for_period'] += entry['total_gross_for_period']
            #merged_data[month]['total_net_for_period'] += entry['total_net_for_period']
            merged_data[month]['month_word'] = entry['month_word']

            merged_data[month]['total_balance'] = round(merged_data[month]['total_balance'],2)
            merged_data[month]['contribution']  = round(merged_data[month]['contribution'] ,2)

            #merged_data[month]['id'] = generate_unique_id(month)


    # Convert the merged data back into a list if needed
    result = [{"month": month, **data} for month, data in merged_data.items()]


    
    
    
    return jsonify({
        "payLoads":{            
            
               #'projection_list':result,
               #'projection_list_boost':result_boost,
               'projection_list':result
                     


        }        
    })


@app.route('/api/saving-contributions-previous', methods=['GET'])
def saving_contributions_previous():

    userid = request.args.get('userid')
    saving_id = request.args.get('saving_id')

    twelve_months_ago = datetime.now() - timedelta(days=365)

    match_query = {
        "contribution_date": {"$gte": twelve_months_ago},
        #"deleted_at": None,
        #"closed_at":None,
        #"user_id":ObjectId(userid)
        
    }

    if userid!=None:
        match_query["user_id"] = ObjectId(userid)
    if saving_id!=None:
        match_query["saving_id"] = ObjectId(saving_id)

    '''

    pipeline = [
    # Step 1: Match documents from the main collection
    { 
        "$match": match_query 
    },

    {
        "$lookup": {
            "from": "saving",  # The collection to join with
            "localField": "saving_id",  # Field from saving_contributions
            "foreignField": "_id",  # Field from saving collection
            "as": "saving_details",  # The alias for the joined data
            "pipeline": [
                {
                    "$match": {
                        "deleted_at": None  # Ensure the deleted_at field is None (active records)
                    }
                }
            ]
        }
    },
    {
        "$unwind": "$saving_details"  # Unwind the joined array (in case there are multiple matches, only take the first)
    },
    
    

    {
        "$group": {
            "_id": { "month": "$month", "saving_id": "$saving_id" },
            "max_total_balance": { "$max": "$total_balance_xyz" },  # Max balance for each saving_id in the month
            "month_word": { "$first": "$month_word" },                   # Include month_word for formatting
            "month": { "$first": "$month" }                              # Include month for further grouping
        }
    },
    
    # Step 6: Group by month and sum the max total_balance
    {
        "$group": {
            "_id": "$_id.month",  # Group by month
            "total_balance": { "$sum": "$max_total_balance" },  # Sum the max balances per saving_id in the month
            "month_word": { "$first": "$month_word" },          # Keep month_word
            "month": { "$first": "$month" }                     # Keep month for sorting later
        }
    },
    
    # Step 7: Project the fields you want
    {
        "$project": {
            "_id": 1,
            "total_balance": 1,
            "month_word": 1
        }
    },
    
    # Step 8: Sort by month
    { 
        "$sort": { "_id": 1 }  # Sort by month
    },
    
    # Step 9: Limit to 12 rows
    { 
        "$limit": 12 
    },
    
    # Step 10: Aggregate results into an array for final output
    {
        "$group": {
            "_id": None,
            "grouped_results": {
                "$push": {
                    "year_month_word": "$month_word",
                    "total_balance": "$total_balance",
                }
            }
        }
    },
    
    # Step 11: Project the final output
    {
        "$project": {
            "_id": 0,
            "grouped_results": 1
        }
    }
]
'''
#4.6 mongodb
    pipeline = [
    # Step 1: Match documents from the main collection
    { 
        "$match": match_query 
    },

    # Step 2: Perform the lookup without a pipeline
    {
        "$lookup": {
            "from": "saving",  # The collection to join with
            "localField": "saving_id",  # Field from saving_contributions
            "foreignField": "_id",  # Field from saving collection
            "as": "saving_details"  # The alias for the joined data
        }
    },
    
    # Step 3: Unwind the joined array
    {
        "$unwind": {
            "path": "$saving_details",
            "preserveNullAndEmptyArrays": True  # Include documents even if saving_details is null
        }
    },

    # Step 4: Filter out records where saving_details.deleted_at is not None
    {
        "$match": {
            "saving_details.deleted_at": None,
            # "$or": [
            #     { "saving_details.deleted_at": None },  # Deleted_at field is null
            #     { "saving_details.deleted_at": { "$exists": False } }  # Deleted_at field does not exist
            # ]
        }
    },
    
    # Step 5: Group by month and saving_id
    {
        "$group": {
            "_id": { "month": "$month", "saving_id": "$saving_id" },
            "max_total_balance": { "$max": "$total_balance_xyz" },  # Max balance for each saving_id in the month
            "month_word": { "$first": "$month_word" },              # Include month_word for formatting
            "month": { "$first": "$month" }                         # Include month for further grouping
        }
    },
    
    # Step 6: Group by month and sum the max total_balance
    {
        "$group": {
            "_id": "$_id.month",  # Group by month
            "total_balance": { "$sum": "$max_total_balance" },  # Sum the max balances per saving_id in the month
            "month_word": { "$first": "$month_word" },          # Keep month_word
            "month": { "$first": "$month" }                     # Keep month for sorting later
        }
    },
    
    # Step 7: Project the fields you want
    {
        "$project": {
            "_id": 1,
            "total_balance": 1,
            "month_word": 1
        }
    },
    
    # Step 8: Sort by month
    { 
        "$sort": { "_id": 1 }  # Sort by month
    },
    
    # Step 9: Limit to 12 rows
    { 
        "$limit": 12 
    },
    
    # Step 10: Aggregate results into an array for final output
    {
        "$group": {
            "_id": None,
            "grouped_results": {
                "$push": {
                    "year_month_word": "$month_word",
                    "total_balance": "$total_balance"
                }
            }
        }
    },
    
    # Step 11: Project the final output
    {
        "$project": {
            "_id": 0,
            "grouped_results": 1
        }
    }
]


    year_month_wise_all = list(collection.aggregate(pipeline))

    year_month_wise_counts = year_month_wise_all[0]['grouped_results'] if year_month_wise_all else []

    if len(year_month_wise_counts) > 0:
        data_json = MongoJSONEncoder().encode(year_month_wise_counts)
        year_month_wise_counts = json.loads(data_json)


    total_monthly_balance = 0

    cuurent_month = datetime.now().strftime('%Y-%m')

    if saving_id!=None:

        pipeline = [
            {
                "$match": {
                    "month": cuurent_month,  # Filter documents for the specified month
                    "saving_id":ObjectId(saving_id)
                }
            },
            {
                "$group": {
                    "_id": "$month",  # Group by month
                    "total_balance": { "$max": "$total_balance_xyz" }  # Sum total_balance for the matched month
                }
            }
        ]

        # Execute the aggregation
        results = list(collection.aggregate(pipeline))
        total_monthly_balance = results[0]['total_balance'] if results else 0 
    return jsonify({
        "payLoads":{            
            
            "year_month_wise_counts":year_month_wise_counts,
            "total_monthly_balance":total_monthly_balance            


        }        
    })




@app.route('/api/saving-contributions/<string:saving_id>', methods=['POST'])
def list_saving_contributions(saving_id:str):
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)
    #global_filter = data.get('filter', '')
    #sort_by = data.get('sortBy', [])

    # Construct MongoDB filter query
    query = {
        #'role':{'$gte':10}
        "saving_id":ObjectId(saving_id),
        "deleted_at":None,
        #"closed_at":None,        
    }
    # if global_filter:
        

    #     pattern_str = r'^\d{4}-\d{2}-\d{2}$'
    #     contribution_date = None
        
    #     #try:
    #     if re.match(pattern_str, global_filter):
    #         contribution_date = datetime.strptime(global_filter,"%Y-%m-%d")
            
    #     #except ValueError:
    #     else:
    #         contribution_date = None
            

    #     query["$or"] = [
            
    #         #{"earner": {"$regex": global_filter, "$options": "i"}},            
    #         {"contribution_date":contribution_date},                                        
    #         # Add other fields here if needed
    #     ]

    # Construct MongoDB sort parameters
    sort_params = [
        ('contribution_date',-1)
    ]
    cursor = collection.find(query).sort(sort_params).skip(page_index * page_size).limit(page_size)
    # for sort in sort_by:
    #     sort_field = sort['id']
    #     sort_direction = -1 if sort['desc'] else 1
    #     sort_params.append((sort_field, sort_direction))

    # Fetch data from MongoDB
    # if sort_params:
    #     cursor = collection.find(query).sort(sort_params).skip(page_index * page_size).limit(page_size)
    # else:
    #     # Apply default sorting or skip sorting
    #     cursor = collection.find(query).skip(page_index * page_size).limit(page_size)



    total_count = collection.count_documents(query)
    #data_list = list(cursor)
    data_list = []

    for todo in cursor:

        
        todo['contribution_date_word'] = todo['contribution_date'].strftime('%d %b, %Y')
        todo['contribution_date'] = convertDateTostring(todo['contribution_date'],"%Y-%m-%d")

        todo['next_contribution_date_word'] = todo['next_contribution_date'].strftime('%d %b, %Y')
        todo['next_contribution_date'] = convertDateTostring(todo['next_contribution_date'],"%Y-%m-%d")                

        


        data_list.append(todo)
    data_json = MongoJSONEncoder().encode(data_list)
    data_obj = json.loads(data_json)

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size


    #total balance , interest, monthly intereset paid off
    # Aggregate query to sum the balance field
    # pipeline = [
    #     {"$match": query},  # Filter by user_id
    #     # {
    #     #     '$addFields': {
    #     #         'total_monthly_saving': {'$add': ['$gross_saving', '$saving_boost']}
    #     #     }
    #     # },
    #     {"$group": {"_id": None, 
    #                 "total_net_saving": {"$sum": "$base_net_saving"},
    #                 "total_gross_saving":{"$sum": "$base_gross_saving"},                                                        
    #                 }}  # Sum the balance
    # ]

    # # Execute the aggregation pipeline
    # result = list(collection.aggregate(pipeline))

    #  # Extract the total balance from the result
    # total_net_saving = result[0]['total_net_saving'] if result else 0
    # total_gross_saving = result[0]['total_gross_saving'] if result else 0
    
    

    return jsonify({
        'rows': data_obj,
        'pageCount': total_pages,
        'totalRows': total_count,
        # 'extra_payload':{
        #     'total_net_saving':total_net_saving,
        #     'total_gross_saving':total_gross_saving,             
        # }
    })



@app.route('/api/saving-boost-contributions/<string:saving_id>', methods=['POST'])
def list_saving_boost_contributions(saving_id:str):
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)
    
    # Construct MongoDB filter query
    query = {
        #'role':{'$gte':10}
        "saving_id":ObjectId(saving_id),
        "deleted_at":None,
        #"closed_at":None,        
    }
   

    # Construct MongoDB sort parameters
    sort_params = [
        #('contribution_date',-1)
        ('created_at',-1)
    ]
    cursor = saving_boost_contribution.find(query).sort(sort_params).skip(page_index * page_size).limit(page_size)
   



    total_count = saving_boost_contribution.count_documents(query)
    #data_list = list(cursor)
    data_list = []

    for todo in cursor:

        saving_boost_ac = saving_boost.find_one({'_id':todo['saving_boost_id']})

        #print(saving_boost_ac)

        todo['saving_boost'] = saving_boost_ac['saver'] if saving_boost_ac!=None else None


        todo['contribution_date_word'] = todo['contribution_date'].strftime('%d %b, %Y')
        todo['contribution_date'] = convertDateTostring(todo['contribution_date'],"%Y-%m-%d")
        

        todo['next_contribution_date_word'] = convertDateTostring(todo['next_contribution_date']) if todo['next_contribution_date']!=None else None
        todo['next_contribution_date'] = convertDateTostring(todo['next_contribution_date'],"%Y-%m-%d") if todo['next_contribution_date']!=None else None                

        


        data_list.append(todo)
    data_json = MongoJSONEncoder().encode(data_list)
    data_obj = json.loads(data_json)

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size   
    
    

    return jsonify({
        'rows': data_obj,
        'pageCount': total_pages,
        'totalRows': total_count,
        # 'extra_payload':{
        #     'total_net_saving':total_net_saving,
        #     'total_gross_saving':total_gross_saving,             
        # }
    })