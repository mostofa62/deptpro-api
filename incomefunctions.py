from datetime import datetime
from bson import ObjectId
from util import MongoJSONEncoder
from db import my_col,myclient,mydb
from incomeutil import get_single_boost, get_single_income
from app import app
from flask import Flask,request,jsonify, json
from bson.objectid import ObjectId
from bson.json_util import dumps

client = myclient
app_data = my_col('app_data')
income_monthly_log = my_col('income_monthly_log')
income_yearly_log = my_col('income_yearly_log')
income_boost_monthly_log = my_col('income_boost_monthly_log')
income = my_col('income')
income_boost = my_col('income_boost')
income_boost_transaction = my_col('income_boost_transactions')
income_transactions = my_col('income_transactions')

def income_update_next(income_ac):

    myquery = {
        '_id':ObjectId(income_ac['_id'])
    }
     
    total_gross_income = 0
    total_net_income = 0
    
    if income_ac!=None:
        total_gross_income = income_ac['total_gross_income']
        total_net_income = income_ac['total_net_income']

        income_transaction_generate = get_single_income(
            initial_gross_input=total_gross_income,
            initial_net_input=total_net_income,
            gross_input=income_ac['gross_income'],
            net_input=income_ac['net_income'],
            pay_date=income_ac['next_pay_date'],
            frequency=income_ac['repeat']['value'],
            commit=income_ac['commit'],
            income_id=ObjectId(id),
            user_id=ObjectId(income_ac['user_id'])
        )


        income_transaction_list = income_transaction_generate['income_transaction']
        total_gross_income = income_transaction_generate['total_gross_for_period']
        total_net_income = income_transaction_generate['total_net_for_period']
        next_pay_date = income_transaction_generate['next_pay_date']


        change_append_data = {
            "total_net_income":total_net_income,            
            'total_gross_income':total_gross_income,
            'next_pay_date':next_pay_date,         
            'updated_at':datetime.now()              

        }
        newvalues = { "$set": change_append_data }

        len_income_transaction = len(income_transaction_list)

        if len_income_transaction > 0:

            with client.start_session() as session:
                with session.start_transaction():

                    try:
                        c_data = income_transactions.insert_one(income_transaction_list,session=session)

                        s_data = income.update_one(myquery, newvalues, session=session)

                        i_m_log = income_monthly_log.update_one({
                             'income_id':ObjectId(id)
                        },{
                             '$set':{
                                 'updated_at':None 
                             }
                        },session=session)

                        i_y_log = income_yearly_log.update_one({
                             'income_id':ObjectId(id)
                        },{
                             '$set':{
                                 'updated_at':None 
                             }
                        },session=session)

                        result = 1 if c_data.inserted_id and s_data.modified_count and i_m_log.modified_count and i_y_log.modified_count else 0

                        if result:
                                session.commit_transaction()
                        else:
                                session.abort_transaction()
                    except Exception as ex:
                        print(ex)
                        result = 0
                        session.abort_transaction()



def income_update_next_boost(income_b):

    income_ac = income_b['income_details']
    id = income_ac['_id']
    myquery = {
        '_id':ObjectId(id)
    }
    income_transaction_list = {}
    total_gross_income = 0
    total_net_income = 0
    boost_status = {}
    len_income_transaction = 0
    result = 0
    
    starting_date_b = income_b['next_pay_date_boost'] if income_b['next_pay_date_boost'] != None else income_b['pay_date_boost'] 
    starting_amount_b = round(income_b["total_balance"],2)
    income_boost_amount = round(income_b["income_boost"],2)
    repeat_boost = income_b['repeat_boost']['value'] if income_b['repeat_boost']['value'] > 0 else None

    repeat_b = income_b['repeat_boost']['value']
    

    contribution_breakdown_b = get_single_boost(
        starting_amount_b,
        income_boost_amount,
        starting_date_b,
        repeat_boost,
        total_gross_income,
        total_net_income
        )
    breakdown_b = contribution_breakdown_b['income_transaction']
    total_balance_b = contribution_breakdown_b['total_boost_for_period']
    total_gross_income = contribution_breakdown_b['total_gross_for_period']
    total_net_income = contribution_breakdown_b['total_net_for_period']
    next_contribution_date_b = contribution_breakdown_b['next_pay_date']

    len_c_b = len(breakdown_b)
    if len_c_b > 0:
        income_transaction_list = {
                'income_id':income_ac['_id'],
                'income_boost_id':income_b['_id'],
                'commit':income_ac['commit'],
                'user_id':income_ac['user_id'],
                **breakdown_b
        }
        

    boost_status = {
        '_id':income_b['_id'],
        'next_pay_date_boost':next_contribution_date_b,
        'total_balance':total_balance_b,
        'closed_at':datetime.now() if repeat_b < 1 else None
    }
    
    len_boost_status =  len(boost_status)
    len_income_transaction = len(income_transaction_list)
    change_append_data = {
        "total_net_income":total_net_income,            
        'total_gross_income':total_gross_income,       
        'updated_at':datetime.now()              

    }
    newvalues = { "$set": change_append_data }
    if len_income_transaction > 0:
        with client.start_session() as session:
            with session.start_transaction():
                try:
                    c_data = income_transactions.insert_many(income_transaction_list,session=session)
                    s_b_k = 0
                    if len_boost_status > 0:
                        sb_data = income_boost.update_one({
                                '_id':boost_status['_id']
                                }, 
                                { "$set":{
                                    'next_pay_date_boost':boost_status['next_pay_date_boost'],
                                    'total_balance':boost_status['total_balance'],
                                    'closed_at':boost_status['closed_at']
                                
                                } 
                            },
                            session=session
                        )
                        s_b_k = 1 if sb_data.modified_count else 0 
                    s_data = income.update_one(myquery, newvalues, session=session)

                    i_m_log = income_monthly_log.update_one({
                             'income_id':ObjectId(id)
                    },{
                            '$set':{
                                'updated_at':None 
                            }
                    },session=session)

                    i_y_log = income_yearly_log.update_one({
                            'income_id':ObjectId(id)
                    },{
                            '$set':{
                                'updated_at':None 
                            }
                    },session=session)

                    
                    result = 1 if c_data.inserted_ids and s_data.modified_count  and s_b_k > 0 and i_m_log.modified_count and i_y_log.modified_count else 0
                    

                    

                    if result:
                            session.commit_transaction()
                    else:
                            session.abort_transaction()
                except Exception as ex:
                    print(ex)
                    result = 0
                    session.abort_transaction()



@app.route('/api/income-next/<string:id>', methods=['GET'])
def income_next(id:str):

    myquery = {
        'closed_at':None,
        'deleted_at':None,
        '_id':ObjectId(id)
    }
   
    income_ac = income.find_one(myquery,{
        'total_net_income':1,
        'total_gross_income':1,
        'gross_income':1,
        'net_income':1,
        'pay_date':1,
        'next_pay_date':1,
        'repeat':1,
        'commit':1,
        'user_id':1
        })
    
    total_gross_income = 0
    total_net_income = 0
    
    if income_ac!=None:
        total_gross_income = income_ac['total_gross_income']
        total_net_income = income_ac['total_net_income']

        income_transaction_generate = get_single_income(
            initial_gross_input=total_gross_income,
            initial_net_input=total_net_income,
            gross_input=income_ac['gross_income'],
            net_input=income_ac['net_income'],
            pay_date=income_ac['next_pay_date'],
            frequency=income_ac['repeat']['value'],
            commit=income_ac['commit'],
            income_id=ObjectId(id),
            user_id=ObjectId(income_ac['user_id'])
        )


        income_transaction_list = income_transaction_generate['income_transaction']
        total_gross_income = income_transaction_generate['total_gross_for_period']
        total_net_income = income_transaction_generate['total_net_for_period']
        next_pay_date = income_transaction_generate['next_pay_date']


        change_append_data = {
            "total_net_income":total_net_income,            
            'total_gross_income':total_gross_income,
            'next_pay_date':next_pay_date,         
            'updated_at':datetime.now()              

        }
        newvalues = { "$set": change_append_data }

        len_income_transaction = len(income_transaction_list)

        if len_income_transaction > 0:

            with client.start_session() as session:
                with session.start_transaction():

                    try:
                        c_data = income_transactions.insert_one(income_transaction_list,session=session)

                        s_data = income.update_one(myquery, newvalues, session=session)

                        i_m_log = income_monthly_log.update_one({
                             'income_id':ObjectId(id)
                        },{
                             '$set':{
                                 'updated_at':None 
                             }
                        },session=session)

                        i_y_log = income_yearly_log.update_one({
                             'income_id':ObjectId(id)
                        },{
                             '$set':{
                                 'updated_at':None 
                             }
                        },session=session)

                        result = 1 if c_data.inserted_id and s_data.modified_count and i_m_log.modified_count and i_y_log.modified_count else 0

                        if result:
                                session.commit_transaction()
                        else:
                                session.abort_transaction()
                    except Exception as ex:
                        print(ex)
                        result = 0
                        session.abort_transaction()

        data_json = MongoJSONEncoder().encode(income_transaction_list)
        income_transaction_list = json.loads(data_json)


        return jsonify({
            'income_transaction_list':income_transaction_list,
            'total_gross_income':total_gross_income,
            'total_net_income':total_net_income,
            'next_pay_date':next_pay_date,
            'result':result
        })


@app.route('/api/income-next-boost/<string:id>', methods=['GET'])
def income_next_boost(id:str):

    myquery = {
        'closed_at':None,
        'deleted_at':None,
        '_id':ObjectId(id)
    }
   
    income_ac = income.find_one(myquery,{
        'total_net_income':1,
        'total_gross_income':1,
        'gross_income':1,
        'net_income':1,
        'pay_date':1,
        'next_pay_date':1,
        'repeat':1,
        'commit':1,
        'user_id':1
        })
    
    income_transaction_list = []

    total_gross_income = 0
    total_net_income = 0

    

    boost_status = []
    len_income_transaction = 0
    result = 0

    if income_ac!=None:
        total_gross_income = income_ac['total_gross_income']
        total_net_income = income_ac['total_net_income']

        ### we will check any boost here
        counted_income_boost = income_boost.count_documents(
            {
                     'income.value':income_ac['_id'],
                     'deleted_at':None,
                     'closed_at':None
            }
        )

        if counted_income_boost > 0:
            income_boosts = income_boost.find(
                {
                     'income.value':income_ac['_id'],
                     'deleted_at':None,
                     'closed_at':None
                },
                # {'_id':1}
            )

            for income_b in income_boosts:
                 starting_date_b = income_b['next_pay_date_boost'] if income_b['next_pay_date_boost'] != None else income_b['pay_date_boost'] 
                 starting_amount_b = round(income_b["total_balance"],2)
                 income_boost_amount = round(income_b["income_boost"],2)
                 repeat_boost = income_b['repeat_boost']['value'] if income_b['repeat_boost']['value'] > 0 else None

                 repeat_b = income_b['repeat_boost']['value']

                 

                 contribution_breakdown_b = get_single_boost(
                      starting_amount_b,
                      income_boost_amount,
                      starting_date_b,
                      repeat_boost,
                      total_gross_income,
                      total_net_income
                      )
                 breakdown_b = contribution_breakdown_b['income_transaction']
                 total_balance_b = contribution_breakdown_b['total_boost_for_period']
                 total_gross_income = contribution_breakdown_b['total_gross_for_period']
                 total_net_income = contribution_breakdown_b['total_net_for_period']
                 next_contribution_date_b = contribution_breakdown_b['next_pay_date']

                 len_c_b = len(breakdown_b)
                 if len_c_b > 0:
                    breakdown_b = {
                         'income_id':income_ac['_id'],
                         'income_boost_id':income_b['_id'],
                         'commit':income_ac['commit'],
                         'user_id':income_ac['user_id'],
                         **breakdown_b
                    }
                    income_transaction_list.append(breakdown_b)
                
                 boost_status_data = {
                    '_id':income_b['_id'],
                    'next_pay_date_boost':next_contribution_date_b,
                    'total_balance':total_balance_b,
                    'closed_at':datetime.now() if repeat_b < 1 else None
                }
                 boost_status.append(boost_status_data)


       


    

    len_boost_status =  len(boost_status)

    len_income_transaction = len(income_transaction_list)

    change_append_data = {
        "total_net_income":total_net_income,            
        'total_gross_income':total_gross_income,       
        'updated_at':datetime.now()              

    }
    newvalues = { "$set": change_append_data }

    if len_income_transaction > 0:
        with client.start_session() as session:
            with session.start_transaction():

                try:
                    c_data = income_transactions.insert_many(income_transaction_list,session=session)

                    

                    s_b_k = 0
                    if len_boost_status > 0:

                        for b_s in  boost_status:
                            sb_data = income_boost.update_one({
                                    '_id':b_s['_id']
                                    }, 
                                    { "$set":{
                                        'next_pay_date_boost':b_s['next_pay_date_boost'],
                                        'total_balance':b_s['total_balance'],
                                        'closed_at':b_s['closed_at']
                                    
                                    } 
                                },
                                session=session
                            )
                            s_b_k = 1 if sb_data.modified_count else 0 

                    s_data = income.update_one(myquery, newvalues, session=session)


                    i_m_log = income_monthly_log.update_one({
                             'income_id':ObjectId(id)
                    },{
                            '$set':{
                                'updated_at':None 
                            }
                    },session=session)

                    i_y_log = income_yearly_log.update_one({
                            'income_id':ObjectId(id)
                    },{
                            '$set':{
                                'updated_at':None 
                            }
                    },session=session)

                    
                    result = 1 if c_data.inserted_ids and s_data.modified_count  and s_b_k > 0 and i_m_log.modified_count and i_y_log.modified_count else 0
                    

                    

                    if result:
                            session.commit_transaction()
                    else:
                            session.abort_transaction()
                except Exception as ex:
                    print(ex)
                    result = 0
                    session.abort_transaction()

    data_json = MongoJSONEncoder().encode(income_transaction_list)
    income_transaction_list = json.loads(data_json)

    

    return jsonify({
        'income_transaction_list':income_transaction_list,
        'total_gross_income':total_gross_income,
        'total_net_income':total_net_income,
        'result':result
    })

def update_current_income(user_id:str):
    commit = datetime.now()
    pipeline_log = [
        # Step 1: Match documents with pay_date in the last 12 months and not deleted
        {
            "$match": {
                "month": commit.strftime('%Y-%m'),
                "deleted_at": None,
                "closed_at":None
            }
        },
        
        # Step 2: Project to extract year and month from pay_date
        {
            "$project": {
                "total_monthly_gross_income":1,
                "total_monthly_net_income": 1,                                    
                #"month_word":1,
                "month":1            
            }
        },

        # Step 3: Group by year_month and sum the balance
        {
            "$group": {
                "_id": "$month",  # Group by the formatted month-year
                "total_monthly_net_income": {"$sum": "$total_monthly_net_income"},
                "total_monthly_gross_income": {"$sum": "$total_monthly_gross_income"},                                    
                "month": {"$first": "$month"}   # Include the month
            }
        },

        # Step 4: Create the formatted year_month_word
        {
            "$project": {
                "_id": 1,
                "total_monthly_gross_income":1,
                "total_monthly_net_income": 1,                                      
            }
        },


    
    ]

    month_wise_all = list(income_monthly_log.aggregate(pipeline_log))

    total_current_net_income = month_wise_all[0]['total_monthly_net_income'] if month_wise_all else 0
    total_current_gross_income = month_wise_all[0]['total_monthly_gross_income'] if month_wise_all else 0

    filter_query = {
        "user_id" :ObjectId(user_id)
    }

    update_document = {'$set': {
            #'minimum_payments': float(data['minimum_payments']),
            'total_current_gross_income':total_current_gross_income,
            'total_current_net_income': total_current_net_income,
                             
        }
    }

    app_datas = app_data.update_one(filter_query, update_document, upsert=True)

    app_data_log = app_datas.upserted_id!=None or app_datas.modified_count


def update_current_boost(user_id:str):
    commit = datetime.now()
    pipeline_log = [
        # Step 1: Match documents with pay_date in the last 12 months and not deleted
        {
            "$match": {
                "month": commit.strftime('%Y-%m'),
                "deleted_at": None,
                "closed_at":None
            }
        },
        
        # Step 2: Project to extract year and month from pay_date
        {
            "$project": {
                "total_monthly_boost_income": 1,                                    
                #"month_word":1,
                "month":1            
            }
        },

        # Step 3: Group by year_month and sum the balance
        {
            "$group": {
                "_id": "$month",  # Group by the formatted month-year
                "total_monthly_boost_income": {"$sum": "$total_monthly_boost_income"},                                    
                "month": {"$first": "$month"}   # Include the month
            }
        },

        # Step 4: Create the formatted year_month_word
        {
            "$project": {
                "_id": 1,
                "total_monthly_boost_income": 1,                                      
            }
        },


    
    ]

    month_wise_all = list(income_boost_monthly_log.aggregate(pipeline_log))

    total_monthly_boost_income = month_wise_all[0]['total_monthly_boost_income'] if month_wise_all else 0

    filter_query = {
        "user_id" :ObjectId(user_id)
    }

    update_document = {'$set': {
            #'minimum_payments': float(data['minimum_payments']),
            'total_current_boost_income': total_monthly_boost_income,                 
        }
    }

    app_datas = app_data.update_one(filter_query, update_document, upsert=True)

    app_data_log = app_datas.upserted_id!=None or app_datas.modified_count