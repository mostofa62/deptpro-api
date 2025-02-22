
from datetime import datetime
import time
import os
from flask_apscheduler import APScheduler
from util import *
from scheduler_functions.savingpg import *
from scheduler_functions.incomepg import *
from app import app



CALENDER_ENTRY_DURATION = os.environ["CALENDER_ENTRY_DURATION"]
MONTHLY_LOG_UPDATE = os.environ["MONTHLY_LOG_UPDATE"]
from models import CalendarData, BillAccounts, DebtAccounts, Income, Saving
from dbpg import db


def bill_to_calender():
    # Querying the bill accounts that do not have a calendar entry
    bill_list = BillAccounts.query.filter(BillAccounts.calender_at == None).limit(5).all()

    calender_data_list = []
    bill_id_list = []

    for todo in bill_list:
        bill_id_list.append(todo.id)
        entry = CalendarData(
            module_name='Bill',
            module_id='bill',
            month=convertDateTostring(todo.next_due_date, '%Y-%m'),
            month_word=convertDateTostring(todo.next_due_date),
            event_date=convertDateTostring(todo.next_due_date, '%Y-%m-%d'),
            data_id = todo.id,
            data={
                'name': todo.name,
                'description': 'Next Due Date',                
            },
            user_id=todo.user_id
        )
        calender_data_list.append(entry)

    if calender_data_list and bill_id_list:
        # Inserting the calendar data entries
        db.session.add_all(calender_data_list)
        db.session.commit()

        # Updating the bill accounts with calendar_at timestamp
        BillAccounts.query.filter(BillAccounts.id.in_(bill_id_list)).update({
            BillAccounts.calender_at: datetime.now()
        }, synchronize_session='fetch')
        db.session.commit()



def deb_to_calender():
    # Querying the debt accounts that do not have a calendar entry and having a 'month_debt_free'
    debt_list = DebtAccounts.query.filter(DebtAccounts.calender_at == None).limit(5).all()

    calender_data_list = []
    debt_id_list = []

    for todo in debt_list:
        if todo.month_debt_free is None:
            continue
        debt_id_list.append(todo.id)
        entry = CalendarData(
            module_name='Debt',
            module_id='debt',
            month=convertDateTostring(todo.month_debt_free, '%Y-%m'),
            month_word=convertDateTostring(todo.month_debt_free),
            event_date=convertDateTostring(todo.month_debt_free, '%Y-%m-%d'),
            data_id = todo.id,
            data={
                'name': todo.name,
                'description': 'Month Debt Free'                
            },
            user_id=todo.user_id
        )
        calender_data_list.append(entry)

    if calender_data_list and debt_id_list:
        # Inserting the calendar data entries
        db.session.add_all(calender_data_list)
        db.session.commit()

        # Updating the debt accounts with calendar_at timestamp
        DebtAccounts.query.filter(DebtAccounts.id.in_(debt_id_list)).update({
            DebtAccounts.calender_at: datetime.now()
        }, synchronize_session='fetch')
        db.session.commit()



def income_to_calender():
    # Querying the income accounts that do not have a calendar entry
    income_list = Income.query.filter(Income.calender_at == None).limit(5).all()

    calender_data_list = []
    income_id_list = []

    for todo in income_list:
        if todo.next_pay_date is None:
            continue
        income_id_list.append(todo.id)
        entry = CalendarData(
            module_name='Income',
            module_id='income',
            month=convertDateTostring(todo.next_pay_date, '%Y-%m'),
            month_word=convertDateTostring(todo.next_pay_date),
            event_date=convertDateTostring(todo.next_pay_date, '%Y-%m-%d'),
            data_id=todo.id,
            data={
                'name': todo.earner,
                'description': 'Next Pay Date',
                
            },
            user_id=todo.user_id
        )
        calender_data_list.append(entry)

    if calender_data_list and income_id_list:
        # Inserting the calendar data entries
        db.session.add_all(calender_data_list)
        db.session.commit()

        # Updating the income accounts with calendar_at timestamp
        Income.query.filter(Income.id.in_(income_id_list)).update({
            Income.calender_at: datetime.now()
        }, synchronize_session='fetch')
        db.session.commit()



def saving_to_calender():
    # Querying the saving accounts that do not have a calendar entry
    saving_list = Saving.query.filter(Saving.calender_at == None).limit(5).all()

    calender_data_list = []
    saving_id_list = []

    for todo in saving_list:
        if todo.next_contribution_date is None:
            continue
        saving_id_list.append(todo.id)
        entry = CalendarData(
            module_name='Saving',
            module_id='saving',
            month=convertDateTostring(todo.next_contribution_date, '%Y-%m'),
            month_word=convertDateTostring(todo.next_contribution_date),
            event_date=convertDateTostring(todo.next_contribution_date, '%Y-%m-%d'),
            data_id=todo.id,
            data={
                'name': todo.saver,
                'description': 'Next Pay Date',                
            },
            user_id=todo.user_id
        )
        calender_data_list.append(entry)

    if calender_data_list and saving_id_list:
        # Inserting the calendar data entries
        db.session.add_all(calender_data_list)
        db.session.commit()

        # Updating the saving accounts with calendar_at timestamp
        Saving.query.filter(Saving.id.in_(saving_id_list)).update({
            Saving.calender_at: datetime.now()
        }, synchronize_session='fetch')
        db.session.commit()


def calender_entry():
    with app.app_context():
        print('CALENER ENTRY RUNNING', datetime.now())
        bill_to_calender()
        time.sleep(1)
        deb_to_calender()
        time.sleep(1)
        income_to_calender()
        time.sleep(1)
        saving_to_calender()

def monthly_log_update():
     with app.app_context():
        print('MONTHLY LOG UPDATE', datetime.now())
        saving_calculate_yearly_and_monthly_data_pg()
        time.sleep(1)
        income_calculate_monthly_data_pg()
        time.sleep(1)
        income_calculate_yearly_data_pg()

# def transaction_udpate():
#     print('TRANSACTION UPDATE', datetime.now())
#     transaction_update_income()


scheduler = APScheduler()
#scheduler.add_job(id = 'CALENDER_ENTRY', func=calender_entry, trigger="cron", minute='*/'+str(CALENDER_ENTRY_DURATION))
scheduler.add_job(id = 'CALENDER_ENTRY', func=calender_entry, trigger='interval',minutes=int(CALENDER_ENTRY_DURATION))
scheduler.add_job(id = 'MONTHLY_LOG_UPDATE', func=monthly_log_update, trigger='interval',minutes=int(MONTHLY_LOG_UPDATE))
#scheduler.add_job(id = 'TRANSACTION_UPDATE',func=transaction_udpate, trigger='cron', hour=23, minute=45)
scheduler.start()

