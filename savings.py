import os
from flask import Flask,request,jsonify, json
#from flask_cors import CORS, cross_origin
from savingutil import calculate_breakdown, get_single_breakdown
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
category_types = my_col('category_types')
saving_source_types = my_col('saving_source_types')
contributions = my_col('saving_contributions')
saving_boost = my_col('saving_boost')
saving_boost_contributions = my_col('saving_boost_contributions')
# Helper function to calculate interest and progress
def calculate_savings(savings):
    # Calculate total savings: starting amount + total contributions + any savings boosts
    total_contributions = savings['contribution'] * savings['months_contributed']
    savings_boost = savings.get('savings_boost', 0)
    total_savings = savings['starting_amount'] + total_contributions + savings_boost
    
    # Calculate interest (assuming monthly compounding for simplicity)
    interest_rate = savings['interest_rate'] / 100
    months = savings['months_contributed']
    interest_earned = total_savings * ((1 + interest_rate / 12) ** months - 1)
    
    # Update progress toward goal
    progress = (total_savings + interest_earned) / savings['goal_amount'] * 100
    
    return total_savings, interest_earned, progress



@app.route('/api/delete-saving', methods=['POST'])
def delete_saving():
    if request.method == 'POST':
        data = json.loads(request.data)

        id = data['id']
        key = data['key']
        action = 'Deleted' if key < 2 else 'Closed'
        field = 'deleted_at' if key < 2 else 'closed_at'

        saving_account_id = None
        message = None
        error = 0
        deleted_done = 0

        myquery = { "_id" :ObjectId(id)}
        previous_saving = collection.find_one(myquery,{'commit':1})
        previous_commit = previous_saving['commit']

        with client.start_session() as session:
                with session.start_transaction():

                    try:
                        myquery = { "_id" :ObjectId(id)}

                        newvalues = { "$set": {                                     
                                        field:datetime.now()                
                                    } }
                        saving_account_data =  collection.update_one(myquery, newvalues, session=session)
                        saving_account_id = id if saving_account_data.modified_count else None

                        #delete previous commits data
                        saving_data_delete = contributions.update_many({
                            'saving_id':ObjectId(saving_account_id),
                            'commit':previous_commit
                        },{
                            "$set":{
                                field:datetime.now()
                            }
                        },session=session)

                        saving_boost_delete = saving_boost.update_many({
                            'saving.value':ObjectId(saving_account_id),
                        },{
                            "$set":{
                                field:datetime.now()
                            }
                        },session=session)


                        saving_boost_c_delete = saving_boost_contributions.update_many({
                            'saving_id':ObjectId(saving_account_id),
                        },{
                            "$set":{
                                field:datetime.now()
                            }
                        },session=session)


                        error = 0 if saving_account_data.modified_count and saving_data_delete.modified_count else 1
                        deleted_done = 1 if saving_account_data.modified_count and saving_data_delete.modified_count else 0
                        if deleted_done:
                            message = f'Saving account {action} Successfully'
                            session.commit_transaction()
                        else:
                            message = f'Saving account {action} Failed'
                            session.abort_transaction()            

                    except Exception as ex:
                        saving_account_id = None
                        print('Saving account Save Exception: ',ex)
                        message = f'Saving account {action} Failed'
                        error  = 1
                        deleted_done = 0
                        session.abort_transaction()
        
        return jsonify({
            "saving_account_id":saving_account_id,
            "message":message,
            "error":error,
            "deleted_done":deleted_done
        })


@app.route("/api/saving-all/<string:id>", methods=['GET'])
def get_saving_all(id:str):
    saving = collection.find_one(
        {"_id":ObjectId(id)},
        {"_id":0}
        )
    
    saving['starting_date_word'] = convertDateTostring(saving['starting_date'],'%d %b, %Y')
    saving['starting_date'] = convertDateTostring(saving['starting_date'],"%Y-%m-%d")

    saving['next_contribution_date_word'] = convertDateTostring(saving['next_contribution_date'],'%d %b, %Y')
    saving['next_contribution_date'] = convertDateTostring(saving['next_contribution_date'],"%Y-%m-%d")


    saving['goal_reached_word'] = convertDateTostring(saving['goal_reached'],'%d %b, %Y')
    saving['goal_reached'] = convertDateTostring(saving['goal_reached'],"%Y-%m-%d")
      
    saving['user_id'] = str(saving['user_id'])

    
    category_type = my_col('category_types').find_one(
        {"_id":saving['category']['value']},
        {"_id":0,"name":1}
        )
    
    
    saving['category'] = category_type['name']

    saving['repeat'] = saving['repeat']['label']

    saving['interest_type'] = saving['interest_type']['label']
    saving['savings_strategy'] = saving['savings_strategy']['label']
    


   
    

    return jsonify({
        "payLoads":{
            "saving":saving
        }
    })

@app.route('/api/saving-typewise-info/<string:userid>', methods=['GET'])
def get_typewise_saving_info(userid:str):

    # Fetch the saving type cursor
    saving_type_cursor = my_col('category_types').find(
        {"deleted_at": None},
        {'_id': 1, 'name': 1}
    )

    # Create a list of _id values
    savingtype_id_list = [item['_id'] for item in saving_type_cursor]


    pipeline = [
        # Step 1: Match documents with category.value in billtype_id_list
        {
            "$match": {
                "category.value": {"$in": savingtype_id_list},
                "deleted_at": None,
                "closed_at":None,
                'user_id':ObjectId(userid)
            }
        },

        # Step 2: Lookup to join category collection to get the name (label)
        {
            "$lookup": {
                "from": "category_types",                # The collection to join
                "localField": "category.value",    # Field from the current collection
                "foreignField": "_id",              # Field from the category collection
                "as": "category_info"                   # Resulting array field for joined data
            }
        },

        # Step 3: Unwind the category_info array to flatten it
        {"$unwind": "$category_info"},

        # Step 4: Group by category.value and count occurrences, include category name
        {
            "$group": {
                "_id": "$category.value",          # Group by category.value
                "count": {"$sum": 1},               # Count occurrences per bill type
                "balance": {"$sum": "$goal_amount"},  # Sum balance and monthly_interest
                "name": {"$first": "$category_info.name"}  # Get the first name (label)
            }
        },

        # Step 5: Calculate the total count and total balance by summing up all the individual counts and balances
        {
            "$group": {
                "_id": None,                        # No specific grouping field, aggregate the entire collection
                "total_count": {"$sum": "$count"},  # Sum all the 'count' values from the grouped results
                "total_balance": {"$sum": "$balance"},  # Sum the already calculated balance (which includes balance and monthly_interest)
                "grouped_results": {"$push": "$$ROOT"}  # Preserve all grouped results in an array
            }
        },

        # Step 6: Use $project to format the output
        {
            "$project": {
                "_id": 0,                           # Remove the _id field
                "total_count": 1,                   # Include the total count
                "total_balance": 1,                 # Include the total balance
                "grouped_results": 1                # Include the grouped results
            }
        }
    ]

    # Perform the aggregation
    category_type_all = list(collection.aggregate(pipeline))

    category_type_counts = category_type_all[0]['grouped_results'] if category_type_all else []
    total_category_type = category_type_all[0]['total_count'] if category_type_all else 0
    total_balance = category_type_all[0]['total_balance'] if category_type_all else 0
    if len(category_type_counts) > 0:
        data_json = MongoJSONEncoder().encode(category_type_counts)
        category_type_counts = json.loads(data_json)

     # Fetch bill type names
    category_types = my_col('category_types').find({'_id': {'$in': savingtype_id_list}})    
    category_type_names = {str(d['_id']): d['name'] for d in category_types}

    twelve_months_ago = datetime.now() - timedelta(days=365)

    print(twelve_months_ago)

    

    
    

    pipeline = [
    # Step 1: Match documents with starting_date in the last 12 months and not deleted
    {
        "$match": {
            "starting_date": {"$gte": twelve_months_ago},
            "deleted_at": None
        }
    },
    
    # Step 2: Project to extract year and month from starting_date
    {
        "$project": {
            "starting_amount": 1,
            "goal_amount": 1,
            "year_month": {
                "$dateToString": {
                    "format": "%Y-%m",  # Format as "YYYY-MM"
                    "date": "$starting_date"
                }
            },
            "month": {
                "$dateToString": {
                    "format": "%m",  # Extract the month number (01-12)
                    "date": "$starting_date"
                }
            },
            "year": {
                "$dateToString": {
                    "format": "%Y",  # Extract the year
                    "date": "$starting_date"
                }
            }
        }
    },

    # Step 3: Group by year_month and sum the balance
    {
        "$group": {
            "_id": "$year_month",  # Group by the formatted month-year
            "total_balance": {"$sum": "$starting_amount"},
            "total_goal_amount": {"$sum": "$goal_amount"},
            "year": {"$first": "$year"},  # Include the year
            "month": {"$first": "$month"}   # Include the month
        }
    },

    # Step 4: Create the formatted year_month_word
    {
        "$project": {
            "_id": 1,
            "total_balance": 1,
            "total_goal_amount":1,
            "year_month_word": {
                "$concat": [
                    {"$substr": [
                        {"$arrayElemAt": [
                            ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                            { "$subtract": [{ "$toInt": "$month" }, 1] }  # Convert month string to integer, { "$subtract": [{ "$toInt": "$month" }, 1] }  // Adjust for zero-based index
                        ]}, 0, 3  # Get the first 3 letters of the month
                    ]},
                    ", ",
                    "$year"  # Append the year
                ]
            }
        }
    },

    # Step 5: Optionally, sort by year_month
    {
        "$sort": {
            "_id": 1  # Sort in ascending order of year_month
        }
    },

    # Step 6: Limit to 12 rows
    {
        "$limit": 12  # Limit the output to the most recent 12 months
    },

    # Step 7: Calculate the total count and total balance
    {
        "$group": {
            "_id": None,  # No specific grouping field, aggregate the entire collection
            "total_count": {"$sum": 1},  # Count the number of months (or documents)
            "total_balance": {"$sum": "$total_balance"},  # Sum all the 'total_balance' values from the grouped results
            "total_goal_amount": {"$sum": "$total_goal_amount"},
            "grouped_results": {"$push": {  # Preserve all grouped results in an array
                "year_month": "$_id",
                "year_month_word": "$year_month_word",
                "total_balance": "$total_balance",
                "total_goal_amount":"$total_goal_amount"
            }}
        }
    },

    # Step 8: Use $project to format the output
    {
        "$project": {
            "_id": 0,                           # Remove the _id field
            #"total_count": 1,                   # Include the total count
            "total_balance": 1,
            "total_goal_amount":1,                 # Include the total balance
            "grouped_results": 1                # Include the grouped results
        }
    }
    
]
    
    
    
    year_month_wise_all = list(collection.aggregate(pipeline))

    year_month_wise_counts = year_month_wise_all[0]['grouped_results'] if year_month_wise_all else []
    #year_month_wise_type_t_count= year_month_wise_all[0]['total_count'] if year_month_wise_all else 0
    year_month_wise_balance = year_month_wise_all[0]['total_balance'] if year_month_wise_all else 0
    if len(year_month_wise_counts) > 0:
        data_json = MongoJSONEncoder().encode(year_month_wise_counts)
        year_month_wise_counts = json.loads(data_json)

    return jsonify({
        "payLoads":{            
            "category_type_counts":category_type_counts,
            "total_category_type":total_category_type,
            "total_balance":total_balance,
            "category_type_names":category_type_names,
            "year_month_wise_counts":year_month_wise_counts,
            "year_month_wise_balance":year_month_wise_balance


        }        
    })

@app.route("/api/saving/<string:id>", methods=['GET'])
def view_saving(id:str):
    saving = collection.find_one(
        {
            "_id":ObjectId(id),
            'goal_reached':None,
        },
        {
            "_id":0,
            "commit":0,
            'goal_reached':0,
            'progress':0,
            'next_contribution_date':0,
            "created_at":0,
            "updated_at":0,
            "deleted_at":0,
            "closed_at":0,
            "total_balance":0
         
        }
        )
    
    if saving != None:
        saving['starting_date'] = convertDateTostring(saving['starting_date'],"%Y-%m-%d")
        
        saving['user_id'] = str(saving['user_id'])

        
        category_type = my_col('category_types').find_one(
            {"_id":saving['category']['value']},
            {"_id":0,"name":1}
            )
        
        saving['category']['value'] = str(saving['category']['value'])
        saving['category']['label'] = category_type['name']


   
    

    return jsonify({
        "saving":saving
    })

@app.route('/api/saving/<string:user_id>', methods=['POST'])
def list_saving(user_id:str):

    action  = request.args.get('action', None)
    print(action)

    current_month = datetime.now().strftime('%Y-%m')
    data = request.get_json()
    page_index = data.get('pageIndex', 0)
    page_size = data.get('pageSize', 10)
    global_filter = data.get('filter', '')
    sort_by = data.get('sortBy', [])

    # Construct MongoDB filter query
    query = {
        #'role':{'$gte':10}
        "user_id":ObjectId(user_id),
        "deleted_at": None,
        "closed_at": None,
        "goal_reached":None
    }

    if action!=None:
        query = {
            "user_id": ObjectId(user_id),
            "deleted_at": None,
            "$or": [
                {"goal_reached": {"$ne": None}},  # deleted_at is not None
                {"closed_at": {"$ne": None}},    # or closed_at is not None
                
            ]
        }

    if global_filter:

        #saving type filter
        category_types = my_col('category_types').find(
                {'name':{"$regex":global_filter,"$options":"i"}},
                {'_id':1}
            )
        category_types_list = list(category_types)
        category_types_id_list = [d.pop('_id') for d in category_types_list]

        pattern_str = r'^\d{4}-\d{2}-\d{2}$'
        starting_date = None        
        #try:
        if re.match(pattern_str, global_filter):
            starting_date = datetime.strptime(global_filter,"%Y-%m-%d")            
        #except ValueError:
        else:
            starting_date = None            

        query["$or"] = [
            
            {"saver": {"$regex": global_filter, "$options": "i"}},            
            {"starting_date":starting_date},            
            {"category.value": {"$in":category_types_id_list}},                 
            # Add other fields here if needed
        ]

    # Construct MongoDB sort parameters
    sort_params = [
        ('created_at',-1)
    ]
    for sort in sort_by:
        sort_field = sort['id']
        sort_direction = -1 if sort['desc'] else 1
        sort_params.append((sort_field, sort_direction))

    # Fetch data from MongoDB
    if sort_params:
        cursor = collection.find(query).sort(sort_params).skip(page_index * page_size).limit(page_size)
    else:
        # Apply default sorting or skip sorting
        cursor = collection.find(query).skip(page_index * page_size).limit(page_size)

    total_count = collection.count_documents(query)
    #data_list = list(cursor)
    data_list = []

    total_monthly_saving = 0

    for todo in cursor:
        monthly_saving_boost = 0
        monthly_saving = 0
        if todo['category']!=None:
            category_id = todo['category']['value']
            category_type = my_col('category_types').find_one(
            {"_id":category_id},
            {"_id":0,"name":1}
            )
            todo['category'] =  category_type['name']

            '''

            #monthly savings calcualtion
            pipeline = [
                # Step 1: Match documents
                { 
                    "$match":{
                        'month':current_month,
                        'saving_id':todo['_id']
                    }  
                },

                {
                    "$group": {
                        "_id": "$month",
                        "max_total_balance": { "$max": "$total_balance" },  # Max balance for each saving_id in the month
                        
                        #"total_contribution": { "$sum": "$contribution" },  # Sum of contributions
                        "month_word": { "$first": "$month_word" },          # Include month_word for formatting
                        "month": { "$first": "$month" }                     # Include the month for further grouping
                    }
                },

                # Step 4: Project the fields you want
                {
                    "$project": {
                        "_id": 0,
                        "max_total_balance": 1,
                        
                        #"total_contribution": 1,
                        #"month_word": 1
                    }
                },

            ]

            year_month_wise_all = list(contributions.aggregate(pipeline))

            monthly_saving = year_month_wise_all[0]['max_total_balance'] if year_month_wise_all else 0
            total_monthly_saving +=monthly_saving 
            '''

            saving_boosts = my_col('saving_boost').find(
                {
                    'saving.value':ObjectId(todo['_id']),
                    'deleted_at':None,
                    'closed_at':None
                },
                {'_id':1}
            )
            saving_boost_id_list = []
            saving_boost_list = list(saving_boosts)
            if len(saving_boost_list) > 0:
                saving_boost_id_list = [d.pop('_id') for d in saving_boost_list]

                if len(saving_boost_id_list) > 0:
                    print('saving_boost_id_list',saving_boost_id_list)



            

            # if len(saving_boost_id_list) > 0:
            #     pipeline=[

            #     ]
        

        todo['starting_date'] = convertDateTostring(todo['starting_date'])
        todo['next_contribution_date'] = convertDateTostring(todo['next_contribution_date'])
        todo['goal_reached'] = convertDateTostring(todo['goal_reached']) if todo['goal_reached']!=None else None 
        todo['monthly_saving_boost'] = monthly_saving_boost 
        todo['monthly_saving'] = round(todo['total_monthly_balance'],2) if 'total_monthly_balance' in todo else 0
        


        data_list.append(todo)
    data_json = MongoJSONEncoder().encode(data_list)
    data_obj = json.loads(data_json)

    # Calculate total pages
    total_pages = (total_count + page_size - 1) // page_size


    #total balance , interest, monthly intereset paid off
    # Aggregate query to sum the balance field
    pipeline = [
        {"$match": query},  # Filter by user_id        
        {"$group": {"_id": None, 
                    "total_goal_amount": {"$sum": "$goal_amount"},
                    "total_starting_amount":{"$sum": "$starting_amount"},
                    "total_contribution" :{"$sum": "$contribution"}                                      
                    }}  # Sum the balance
    ]

    # Execute the aggregation pipeline
    result = list(collection.aggregate(pipeline))

     # Extract the total balance from the result
    total_goal_amount = result[0]['total_goal_amount'] if result else 0
    total_starting_amount = result[0]['total_starting_amount'] if result else 0
    total_contribution = result[0]['total_contribution'] if result else 0

    total_monthly_saving  = round(total_monthly_saving,2)

    print('total_monthly_saving',total_monthly_saving)
        
    return jsonify({
        'rows': data_obj,
        'pageCount': total_pages,
        'totalRows': total_count,
        'extra_payload':{
            'total_goal_amount':total_goal_amount,
            'total_starting_amount':total_starting_amount,
            'total_contribution':total_contribution,
            'total_monthly_saving':total_monthly_saving                       
        }
    })


def newEntryOptionData(data_obj:any, collectionName:str, user_id:str):

    

    if data_obj == None:
        return data_obj

    if '__isNew__' in data_obj:
        collecObj =  my_col(collectionName).insert_one({
            'name':data_obj['label'],
            'parent':None,
            'deleted_at':None,
            'user_id':ObjectId(user_id)
        })

        if collecObj.inserted_id != None:
            return {'value': collecObj.inserted_id}
    else:

        if data_obj['value'] == '':
            return None        
        else:
            return {'value': ObjectId(data_obj['value'])}



@app.route('/api/save-saving-account/<string:id>', methods=['POST'])
async def update_saving(id:str):
    if request.method == 'POST':
        data = json.loads(request.data)

        user_id = data['user_id']

        saving_id = id
        message = ''
        result = 0

        myquery = { "_id" :ObjectId(id)}
        previous_saving = collection.find_one(myquery)

        if previous_saving['goal_reached'] !=None:
            saving_id = None
            print('Saving Save Exception: ',previous_saving['goal_reached'])
            result = 0
            message = 'Saving account goal reached'

            return jsonify({
                "saving_id":saving_id,
                "message":message,
                "result":result
            })


        goal_amount = round(float(data.get("goal_amount", 0)),2)
        interest = round(float(data.get("interest", 0)),2)
        starting_amount = round(float(data.get("starting_amount", 0)),2)
        contribution = round(float(data.get("contribution", 0)),2)
        i_contribution = round(float(data.get("increase_contribution_by", 0)),2)
        repeat = data['repeat']['value'] if data['repeat']['value'] > 0 else None

        previous_goal_amount = float(previous_saving['goal_amount'])
        previous_interest = float(previous_saving['interest'])
        previous_starting_amount = float(previous_saving['starting_amount'])
        previous_contribution = float(previous_saving['contribution'])
        previous_i_contribution = float(previous_saving['increase_contribution_by'])
        previous_repeat = previous_saving['repeat']['value'] if previous_saving['repeat']['value'] > 0 else None
        previous_commit = previous_saving['commit']
        starting_date = previous_saving['starting_date']

        change_goal_amount = False if are_floats_equal(previous_goal_amount, goal_amount) else True
        change_interest = False if are_floats_equal(previous_interest, interest) else True
        change_starting_amount = False if are_floats_equal(previous_starting_amount, starting_amount) else True
        change_contribution = False if are_floats_equal(previous_contribution, contribution) else True
        change_i_contribution = False if are_floats_equal(previous_i_contribution, i_contribution) else True

        change_repeat = False if previous_repeat == repeat else True

        any_change = change_goal_amount or change_interest or change_starting_amount or change_contribution or change_i_contribution or change_repeat

        print('change_goal_amount', change_goal_amount)
        print('change_interest', change_interest)
        print('change_starting_amount', change_starting_amount)
        print('change_contribution', change_contribution)
        print('change_contribution_by', change_i_contribution)
        print('change_repeat', change_repeat)

        print('any_change', any_change)

        breakdown = []

        append_data = {
            'category':newEntryOptionData(data['category'],'category_types',user_id),                
            'user_id':ObjectId(user_id),
            'goal_amount':goal_amount,            
            'interest':interest,
            'starting_amount':starting_amount,
            'contribution':contribution,
            'increase_contribution_by':i_contribution,                    
            "updated_at":datetime.now(),                                                           

        }
                
        if any_change:
                                   
            contribution_breakdown = calculate_breakdown(starting_amount,contribution,interest, goal_amount, starting_date,repeat,i_contribution)
            breakdown = contribution_breakdown['breakdown']
            len_breakdown = len(breakdown)
            total_balance = contribution_breakdown['total_balance']
            progress  = contribution_breakdown['progress']
            next_contribution_date = contribution_breakdown['next_contribution_date']
            goal_reached = contribution_breakdown['goal_reached']
            period = contribution_breakdown['period']


            if next_contribution_date == None:
                goal_reached = goal_reached if len_breakdown > 0 else None

            commit = datetime.now() 

            change_append_data = {
                'period':period,
                "goal_reached":goal_reached,            
                'next_contribution_date':next_contribution_date,
                'total_balance':total_balance, 
                'progress':progress,
                'commit':commit,
                'current_month':None        

            }

            append_data = append_data | change_append_data

        
        


        

        

        
        merge_data = data | append_data

        del merge_data['starting_date']        

        newvalues = { "$set": merge_data }

        if len_breakdown < 1:
            
            saving_data = collection.update_one(myquery, newvalues)            
            result = 1 if saving_data.modified_count else 0

            if result:
                message = 'Saving account update Succefull'
              
            else:
                message = 'Saving account update Failed'
        else:

            with client.start_session() as session:
                with session.start_transaction():
            
                    try:

                        breakdown_data = []
                        for todo in breakdown:
                            breakdown_data.append({
                                'saving_id':ObjectId(id),
                                'deleted_at':None,
                                'closed_at':None,
                                #"goal_reached":goal_reached,
                                'commit':commit,
                                'user_id':ObjectId(user_id),
                                **todo
                            })


                        if len(breakdown_data)> 0:
                            contribution_data = contributions.insert_many(breakdown_data,session=session )
                    
                                                
                        saving_data = collection.update_one(myquery,newvalues,session=session)

                        #delete previous commits data
                        saving_data_delete = contributions.update_many({
                            'saving_id':ObjectId(id),
                            'commit':previous_commit
                        },{
                            "$set":{
                                'deleted_at':datetime.now()
                            }
                        },session=session)
                        result = 1 if saving_id!=None and contribution_data.acknowledged and saving_data.modified_count and saving_data_delete.modified_count else 0
                        
                        if result:
                            message = 'Saving account updated Succefull'
                            session.commit_transaction()
                        else:
                            message = 'Saving account updated Failed'
                            session.abort_transaction()

                    except Exception as ex:
                        saving_id = None
                        print('Saving Save Exception: ',ex)
                        result = 0
                        message = 'Saving account updated Failed'
                        session.abort_transaction()


           
           
       

        return jsonify({
            "saving_id":saving_id,
            "message":message,
            "result":result
        })
    





@app.route('/api/save-saving-account', methods=['POST'])
async def save_saving():
    if request.method == 'POST':
        data = json.loads(request.data)

        user_id = data['user_id']

        saving_id = None
        message = ''
        result = 0

        starting_date = convertStringTodate(data['starting_date'])
        goal_amount = round(float(data.get("goal_amount", 0)),2)
        interest = round(float(data.get("interest", 0)),2)
        starting_amount = round(float(data.get("starting_amount", 0)),2)
        contribution = round(float(data.get("contribution", 0)),2)
        i_contribution = round(float(data.get("increase_contribution_by", 0)),2)
        repeat = data['repeat']['value'] if data['repeat']['value'] > 0 else None
        

        commit = datetime.now()            
        goal_reached = None
                
        

        contribution_breakdown = calculate_breakdown(starting_amount,contribution,interest, goal_amount, starting_date,repeat,i_contribution)
        breakdown = contribution_breakdown['breakdown']
        total_balance = contribution_breakdown['total_balance']
        total_balance_xyz = contribution_breakdown['total_balance_xyz']
        progress  = contribution_breakdown['progress']
        next_contribution_date = contribution_breakdown['next_contribution_date']
        goal_reached = contribution_breakdown['goal_reached']
        period = contribution_breakdown['period']

        len_breakdown = len(breakdown)

        if next_contribution_date == None:
            goal_reached = goal_reached if len_breakdown > 0 else None

        append_data = {
            'category':newEntryOptionData(data['category'],'category_types',user_id),                
            'user_id':ObjectId(user_id),
            'goal_amount':goal_amount,
            'interest':interest,
            'starting_amount':starting_amount,
            'contribution':contribution,
            'increase_contribution_by':i_contribution,        
            "created_at":datetime.now(),
            "updated_at":datetime.now(),
            "deleted_at":None,
            "closed_at":None,
            "goal_reached":goal_reached,
            'starting_date':starting_date,
            'next_contribution_date':next_contribution_date,
            'total_balance':total_balance,
            'total_balance_xyz':total_balance_xyz, 
            'progress':progress,
            'period':period,
            'commit':commit                                             

        }
        merge_data = data | append_data

        if len_breakdown < 1:
            saving_data = collection.insert_one(merge_data)
            saving_id = str(saving_data.inserted_id)
            result = 1 if saving_id!=None else 0

            if result:
                message = 'Saving account added Succefull'
              
            else:
                message = 'Saving account addition Failed'
                

        else:
            

            with client.start_session() as session:
                with session.start_transaction():
            
                    try:
                        
                        saving_data = collection.insert_one(merge_data,session=session)

                        breakdown_data = []
                        for todo in breakdown:
                            breakdown_data.append({
                                'saving_id':saving_data.inserted_id,
                                'deleted_at':None,
                                'closed_at':None,
                                #"goal_reached":goal_reached,
                                'commit':commit,
                                'user_id':ObjectId(user_id),
                                **todo
                            })
                        
                        contribution_data = contributions.insert_many(breakdown_data,session=session )

                        saving_id = str(saving_data.inserted_id)

                        saving_query = {
                            "_id" :ObjectId(saving_id)
                        }

                        newvalues = { "$set": {                                                     
                            "goal_reached":goal_reached,
                            'current_month':None,                                                                                               
                            "updated_at":datetime.now()
                        } }
                        saving_data = collection.update_one(saving_query,newvalues,session=session)
                        result = 1 if saving_id!=None and contribution_data.acknowledged and saving_data.modified_count else 0
                        
                        if result:
                            message = 'Saving account added Succefull'
                            session.commit_transaction()
                        else:
                            message = 'Saving account addition Failed'
                            session.abort_transaction()

                    except Exception as ex:
                        saving_id = None
                        print('Saving Save Exception: ',ex)
                        result = 0
                        message = 'Saving account addition Failed'
                        session.abort_transaction()

        return jsonify({
            "saving_id":saving_id,
            "message":message,
            "result":result
        })