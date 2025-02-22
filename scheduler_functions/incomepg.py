from datetime import datetime
from dateutil.relativedelta import relativedelta
import time
import sys
import os

from sqlalchemy import extract, func
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


#from incomefunctions import income_update_next, income_update_next_boost


from models import Income, IncomeTransaction, AppData,IncomeMonthlyLog, IncomeYearlyLog
from dbpg import db
from app import app



def income_calculate_yearly_data_pg():
    now = datetime.now()
    current_year = now.year
    current_year_str = f"{current_year}"    

    user_query = db.session.query(
            IncomeTransaction.user_id,        
            func.sum(IncomeTransaction.gross_income).label("total_yearly_gross_income"),
            func.sum(IncomeTransaction.net_income).label("total_yearly_net_income"),
        )\
            .join(Income, Income.id == IncomeTransaction.income_id)\
            .join(AppData, AppData.user_id == IncomeTransaction.user_id)\
    .filter(
            func.substr(IncomeTransaction.month, 1, 4) == current_year_str,  # Extract YYYY, 
            Income.deleted_at == None,  # Filter for deleted_at == None
            Income.closed_at == None,
            AppData.income_updated_at == None           
        ).group_by(IncomeTransaction.user_id)

    user_yearly_income = user_query.all()

    for doc in user_yearly_income:        
        user_id = doc.user_id        
        total_yearly_gross_income = doc.total_yearly_gross_income
        total_yearly_net_income = doc.total_yearly_net_income
        
        # Update AppData model (by user_id)
        app_data = db.session.query(AppData).filter(AppData.user_id == user_id).first()
        if app_data:
            app_data.total_yearly_gross_income = total_yearly_gross_income
            app_data.total_yearly_net_income = total_yearly_net_income
            app_data.user_id = user_id
            app_data.income_updated_at = datetime.now()
            db.session.commit()  # Commit the change to AppData

        else:
            app_data = AppData(
                total_yearly_gross_income = total_yearly_gross_income,
                total_yearly_net_income = total_yearly_net_income,
                user_id = user_id,
                income_updated_at = datetime.now()
            )
            db.session.add(app_data)
            db.session.commit()

    income_query = db.session.query(
            IncomeTransaction.user_id,
            IncomeTransaction.income_id,
            func.sum(IncomeTransaction.gross_income).label("total_yearly_gross_income"),
            func.sum(IncomeTransaction.net_income).label("total_yearly_net_income"),
        )\
            .join(Income, Income.id == IncomeTransaction.income_id)\
            .join(IncomeYearlyLog, IncomeYearlyLog.income_id == Income.id, isouter=True)\
    .filter(
            func.substr(IncomeTransaction.month, 1, 4) == current_year_str,  # Extract YYYY, 
            Income.deleted_at == None,  # Filter for deleted_at == None
            Income.closed_at == None,
            IncomeYearlyLog.updated_at == None,                        
        ).group_by(IncomeTransaction.user_id, IncomeTransaction.income_id)

    yearly_income = income_query.all()
      
    print('yearly_income',yearly_income)
    for doc in yearly_income:
        print('doc',doc)
        user_id = doc.user_id
        income_id = doc.income_id
        total_yearly_gross_income = doc.total_yearly_gross_income
        total_yearly_net_income = doc.total_yearly_net_income
                

        income_log = db.session.query(Income).filter(Income.id == income_id).first()
        if income_log:
            income_log.total_yearly_gross_income = total_yearly_gross_income
            income_log.total_yearly_net_income = total_yearly_net_income

        # Update IncomeYearlyLog model (by income_id)
        income_year_log = db.session.query(IncomeYearlyLog).filter(IncomeYearlyLog.income_id == income_id).first()
        if income_year_log:
            income_year_log.total_yearly_gross_income = total_yearly_gross_income
            income_year_log.total_yearly_net_income = total_yearly_net_income
            income_year_log.updated_at = datetime.now()
            db.session.commit()  # Commit the change to IncomeYearlyLog

    


def income_calculate_monthly_data_pg():
    now = datetime.now()
    current_year = now.year
    current_month = now.month    
    current_month_str = f"{current_year}-{current_month:02d}"  


    user_query =  db.session.query(
            IncomeTransaction.user_id,            
            func.sum(IncomeTransaction.gross_income).label("total_monthly_gross_income"),
            func.sum(IncomeTransaction.net_income).label("total_monthly_net_income"),
        )\
            .join(Income, Income.id == IncomeTransaction.income_id)\
            .join(AppData, AppData.user_id == IncomeTransaction.user_id)\
        .filter(
            IncomeTransaction.month == current_month_str,  # Check exact YYYY-MM format
            Income.deleted_at == None,  # Filter for deleted_at == None
            Income.closed_at == None,   # Filter for closed_at == None
            AppData.income_updated_at == None
        )\
        .group_by(IncomeTransaction.user_id,IncomeTransaction.month)  # Group by month as well
       
    

    user_monthly_income = user_query.all()

    for doc in user_monthly_income:
        user_id = doc.user_id        
        total_monthly_gross_income = doc.total_monthly_gross_income
        total_monthly_net_income = doc.total_monthly_net_income
        
        # Update AppData model (by user_id)
        app_data = db.session.query(AppData).filter(AppData.user_id == user_id).first()
        if app_data:
            app_data.total_monthly_gross_income = total_monthly_gross_income
            app_data.total_monthly_net_income = total_monthly_net_income
            db.session.commit()  # Commit the change to AppData
        else:
            app_data = AppData(
                total_monthly_gross_income = total_monthly_gross_income,
                total_monthly_net_income = total_monthly_net_income,
                user_id = user_id
            )
            db.session.add(app_data)
            db.session.commit()
 

    
    query =  db.session.query(
            IncomeTransaction.user_id,
            IncomeTransaction.income_id,
            func.sum(IncomeTransaction.gross_income).label("total_monthly_gross_income"),
            func.sum(IncomeTransaction.net_income).label("total_monthly_net_income"),
        )\
            .join(Income, Income.id == IncomeTransaction.income_id)\
            .join(IncomeMonthlyLog, IncomeMonthlyLog.income_id == Income.id, isouter=True)\
        .filter(
            IncomeTransaction.month == current_month_str,  # Check exact YYYY-MM format
            Income.deleted_at == None,  # Filter for deleted_at == None
            Income.closed_at == None,   # Filter for closed_at == None
            IncomeMonthlyLog.updated_at == None 
        )\
        .group_by(IncomeTransaction.user_id, IncomeTransaction.income_id, IncomeTransaction.month)  # Group by month as well
       
    

    monthly_income = query.all()
    print('monthly_income',monthly_income)
    

    for doc in monthly_income:
        user_id = doc.user_id
        income_id = doc.income_id
        total_monthly_gross_income = doc.total_monthly_gross_income
        total_monthly_net_income = doc.total_monthly_net_income        


        income_log = db.session.query(Income).filter(Income.id == income_id).first()
        if income_log:
            income_log.total_monthly_gross_income = total_monthly_gross_income
            income_log.total_monthly_net_income = total_monthly_net_income

        # Update IncomeYearlyLog model (by income_id)
        income_monthly_log = db.session.query(IncomeMonthlyLog).filter(IncomeMonthlyLog.income_id == income_id).first()
        if income_monthly_log:
            income_monthly_log.total_monthly_gross_income = total_monthly_gross_income
            income_monthly_log.total_monthly_net_income = total_monthly_net_income
            income_monthly_log.updated_at = datetime.now()
            db.session.commit()  # Commit the change to IncomeYearlyLog


    
# with app.app_context():
#     income_calculate_monthly_data_pg()
#     income_calculate_yearly_data_pg()