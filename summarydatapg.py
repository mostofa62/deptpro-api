from flask import jsonify
from dateutil.relativedelta import relativedelta
from sqlalchemy import Float, case, cast, desc, extract, func,and_, or_
from app import app
from util import *
from datetime import datetime

from models import AppData, BillAccounts, BillTransactions, CashFlow, DebtAccounts, DebtTransactions, DebtType, PaymentBoost, Saving, SavingCategory, SavingContribution, UserSettings
from dbpg import db

from sqlalchemy.exc import SQLAlchemyError

@app.route('/api/header-summary-datapg/<int:user_id>', methods=['GET'])
async def header_summary_data_pg(user_id:int):

    session = db.session
    try:
        app_datas = session.query(AppData).filter(
            AppData.user_id == user_id           
        ).first()

        # Get the current date
        current_date = datetime.now()
        current_month = int(convertDateTostring(current_date,'%Y%m'))

        # Aggregate query to calculate debt summary
        result = session.query(
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

        user_setting = session.query(UserSettings.debt_payoff_method, UserSettings.monthly_budget).filter(
            UserSettings.user_id == user_id
        ).first()

        # Set monthly_budget with rounding if user_setting exists, otherwise default to 0
        monthly_budget = round(user_setting.monthly_budget, 2) if user_setting and user_setting.monthly_budget else 0

        current_month_string = datetime.now().strftime('%b %Y')

        total_payment_boost = (
            db.session.query(func.coalesce(func.sum(PaymentBoost.amount), 0))
            .filter(
                PaymentBoost.month == current_month_string,
                PaymentBoost.deleted_at.is_(None)
            )
            .scalar()
        ) or 0
        
        #snowball_amount = round((monthly_budget - total_monthly_minimum)+total_payment_boost,2)
        
        cashflow = (
                session.query(CashFlow.amount)
                .filter(
                    CashFlow.user_id == user_id,
                    CashFlow.month == current_month
                )
                .scalar()
            ) or 0

        active_debt_account = session.query(func.count()).filter(
            DebtAccounts.user_id == user_id,
            DebtAccounts.deleted_at.is_(None)
        ).scalar() or 0

        latest_month_debt_free = convertDateTostring(latest_month_debt_free,'%b %Y') if latest_month_debt_free else ''

        #income and incomeboost      
        total_monthly_net_income = app_datas.total_monthly_net_income if  app_datas!=None else 0
        total_monthly_net_income_f = app_datas.total_monthly_net_income_f if  app_datas!=None else 0
        total_monthly_net_income += total_monthly_net_income_f

        target_year = current_date.year
        target_month = current_date.month
        

        saving_average_progress = session.query(
            (func.sum(Saving.progress) / 
            case((func.count(Saving.id) != 0, cast(func.count(Saving.id), Float)), else_=1)
            ).label("saving_average_progress")
        ).filter(
            Saving.user_id == user_id,
            Saving.deleted_at.is_(None),
            Saving.closed_at.is_(None)
        ).scalar() or 0

        # Extract the average progress, defaulting to 0 if result is None
        #saving_average_progress = round(result.average_progress, 2) if result and result.average_progress else 0



        '''
        monthly_bill_totals = session.query(
            func.sum(BillTransactions.amount).label('monthly_bill_totals')
        ).join(
            BillTransactions.bill_account
        ).filter(
            BillTransactions.user_id == user_id,
            extract('year', BillTransactions.due_date) == target_year,
            extract('month', BillTransactions.due_date) == target_month,
            BillTransactions.type == 1,
            BillAccounts.deleted_at.is_(None),  # Make sure related account is not deleted
            BillAccounts.closed_at.is_(None)    # Make sure related account is not closed
        ).scalar() or 0
        '''
        total_monthly_bill_paid = app_datas.total_monthly_bill_paid if app_datas.current_billing_month!=None and app_datas.current_billing_month == current_month else 0
        total_monthly_bill_unpaid = app_datas.total_monthly_bill_unpaid if app_datas.current_billing_month_up!=None and app_datas.current_billing_month_up == current_month else 0
        total_monthly_bill_unpaidf = app_datas.total_monthly_bill_unpaidf if app_datas.current_billing_month_upf!=None and app_datas.current_billing_month_up == current_month else 0
        monthly_bill_totals = total_monthly_bill_paid + total_monthly_bill_unpaid + total_monthly_bill_unpaidf
        # monthly_bill_totals = session.query(
        #     func.coalesce(func.sum(BillAccounts.default_amount), 0).label("bill_paid_total")
        # ).filter(
        #     BillAccounts.user_id == user_id,
        #     BillAccounts.deleted_at.is_(None)
        # ).scalar() or 0

        # Get the total amount or default to 0 if no result
        #monthly_bill_totals = round(result.total_amount, 2) if result and result.total_amount else 0

        #financial_frdom_date = convertDateTostring(datetime.now()+relativedelta(years=1),"%b %Y")
        financial_frdom_date = convertDateTostring(convertStringTodate(f"{app_datas.financial_freedom_month}","%Y%m"),"%b, %Y") if app_datas.financial_freedom_month!=None else ""

        #financial_frdom_target = app_datas.financial_freedom_target
        financial_frdom_target = (
            session.query(func.coalesce(func.sum(Saving.financial_freedom_target), 0))
            .filter(
                Saving.user_id == user_id,
                Saving.deleted_at.is_(None)
            )
            .scalar()
        ) or 0

        return jsonify({
            "saving_progress":saving_average_progress,
            "debt_total_balance":total_balance,
            'monthly_budget':monthly_budget,
            'total_monthly_minimum':total_monthly_minimum,
            'snowball_amount':cashflow,
            'total_paid_off':total_paid_off,
            'active_debt_account':active_debt_account,
            "month_debt_free":latest_month_debt_free,
            "total_monthly_net_income":total_monthly_net_income,
            "total_monthly_bill_expese":monthly_bill_totals,
            "financial_frdom_date":  financial_frdom_date,
            "financial_frdom_target":financial_frdom_target           
        })
    
    except Exception as e:
        session.rollback()  # Rollback in case of error
        print('header data error: {e}')
        return jsonify({
            "saving_progress":0,
            "debt_total_balance":0,
            'monthly_budget':0,
            'total_monthly_minimum':0,
            'snowball_amount':0,
            'total_paid_off':0,
            'active_debt_account':0,
            "month_debt_free":None,
            "total_monthly_net_income":0,
            "total_monthly_bill_expese":0,
            "financial_frdom_date":  None,
            "financial_frdom_target":0           
        })

    finally:
        session.close()



@app.route('/api/dashboard-datapg/<int:user_id>', methods=['GET'])
async def get_dashboard_data_pg(user_id: int):

    total_allocation_data = [
        ["Modules", "Data"],
        ['Bills', 0],
        ['Debts',0],
        ['Total Net Income', 0],
        ['Total Savings', 0],
        ['Emergency Saving', 0]
    ]

    debt_total_balance = 0
    total_net_income = 0
    total_saving = 0
    total_wealth = 0
    debt_to_wealth = 0
    credit_ratio = 0
    bill_paid_total = 0
    debt_list = []

    current_date = datetime.now()
    current_month = int(convertDateTostring(current_date,'%Y%m'))

    session = None
    try:
        session = db.session

        app_datas = session.query(AppData).filter(
            AppData.user_id == user_id
        ).first()

        page_size = 5

        debts = session.query(DebtAccounts).filter(
            DebtAccounts.user_id == user_id,
            DebtAccounts.deleted_at.is_(None)
        ).order_by(desc(DebtAccounts.updated_at)).limit(page_size).all()

        for debt in debts:
            paid_off_percentage = calculate_paid_off_percentage(debt.highest_balance, debt.balance)
            left_to_go = round(100 - float(paid_off_percentage), 1)
            debt_list.append({
                "id": str(debt.id),
                "title": debt.name,
                "progress": left_to_go,
                "amount": debt.balance
            })
        
        user_setting = session.query(UserSettings.debt_payoff_method, UserSettings.monthly_budget).filter(
            UserSettings.user_id == user_id
        ).first()

        # Set monthly_budget with rounding if user_setting exists, otherwise default to 0
        monthly_budget = round(user_setting.monthly_budget, 2) if user_setting and user_setting.monthly_budget else 0

        current_month_string = datetime.now().strftime('%b %Y')

        total_payment_boost = (
            db.session.query(func.coalesce(func.sum(PaymentBoost.amount), 0))
            .filter(
                PaymentBoost.month == current_month_string,
                PaymentBoost.deleted_at.is_(None)
            )
            .scalar()
        ) or 0

        debt_total_balance = monthly_budget + total_payment_boost
        

        total_monthly_bill_paid = app_datas.total_monthly_bill_paid if app_datas.current_billing_month!=None and app_datas.current_billing_month == current_month else 0
        total_monthly_bill_unpaid = app_datas.total_monthly_bill_unpaid if app_datas.current_billing_month_up!=None and app_datas.current_billing_month_up == current_month else 0
        total_monthly_bill_unpaidf = app_datas.total_monthly_bill_unpaidf if app_datas.current_billing_month_upf!=None and app_datas.current_billing_month_up == current_month else 0
        bill_paid_total = total_monthly_bill_paid + total_monthly_bill_unpaid + total_monthly_bill_unpaidf

        total_net_income = app_datas.total_monthly_net_income if app_datas else 0
        total_net_income_f = app_datas.total_monthly_net_income_f if  app_datas!=None else 0
        total_net_income += total_net_income_f
        total_saving = app_datas.total_monthly_saving if app_datas else 0
        total_wealth = round((total_net_income + total_saving) - (debt_total_balance + bill_paid_total), 2)

       
        debt_to_wealth = 0
        if total_net_income > 0 and total_wealth > 0:
            debt_to_wealth = round(total_wealth / total_net_income* 100 , 0)

        debttype_id_list = session.query(DebtType.id).filter(
            DebtType.deleted_at.is_(None),
            DebtType.in_calculation == 1
        ).all()

        debttype_id_list = [id_tuple[0] for id_tuple in debttype_id_list]

        credit_total_balance = 0
        credit_total_limit = 0
        if debttype_id_list:
            result = session.query(
                func.coalesce(func.sum(DebtAccounts.balance), 0).label("credit_total_balance"),
                func.coalesce(func.sum(DebtAccounts.credit_limit), 0).label("credit_total_limit")
            ).filter(
                DebtAccounts.user_id == user_id,
                DebtAccounts.deleted_at.is_(None),
                DebtAccounts.debt_type_id.in_(debttype_id_list)
            ).first()

            credit_total_balance = result.credit_total_balance or 0
            credit_total_limit = result.credit_total_limit or 0

        if credit_total_balance > 0 and credit_total_limit > 0:
            credit_ratio = round((credit_total_balance * 100) / credit_total_limit, 2)

        total_emergency_saving = 0
        emergency_saving = session.query(SavingCategory.id).filter(
            SavingCategory.in_dashboard_cal == 1
        ).first()

        if emergency_saving:
            total_emergency_saving = session.query(
                func.coalesce(func.sum(Saving.total_balance), 0).label("total_saving")
            ).filter(
                Saving.user_id == user_id,
                Saving.deleted_at.is_(None),
                Saving.category_id == emergency_saving.id
            ).scalar()

        total_allocation = total_net_income + total_saving + debt_total_balance + bill_paid_total + total_emergency_saving
        if total_allocation > 0:
            total_allocation_data = [
                ["Modules", "Data"],
                ['Bills', round(bill_paid_total * 100 / total_allocation, 0)],
                ['Debts', round(debt_total_balance * 100 / total_allocation, 0)],
                ['Total Net Income', round(total_net_income * 100 / total_allocation, 0)],
                ['Total Savings', round(total_saving * 100 / total_allocation, 0)],
                ['Emergency Saving', round(total_emergency_saving * 100 / total_allocation, 0)]
            ]

        return jsonify({
            'debt_total_balance': debt_total_balance,
            'total_net_income': round(total_net_income,0),
            'bill_paid_total': round(bill_paid_total,0),
            "debt_list": debt_list,
            'total_wealth': total_wealth,
            'debt_to_wealth': debt_to_wealth,
            'credit_ratio': credit_ratio,
            'total_saving': round(total_saving,0),
            'total_allocation_data': total_allocation_data
        })

    except SQLAlchemyError as e:
        print(f"Database error: {e}")
        return jsonify({
            'debt_total_balance': 0,
            'total_net_income': 0,
            'bill_paid_total': 0,
            'debt_list': [],
            'total_wealth': 0,
            'debt_to_wealth': 0,
            'credit_ratio': 0,
            'total_saving': 0,
            'total_allocation_data': total_allocation_data
        })

    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({
            'debt_total_balance': 0,
            'total_net_income': 0,
            'bill_paid_total': 0,
            'debt_list': [],
            'total_wealth': 0,
            'debt_to_wealth': 0,
            'credit_ratio': 0,
            'total_saving': 0,
            'total_allocation_data': total_allocation_data
        })

    finally:
        if session:
            session.close()
