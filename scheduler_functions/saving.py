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
saving_monthly_log = my_col('saving_monthly_log')

def saving_calculate_yearly_and_monthly_data():
    #now = datetime.now() +  relativedelta(months=1)
    now = datetime.now()
    current_year = now.year
    current_month = now.month
    current_month_str = f"{current_year}-{current_month:02d}"

    pipeline = [
    # Step 1: Match saving_monthly_log where updated_at is null
    {
        "$match": {
            "updated_at": None
        }
    },
    # Step 2: Lookup saving_contributions by saving_id
    {
        "$lookup": {
            "from": "saving_contributions",
            "localField": "saving_id",
            "foreignField": "saving_id",
            "as": "contributions"
        }
    },
    # Step 3: Unwind the contributions array
    {
        "$unwind": {
            "path": "$contributions",
            "preserveNullAndEmptyArrays": True  # Ensure entries without contributions are preserved
        }
    },
    # Step 3.1: Match for deleted_at: None in contributions
    {
        "$match": {
            "contributions.deleted_at": None
        }
    },
    # Step 4: Match by user_id and current month string
    {
        "$match": {
            "$expr": {
                "$and": [
                    {"$eq": ["$user_id", "$contributions.user_id"]},
                    {"$eq": ["$contributions.month", current_month_str]}
                ]
            }
        }
    },
    # Step 5: Use $facet to separate saving_id and user_id groupings
    {
        "$facet": {
            "by_saving_id": [
                {
                    "$group": {
                        "_id": "$saving_id",
                        "total_contributions_per_saving": {"$sum": "$contributions.contribution_i_intrs_xyz"}
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "saving_id": "$_id",
                        "total_contributions_per_saving": 1
                    }
                }
            ],
            "by_user_id": [
                {
                    "$group": {
                        "_id": "$contributions.user_id", 
                        "total_contributions_per_user": {"$sum": "$contributions.contribution_i_intrs_xyz"}
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "user_id": "$_id",
                        "total_contributions_per_user": 1
                    }
                }
            ]
        }
    }
]
    
    result = list(saving_monthly_log.aggregate(pipeline))

    # Access the results from the facet
    by_saving_id = result[0]["by_saving_id"] if result else None
    by_user_id = result[0]["by_user_id"] if result else None

    if by_saving_id!=None:
        # Print saving_id grouped results
        print("Results grouped by saving_id:")
        for entry in by_saving_id:

            saving_ac.update_one(
                {'_id':ObjectId(entry['saving_id'])},
                {
                    '$set':{
                        'total_monthly_balance':round(entry['total_contributions_per_saving'],2),
                        
                    }
                }
            )
                
            saving_monthly_log.update_one({
                'saving_id':ObjectId(entry['saving_id']),
                
            },{
                '$set':{
                    'total_monthly_balance':round(entry['total_contributions_per_saving'],2),
                    'updated_at':datetime.now(),
                    #'month':current_month_str
                }
                    })
            print(f"Saving ID: {entry['saving_id']}, Total Contributions Per Saving: {entry['total_contributions_per_saving']}")

    if by_user_id!=None:
        # Print user_id grouped results
        print("\nResults grouped by user_id:")
        for entry in by_user_id:
            app_data.update_one({
                'user_id':ObjectId(entry['user_id'])
            },{

                '$set':{
                    'total_monthly_saving':round(entry['total_contributions_per_user'],2)
                }
            },upsert=True)
            print(f"User ID: {entry['user_id']}, Total Contributions Per User: {entry['total_contributions_per_user']}")


    


   
    
    


#saving_calculate_yearly_and_monthly_data()