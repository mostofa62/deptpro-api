from datetime import datetime
from dateutil.relativedelta import relativedelta

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import my_col,myclient
from util import *

income_ac = my_col('income')
income_transaction = my_col('income_transactions')
income_monthly_log = my_col('income_monthly_log')
income_yearly_log = my_col('income_yearly_log')
app_data = my_col('app_data')


def income_calculate_yearly_data():
    now = datetime.now()
    current_year = now.year
    current_year_str = f"^{current_year}-"

def income_calculate_monthly_data():

    now = datetime.now()
    current_year = now.year
    current_month = now.month    
    current_month_str = f"{current_year}-{current_month:02d}"
    
    pipeline = [
    # Step 1: Match income_monthly_log where updated_at is null
    {
        "$match": {
            "updated_at": None
        }
    },
    # Step 2: Lookup income_transactions by income_id
    {
        "$lookup": {
            "from": "income_transactions",
            "localField": "income_id",
            "foreignField": "income_id",
            "as": "transactions"
        }
    },
    # Step 3: Unwind the transactions array
    {
        "$unwind": {
            "path": "$transactions",
            #"preserveNullAndEmptyArrays": True  # Ensure entries without transactions are preserved
        }
    },
    # Step 3.1: Match for deleted_at: None in transactions
    {
        "$match": {
            "transactions.deleted_at": None
        }
    },
    # Step 4: Match by user_id and current month string
    {
        "$match": {
            "$expr": {
                "$and": [
                    {"$eq": ["$user_id", "$transactions.user_id"]},
                    {"$eq": ["$transactions.month", current_month_str]}
                ]
            }
        }
    },
    # Step 5: Use $facet to separate income_id and user_id groupings
    {
        "$facet": {
            "by_income_id": [
                {
                    "$group": {
                        "_id": "$income_id",
                        "total_net_income_per_income": {"$sum": "$transactions.net_income_xyz"},
                        "total_gross_income_per_income": {"$sum": "$transactions.gross_income_xyz"}
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "income_id": "$_id",
                        "total_net_income_per_income": 1,
                        "total_gross_income_per_income": 1
                    }
                }
            ],
            "by_user_id": [
                {
                    "$group": {
                        "_id": "$transactions.user_id",
                        "total_net_income_per_user": {"$sum": "$transactions.net_income_xyz"},
                        "total_gross_income_per_user": {"$sum": "$transactions.gross_income_xyz"}                        
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "user_id": "$_id",
                        "total_net_income_per_user": 1,
                        "total_gross_income_per_user":1
                    }
                }
            ]
        }
    }
]
        

    result = list(income_monthly_log.aggregate(pipeline))

    # Access the results from the facet
    by_income_id = result[0]["by_income_id"] if result else None
    by_user_id = result[0]["by_user_id"] if result else None

    if by_income_id!=None:
        # Print income_id grouped results
        print("Results grouped by income_id:")
        for entry in by_income_id:

            income_ac.update_one(
                {'_id':ObjectId(entry['income_id'])},
                {
                    '$set':{
                        'total_monthly_gross_income':round(entry['total_gross_income_per_income'],2),
                        'total_monthly_net_income':round(entry['total_net_income_per_income'],2),
                        
                    }
                }
            )
                
            income_monthly_log.update_one({
                'income_id':ObjectId(entry['income_id']),
                
            },{
                '$set':{
                    'total_monthly_gross_income':round(entry['total_gross_income_per_income'],2),
                    'total_monthly_net_income':round(entry['total_net_income_per_income'],2),
                    'updated_at':datetime.now(),
                    #'month':current_month_str
                }
                    })
            print(f"Income ID: {entry['income_id']}, Total Transactions Per Income: {entry['total_net_income_per_income']}")

    if by_user_id!=None:
        # Print user_id grouped results
        print("\nResults grouped by user_id:")
        for entry in by_user_id:
            app_data.update_one({
                'user_id':ObjectId(entry['user_id'])
            },{

                '$set':{                    
                    'total_monthly_gross_income':round(entry['total_gross_income_per_user'],2),
                    'total_monthly_net_income':round(entry['total_net_income_per_user'],2),
                }
            },upsert=True)
            print(f"User ID: {entry['user_id']}, Total Transactions Per User: {entry['total_net_income_per_user']}")



income_calculate_monthly_data()