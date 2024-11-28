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

    pipeline  = [


  {
      "$match": {
          "month": current_month_str,
        	"deleted_at":None
      }
  },

  {
      "$lookup": {
          "from": "income_monthly_log",
          "localField": "income_id",
          "foreignField": "income_id",
          "as": "monthlylog"
      }
  },

  {
    "$unwind": {
        "path": "$monthlylog",
        "preserveNullAndEmptyArrays": True  
    }
  },

  {
        "$group": {
        "_id": "$user_id",
        "total_net_income_per_user": {"$sum": "$net_income_xyz"},
        "total_gross_income_per_user": {"$sum": "$gross_income_xyz"}, 
        "incomes": {
            "$push": { 
                "income_id": "$income_id", 
                "net_income_xyz": "$net_income_xyz",
                "gross_income_xyz": "$gross_income_xyz",
              	"updated_at":"$monthlylog.updated_at"

            }
        }
        }
    },
		
    {
      "$unwind": {
          "path": "$incomes",
           
      }
    },

  	{
          "$match": {
              "incomes.updated_at": None,
              
              
          }
    },

  {
    "$group": {
      "_id": {
        "user_id": "$_id",
        "income_id": "$incomes.income_id"
      },
      "total_net_income_per_user": {
        "$first": "$total_net_income_per_user"
      },
      "total_gross_income_per_user": {
        "$first": "$total_gross_income_per_user"
      },
      "total_net_income_xyz": { "$sum": "$incomes.net_income_xyz" },
      "total_gross_income_xyz": { "$sum": "$incomes.gross_income_xyz" }
    }
  },

  {

    "$group": {
      "_id": "$_id.user_id",
      "total_net_income_per_user": {
        "$first": "$total_net_income_per_user"
      },
      "total_gross_income_per_user": {
        "$first": "$total_gross_income_per_user"
      },
      "incomes": {
            "$push": { 
                "income_id": "$_id.income_id", 
                "net_income_xyz": "$total_net_income_xyz",
                "gross_income_xyz": "$total_gross_income_xyz",
              	

            }
        }
    }
  }

  

  
]

    # Execute the pipeline
    result = list(income_transaction.aggregate(pipeline))

    #print(result)

    # Print the results
    for doc in result:
        user_id = doc['_id']
        app_data.update_one({
                'user_id':ObjectId(user_id)
            },{

                '$set':{                    
                    'total_monthly_gross_income':round(doc['total_gross_income_per_user'],2),
                    'total_monthly_net_income':round(doc['total_net_income_per_user'],2),
                }
            },upsert=True)
        incomes = doc['incomes']
        print("user_id", user_id)
        for entry in incomes:
            income_ac.update_one(
                {'_id':ObjectId(entry['income_id'])},
                {
                    '$set':{
                        'total_monthly_gross_income':round(entry['gross_income_xyz'],2),
                        'total_monthly_net_income':round(entry['net_income_xyz'],2),
                        
                    }
                }
            )
                
            income_monthly_log.update_one({
                'income_id':ObjectId(entry['income_id']),
                
            },{
                '$set':{
                    'total_monthly_gross_income':round(entry['gross_income_xyz'],2),
                    'total_monthly_net_income':round(entry['net_income_xyz'],2),
                    'updated_at':datetime.now(),
                    #'month':current_month_str
                }
                    })

            print('income, and data',entry['income_id'], entry['net_income_xyz'],entry['gross_income_xyz'])


#income_calculate_monthly_data()