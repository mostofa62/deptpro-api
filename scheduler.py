
from datetime import datetime
import os
from flask_apscheduler import APScheduler
from db import my_col,myclient
from util import *

calender_data = my_col('calender_data')

#all collections
bill_accounts = my_col('bill_accounts')

CALENDER_ENTRY_DURATION = os.environ["CALENDER_ENTRY_DURATION"]


def bill_to_calender():
    bill_list = bill_accounts.find({
        'calender_at':None
    },{'_id':1, 'name':1,'next_due_date':1}).limit(5)

    calender_data_list = []
    bill_id_list = []

    for todo in bill_list:
        bill_id_list.append(todo['_id'])
        entry = {
            'module_name':'Bill',
            'module_id':'bill',
            'month':convertDateTostring(todo['next_due_date'],'%Y-%m'),
            'month_word':convertDateTostring(todo['next_due_date']),
            'event_date':convertDateTostring(todo['next_due_date'],'%Y-%m-%d'),
            'data':{
                 'name':todo['name'],                 
                 'description':'Next Due Date',
                 'data_id':todo['_id']
            }
           
            
            
            
        }
        calender_data_list.append(entry)

    if len(calender_data_list) > 0  and len(bill_id_list) > 0:

        c_d = calender_data.insert_many(calender_data_list)
        if c_d.inserted_ids:
            bill_accounts.update_many({
                '_id':{'$in':bill_id_list}
            },{
                '$set':{
                    'calender_at':datetime.now()
                }
            })

        


def calender_entry():
    print('CALENER ENTRY RUNNING', datetime.now())
    bill_to_calender()


scheduler = APScheduler()
#scheduler.add_job(id = 'CALENDER_ENTRY', func=calender_entry, trigger="cron", minute='*/'+str(CALENDER_ENTRY_DURATION))
scheduler.add_job(id = 'CALENDER_ENTRY', func=calender_entry, trigger='interval',minutes=int(CALENDER_ENTRY_DURATION))
scheduler.start()