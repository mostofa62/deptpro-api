import os
from flask import Flask,request,jsonify, json
from dateutil.relativedelta import relativedelta
from sqlalchemy import Float, case, cast, desc, extract, func
from app import app
from util import *
from datetime import datetime

from models import AppData, BillAccounts, BillTransactions, DebtAccounts, DebtTransactions, DebtType, Saving, SavingCategory, SavingContribution, UserSettings
from dbpg import db



@app.route('/api/header-summary-datapg/<int:user_id>', methods=['GET'])
def header_summary_data_pg(user_id:int):

    app_datas = db.session.query(AppData).filter(
        AppData.user_id == user_id           
    ).first()


    # Get the current date
    current_date = datetime.now()

    # Aggregate query to calculate debt summary
    result = db.session.query(
        func.coalesce(func.sum(DebtAccounts.balance), 0).label("total_balance"),
        func.coalesce(func.sum(DebtAccounts.monthly_payment), 0).label("total_monthly_minimum"),
        func.coalesce(func.sum(DebtAccounts.highest_balance), 0).label("total_highest_balance"),
        func.max(DebtAccounts.month_debt_free).label("latest_month_debt_free")
    ).filter(
        DebtAccounts.user_id == user_id,
        DebtAccounts.deleted_at.is_(None)
    ).first()

    # Extract values with rounding where necessary
    total_balance = result.total_balance
    total_monthly_minimum = round(result.total_monthly_minimum, 2)
    total_highest_balance = result.total_highest_balance
    latest_month_debt_free = result.latest_month_debt_free
    total_paid_off = calculate_paid_off_percentage(total_highest_balance,total_balance)

    user_setting = db.session.query(UserSettings.debt_payoff_method, UserSettings.monthly_budget).filter(
        UserSettings.user_id == user_id
    ).first()

    # Set monthly_budget with rounding if user_setting exists, otherwise default to 0
    monthly_budget = round(user_setting.monthly_budget, 2) if user_setting and user_setting.monthly_budget else 0
    
    snowball_amount = round(monthly_budget - total_monthly_minimum,2)

    active_debt_account = db.session.query(func.count()).filter(
        DebtAccounts.user_id == user_id,
        DebtAccounts.deleted_at.is_(None)
    ).scalar()

    latest_month_debt_free = latest_month_debt_free.strftime('%b %Y') if latest_month_debt_free else ''

    #income and incomeboost      
    total_monthly_net_income = app_datas.total_monthly_net_income if  app_datas!=None else 0

    target_year = current_date.year
    target_month = current_date.month
    

    result = db.session.query(
        (func.sum(Saving.progress) / 
         case((func.count(Saving.id) != 0, cast(func.count(Saving.id), Float)), else_=1)
        ).label("average_progress")
    ).filter(
        Saving.deleted_at.is_(None),
        Saving.closed_at.is_(None)
    ).first()

    # Extract the average progress, defaulting to 0 if result is None
    saving_average_progress = round(result.average_progress, 2) if result and result.average_progress else 0




    result = db.session.query(
        func.sum(BillTransactions.amount).label('total_amount')
    ).filter(
        extract('year', BillTransactions.due_date) == target_year,
        extract('month', BillTransactions.due_date) == target_month
    ).first()

    # Get the total amount or default to 0 if no result
    monthly_bill_totals = round(result.total_amount, 2) if result and result.total_amount else 0

    financial_frdom_date = convertDateTostring(datetime.now()+relativedelta(years=1),"%b %Y")

    financial_frdom_target = 100000000

    return jsonify({
        "saving_progress":saving_average_progress,
        "debt_total_balance":total_balance,
        'monthly_budget':monthly_budget,
        'total_monthly_minimum':total_monthly_minimum,
        'snowball_amount':snowball_amount,
        'total_paid_off':total_paid_off,
        'active_debt_account':active_debt_account,
        "month_debt_free":latest_month_debt_free,
        "total_monthly_net_income":total_monthly_net_income,
        "total_monthly_bill_expese":monthly_bill_totals,
        "financial_frdom_date":  financial_frdom_date,
        "financial_frdom_target":financial_frdom_target           
    })



@app.route('/api/dashboard-datapg/<int:user_id>', methods=['GET'])
def get_dashboard_data_pg(user_id:int):

    app_datas = db.session.query(AppData).filter(
        AppData.user_id == user_id           
    ).first()

    page_size = 5
    
    debts = db.session.query(DebtAccounts).filter(
        DebtAccounts.user_id == user_id,
        DebtAccounts.deleted_at.is_(None)
    ).order_by(desc(DebtAccounts.updated_at)).limit(page_size).all()

    debt_list = []
    
    for debt in debts:
        paid_off_percentage = calculate_paid_off_percentage(debt.highest_balance, debt.balance)
        left_to_go = round(100 - float(paid_off_percentage), 1)
        
        debt_list.append({
            "id": str(debt.id),
            "title": debt.name,
            "progress": left_to_go,
            "amount": debt.balance
        })

   

    #summary data debt 

    debt_total_balance = db.session.query(
        func.coalesce(func.sum(DebtAccounts.balance), 0).label("debt_total_balance")
    ).filter(
        DebtAccounts.user_id == user_id,
        DebtAccounts.deleted_at.is_(None)
    ).scalar()


    bill_paid_total = db.session.query(
        func.coalesce(func.sum(BillAccounts.paid_total), 0).label("debt_total_balance")
    ).filter(
        BillAccounts.user_id == user_id,
        BillAccounts.deleted_at.is_(None)
    ).scalar()
   

    total_net_income = app_datas.total_monthly_net_income if app_datas != None else 0    
    total_saving = app_datas.total_monthly_saving if app_datas != None  else 0
    total_wealth = round((total_net_income + total_saving) - (debt_total_balance + bill_paid_total),2)


    ##debt to wealth actual calculation
    remaining_income = total_net_income - ( debt_total_balance + bill_paid_total + total_saving )
    saving_ratio = 0
    remaining_income_ratio = 0
    debt_to_wealth = 0
    if total_net_income > 0: 
        saving_ratio = (total_saving / total_net_income ) * 100
        remaining_income_ratio = ( remaining_income / total_net_income ) * 100
        ##end debt to wealth actual collectin
        debt_to_wealth = round(( saving_ratio * 0.5) + ( remaining_income_ratio * 0.5 ),0)

    

    debttype_id_list = db.session.query(DebtType.id).filter(
        DebtType.deleted_at.is_(None),
        DebtType.in_calculation == 1
    ).all()

    # Extract the IDs from the result
    debttype_id_list = [id_tuple[0] for id_tuple in debttype_id_list]
    

    credit_total_balance = 0
    credit_total_limit = 0
    credit_ratio = 0
   
    if debttype_id_list:
        # Aggregate query on DebtAccounts
        result = db.session.query(
            func.coalesce(func.sum(DebtAccounts.balance), 0).label("credit_total_balance"),
            func.coalesce(func.sum(DebtAccounts.credit_limit), 0).label("credit_total_limit")
        ).filter(
            DebtAccounts.user_id == user_id,
            DebtAccounts.deleted_at.is_(None),
            DebtAccounts.debt_type_id.in_(debttype_id_list)
        ).first()

        credit_total_balance = result.credit_total_balance or 0
        credit_total_limit = result.credit_total_limit or 0

    # Calculate credit utilization ratio
    if credit_total_balance > 0 and credit_total_limit > 0:
        credit_ratio = round((credit_total_balance * 100) / credit_total_limit, 2) if credit_total_balance > 0 and credit_total_limit > 0 else 0


    
    #total allocation calculation
    total_emergency_saving = 0
    emergency_saving = db.session.query(SavingCategory.id).filter(
        SavingCategory.in_dashboard_cal == 1
    ).first()

    if emergency_saving:
        # Aggregate query to calculate total emergency savings
        total_emergency_saving = db.session.query(
            func.coalesce(func.sum(Saving.total_balance), 0).label("total_saving")
        ).filter(
            Saving.user_id == user_id,
            Saving.deleted_at.is_(None),
            Saving.category_id == emergency_saving.id
        ).scalar()
    

    

        
        

    total_allocation_data = [
            ["Modules", "Data"],

    ]     

    total_allocation = total_net_income + total_saving + debt_total_balance + bill_paid_total + total_emergency_saving
    if total_allocation > 0:
        total_allocation_data = [
            ["Modules", "Data"],
            ['Bills',round(bill_paid_total * 100 / total_allocation,0) ],
            ['Debts',round(debt_total_balance * 100 / total_allocation,0) ],
            ['Total Net Income',round(total_net_income * 100 / total_allocation,0) ],
            ['Total Savings',round(total_saving * 100 / total_allocation,0) ],
            ['Emergency Saving', round(total_emergency_saving * 100 / total_allocation,0)]
        ]


    return jsonify({
        
        'debt_total_balance':debt_total_balance,
        'total_net_income':total_net_income ,
        'bill_paid_total':bill_paid_total ,           
        

        "debt_list":debt_list,
        
           
        'total_wealth':total_wealth,
        'debt_to_wealth':debt_to_wealth,
        'credit_ratio':credit_ratio,
        'total_saving':total_saving,
        'total_allocation_data':total_allocation_data             
    })
