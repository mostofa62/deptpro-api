from datetime import datetime
from dateutil.relativedelta import relativedelta
import time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import my_col,myclient
from util import *
from incomefunctions import income_update_next, income_update_next_boost

income_ac = my_col('income')
income_bst_ac = my_col('income_boost')
income_transaction = my_col('income_transactions')
income_monthly_log = my_col('income_monthly_log')
income_yearly_log = my_col('income_yearly_log')
app_data = my_col('app_data')



def transaction_update_income():
    
    now_two = datetime.now() +  relativedelta(days=1)
    now = datetime.now()
    
    print('UPDATING INCOME TRANSACTION FOR LESS THAN:',now,now_two)
    
    query = {
        "$or": [
            {"next_pay_date": {"$ne": None, "$lt": now_two, "$gt": now}},  # next_pay_date exists and is between now and now_two
            {"next_pay_date": None, "pay_date": {"$lt": now_two, "$gt": now}}  # next_pay_date is null, and pay_date is between now and now_two
        ],
        'closed_at': None,
        'deleted_at': None
    }

    income_list = income_ac.find(query)
    for inc in income_list:
        income_update_next(inc)
        time.sleep(1)


    pipeline = [
    {
        "$match": {
            "$or": [
                {"next_pay_date_boost": {"$ne": None, "$lt": now, "$gt": now}},  # `next_pay_date_boost` exists and is within range
                {"next_pay_date_boost": None, "pay_date_boost": {"$lt": now, "$gt": now}}  # `next_pay_date_boost` is null, `pay_date_boost` is within range
            ],
            "closed_at": None,
            "deleted_at": None
        }
    },
    {
        "$lookup": {
            "from": "income",             # Name of the income collection
            "localField": "income_id",    # Field in the current collection
            "foreignField": "_id",        # Field in the income collection
            "as": "income_details"        # Name of the resulting array field
        }
    },
    {
        "$unwind": {
            "path": "$income_details",    # Unwind the income details array
            "preserveNullAndEmptyArrays": False  # Remove documents without a match
        }
    }
]
    
    


    income_boost_list = list(income_bst_ac.aggregate(pipeline))
    for inc_bst in income_boost_list:
        income_update_next_boost(inc_bst)
        time.sleep(1)



def pipeline_result(current_str:str, relationPrefix:str='monthly'):

    search_str = { "$regex":current_str} if relationPrefix == 'yearly' else current_str

    pipeline  = [


  {
      "$match": {
          "month": search_str,
           "deleted_at":None
      }
  },

  {
      "$lookup": {
          "from": f"income_{relationPrefix}_log",
          "localField": "income_id",
          "foreignField": "income_id",
          "as": f"{relationPrefix}log"
      }
  },

  {
    "$unwind": {
        "path": f"${relationPrefix}log",
        "preserveNullAndEmptyArrays": True  
    }
  },

  {
        "$group": {
        "_id": "$user_id",
        "total_net_income_per_user": {"$sum": "$net_income"},
        "total_gross_income_per_user": {"$sum": "$gross_income"}, 
        "incomes": {
            "$push": { 
                "income_id": "$income_id", 
                "net_income": "$net_income",
                "gross_income": "$gross_income",
              	"updated_at":f"${relationPrefix}log.updated_at"

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
      "total_net_income": { "$sum": "$incomes.net_income" },
      "total_gross_income": { "$sum": "$incomes.gross_income" }
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
                "net_income": "$total_net_income",
                "gross_income": "$total_gross_income",
              	

            }
        }
    }
  }

  

  
]

    # Execute the pipeline
    result = list(income_transaction.aggregate(pipeline))

    return result
    



def income_calculate_yearly_data():
    now = datetime.now()
    current_year = now.year
    current_year_str = f"^{current_year}-"

    print('YEARLY', current_year_str)

    result = pipeline_result(current_year_str,'yearly')

    # Print the results
    for doc in result:
        user_id = doc['_id']
        app_data.update_one({
                'user_id':ObjectId(user_id)
            },{

                '$set':{                    
                    'total_yearly_gross_income':round(doc['total_gross_income_per_user'],2),
                    'total_yearly_net_income':round(doc['total_net_income_per_user'],2),
                }
            },upsert=True)
        incomes = doc['incomes']
        print("user_id", user_id)
        for entry in incomes:
            income_ac.update_one(
                {'_id':ObjectId(entry['income_id'])},
                {
                    '$set':{
                        'total_yearly_gross_income':round(entry['gross_income'],2),
                        'total_yearly_net_income':round(entry['net_income'],2),
                        
                    }
                }
            )
                
            income_yearly_log.update_one({
                'income_id':ObjectId(entry['income_id']),
                
            },{
                '$set':{
                    'total_yearly_gross_income':round(entry['gross_income'],2),
                    'total_yearly_net_income':round(entry['net_income'],2),
                    'updated_at':datetime.now(),
                    #'month':current_month_str
                }
                    },upsert=True)

            print('income, and data',entry['income_id'], entry['net_income'],entry['gross_income'])



def income_calculate_monthly_data():
    now = datetime.now()
    current_year = now.year
    current_month = now.month    
    current_month_str = f"{current_year}-{current_month:02d}"

    print('MONTHLY', current_month_str)

    result = pipeline_result(current_month_str)

    
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
                        'total_monthly_gross_income':round(entry['gross_income'],2),
                        'total_monthly_net_income':round(entry['net_income'],2),
                        
                    }
                }
            )
                
            income_monthly_log.update_one({
                'income_id':ObjectId(entry['income_id']),
                
            },{
                '$set':{
                    'total_monthly_gross_income':round(entry['gross_income'],2),
                    'total_monthly_net_income':round(entry['net_income'],2),
                    'updated_at':datetime.now(),
                    #'month':current_month_str
                }
                    },upsert=True)

            print('income, and data',entry['income_id'], entry['net_income'],entry['gross_income'])


#income_calculate_monthly_data()
#income_calculate_yearly_data()