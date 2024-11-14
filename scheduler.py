
from datetime import datetime
import time
import os
from flask_apscheduler import APScheduler
from db import my_col,myclient
from util import *

calender_data = my_col('calender_data')

#all collections
bill_accounts = my_col('bill_accounts')
debt_accounts = my_col('debt_accounts')
income_accounts = my_col('income')
saving_accounts = my_col('saving')

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

        


def deb_to_calender():
    debt_list = debt_accounts.find({
        'calender_at':None
    },{'_id':1, 'name':1,'month_debt_free':1}).limit(5)

    calender_data_list = []
    debt_id_list = []

    for todo in debt_list:
        if 'month_debt_free' in todo and todo['month_debt_free'] == None:
            continue
        debt_id_list.append(todo['_id'])
        entry = {
            'module_name':'Debt',
            'module_id':'debt',
            'month':convertDateTostring(todo['month_debt_free'],'%Y-%m'),
            'month_word':convertDateTostring(todo['month_debt_free']),
            'event_date':convertDateTostring(todo['month_debt_free'],'%Y-%m-%d'),
            'data':{
                 'name':todo['name'],                 
                 'description':'Month Debt Free',
                 'data_id':todo['_id']
            }
           
            
            
            
        }
        calender_data_list.append(entry)

    if len(calender_data_list) > 0  and len(debt_id_list) > 0:

        c_d = calender_data.insert_many(calender_data_list)
        if c_d.inserted_ids:
            debt_accounts.update_many({
                '_id':{'$in':debt_id_list}
            },{
                '$set':{
                    'calender_at':datetime.now()
                }
            })

def income_to_calender():
    income_list = income_accounts.find({
        'calender_at':None
    },{'_id':1, 'earner':1,'next_pay_date':1}).limit(5)

    calender_data_list = []
    income_id_list = []

    for todo in income_list:
        if 'next_pay_date' in todo and todo['next_pay_date'] == None:
            continue
        income_id_list.append(todo['_id'])
        entry = {
            'module_name':'Income',
            'module_id':'income',
            'month':convertDateTostring(todo['next_pay_date'],'%Y-%m'),
            'month_word':convertDateTostring(todo['next_pay_date']),
            'event_date':convertDateTostring(todo['next_pay_date'],'%Y-%m-%d'),
            'data':{
                 'name':todo['earner'],                 
                 'description':'Next Pay Date',
                 'data_id':todo['_id']
            }
           
            
            
            
        }
        calender_data_list.append(entry)

    if len(calender_data_list) > 0  and len(income_id_list) > 0:

        c_d = calender_data.insert_many(calender_data_list)
        if c_d.inserted_ids:
            income_accounts.update_many({
                '_id':{'$in':income_id_list}
            },{
                '$set':{
                    'calender_at':datetime.now()
                }
            })


def saving_to_calender():
    saving_list = saving_accounts.find({
        'calender_at':None
    },{'_id':1, 'saver':1,'next_contribution_date':1}).limit(5)

    calender_data_list = []
    saving_id_list = []

    for todo in saving_list:
        if 'next_contribution_date' in todo and todo['next_contribution_date'] == None:
            continue
        saving_id_list.append(todo['_id'])
        entry = {
            'module_name':'Saving',
            'module_id':'saving',
            'month':convertDateTostring(todo['next_contribution_date'],'%Y-%m'),
            'month_word':convertDateTostring(todo['next_contribution_date']),
            'event_date':convertDateTostring(todo['next_contribution_date'],'%Y-%m-%d'),
            'data':{
                 'name':todo['saver'],                 
                 'description':'Next Pay Date',
                 'data_id':todo['_id']
            }
           
            
            
            
        }
        calender_data_list.append(entry)

    if len(calender_data_list) > 0  and len(saving_id_list) > 0:

        c_d = calender_data.insert_many(calender_data_list)
        if c_d.inserted_ids:
            saving_accounts.update_many({
                '_id':{'$in':saving_id_list}
            },{
                '$set':{
                    'calender_at':datetime.now()
                }
            })


def calender_entry():
    print('CALENER ENTRY RUNNING', datetime.now())
    bill_to_calender()
    time.sleep(1)
    deb_to_calender()
    time.sleep(1)
    income_to_calender()
    time.sleep(1)
    saving_to_calender()


scheduler = APScheduler()
#scheduler.add_job(id = 'CALENDER_ENTRY', func=calender_entry, trigger="cron", minute='*/'+str(CALENDER_ENTRY_DURATION))
scheduler.add_job(id = 'CALENDER_ENTRY', func=calender_entry, trigger='interval',minutes=int(CALENDER_ENTRY_DURATION))
scheduler.start()