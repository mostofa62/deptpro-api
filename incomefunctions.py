from datetime import datetime
from bson import ObjectId
from db import my_col,myclient,mydb
client = myclient
app_data = my_col('app_data')


income_monthly_log = my_col('income_monthly_log')
income_boost_monthly_log = my_col('income_boost_monthly_log')
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
                "month": {"$first": "$month"}   # Include the month
            }
        },

        # Step 4: Create the formatted year_month_word
        {
            "$project": {
                "_id": 1,
                "total_monthly_net_income": 1,                                      
            }
        },


    
    ]

    month_wise_all = list(income_monthly_log.aggregate(pipeline_log))

    total_current_net_income = month_wise_all[0]['total_monthly_net_income'] if month_wise_all else 0

    filter_query = {
        "user_id" :ObjectId(user_id)
    }

    update_document = {'$set': {
            #'minimum_payments': float(data['minimum_payments']),
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