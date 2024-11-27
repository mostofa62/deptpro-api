from datetime import datetime
from dateutil.relativedelta import relativedelta

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import my_col,myclient
from util import *

saving_ac = my_col('saving')
saving_contributions = my_col('saving_contributions')
saving_boost_contribution = my_col('saving_boost_contributions')
app_data = my_col('app_data')

def calculate_yearly_and_monthly_data():
    #now = datetime.now() +  relativedelta(months=1)
    now = datetime.now()
    current_year = now.year
    current_month = now.month
    current_month_str = f"{current_year}-{current_month:02d}" 

    # Aggregation pipeline
    # this will save for all saving id
    pipeline = [
    {
        "$match": {
            "month": current_month_str  # Match documents for the current month
        }
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
                        "deleted_at": None,  # Ensure the deleted_at field is None (active records)

                        "$or": [
                            {"current_month": None},               # Field is null
                            {"current_month": {"$exists": False}}, # Field does not exist
                            #{"current_month": current_month_str}       # Field has a non-null value
                        ]

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
            "_id": "$saving_id",  # Group by saving_id
            "saving_total_balance": {"$sum": "$contribution_i_intrs_xyz"}  # Aggregate the total balance
        }
    },
    {
        "$project": {
            "_id": 0,  # Exclude _id from the output
            "saving_id": "$_id",  # Rename _id to saving_id
            "saving_total_balance": 1
        }
    }
]
    
    # Run the aggregation
    result = list(saving_contributions.aggregate(pipeline))

    # Output the result
    if result:
        for item in result:
            
            saving_ac.update_one(
                {'_id':ObjectId(item['saving_id'])},
                {
                    '$set':{
                        'total_monthly_balance':round(item['saving_total_balance'],2),
                        'current_month':convertDateTostring(datetime.now(),'%Y-%m'),
                    }
                }
            )
            
            print(f"Saving ID: {item['saving_id']}, Total Balance: {item['saving_total_balance']}")


    # Aggregation pipeline
    #this will save for user all
    pipeline = [
    {
        "$match": {
            "month": current_month_str  # Match documents for the current month
        }
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
                        "deleted_at": None,  # Ensure the deleted_at field is None (active records)
                        "current_month": current_month_str,
                        # "$or": [
                        #     {"current_month": None},               # Field is null
                        #     {"current_month": {"$exists": False}}, # Field does not exist
                        #     {"current_month": current_month_str}       # Field has a non-null value
                        # ]

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
            "_id": "$saving_details.user_id",  # Group by user_id from the saving collection
            "total_balance_for_user": {"$sum": "$contribution_i_intrs_xyz"}  # Sum total_balance for each user
        }
    },
    {
        "$project": {
            "_id": 0,  # Exclude _id from the output
            "user_id": "$_id",  # Rename _id to user_id
            "total_balance_for_user": 1
        }
    }
]
    
    
    
    # Run the aggregation
    result = list(saving_contributions.aggregate(pipeline))

    # Output the result
    if result:
        for item in result:
            
            app_data.update_one({
                'user_id':ObjectId(item['user_id'])
            },{
                '$set':{
                    'total_monthly_saving':round(item['total_balance_for_user'],2)
                }
            },upsert=True)
            
            print(f"User ID: {item['user_id']}, Total Balance: {item['total_balance_for_user']}")

    # Aggregation pipeline
    #commeting the saving total year
    '''
    pipeline = [
    {
        "$match": {
            "month": {"$regex": f"^{current_year}-"}  # Match months of the current year
        }
    },
    {
        "$addFields": {
            "adjusted_increase_contribution": {
                "$multiply": ["$increase_contribution", "$period"]
            }
        }
    },
    {
        "$addFields": {
            "total_balance": {
                "$add": ["$interest", "$contribution", "$adjusted_increase_contribution"]
            }
        }
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
            "_id": "$saving_details.user_id",  # Group by user_id from the saving collection
            "total_balance_for_user": {"$sum": "$total_balance"}  # Sum total_balance for each user
        }
    },
    {
        "$project": {
            "_id": 0,  # Exclude _id from the output
            "user_id": "$_id",  # Rename _id to user_id
            "total_balance_for_user": 1
        }
    }
]
    
    # Run the aggregation
    result = list(saving_contributions.aggregate(pipeline))
    if result:
        for item in result:
            print(f"User ID: {item['user_id']}, Total Balance: {item['total_balance_for_user']}")
    '''


#calculate_yearly_and_monthly_data()