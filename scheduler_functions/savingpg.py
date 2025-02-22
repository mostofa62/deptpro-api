from datetime import datetime
import sys
import os

from sqlalchemy import func
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from models import AppData, Saving,SavingContribution, SavingMonthlyLog
from dbpg import db
from app import app

def saving_calculate_yearly_and_monthly_data_pg():    
    # Get current month in 'YYYY-MM' format
    now = datetime.now()
    current_year = now.year
    current_month = now.month    
    current_month_str = f"{current_year}-{current_month:02d}"

    print('current_month_str:', current_month_str)

    # Query to calculate the total monthly contribution_i_intrs_xyz for each user_id
    user_query = db.session.query(
        SavingContribution.user_id,
        func.sum(SavingContribution.contribution_i_intrs_xyz).label("total_monthly_saving")
    ).join(Saving, Saving.id == SavingContribution.saving_id) \
    .join(AppData, AppData.user_id == SavingContribution.user_id)\
    .filter(
        SavingContribution.month == current_month_str,  # Check exact YYYY-MM format
        Saving.deleted_at == None,  # Filter for deleted_at == None
        Saving.closed_at == None,   # Filter for closed_at == None
        AppData.saving_updated_at == None 
    ).group_by(
        SavingContribution.user_id
    )

    # Execute the query
    user_monthly_balance = user_query.all()

    # print('User-level monthly balance query:', str(user_query.statement))
    print('User-level monthly balance data:', user_monthly_balance)

    for doc in user_query:
        user_id = doc.user_id        
        total_monthly_saving = doc.total_monthly_saving
        # Update AppData model (by user_id)
        app_data = db.session.query(AppData).filter(AppData.user_id == user_id).first()
        if app_data:
            app_data.total_monthly_saving = round(total_monthly_saving,2)
            app_data.user_id = user_id
            app_data.saving_updated_at = datetime.now()           
            db.session.commit()  # Commit the change to AppData
        else:
            app_data = AppData(
                total_monthly_saving = round(total_monthly_saving,2),                
                user_id = user_id,
                saving_updated_at = datetime.now()
            )
            db.session.add(app_data)
            db.session.commit()        

    # Query to calculate the total monthly contribution_i_intrs_xyz for each saving_id by user_id
    saving_query = db.session.query(
        SavingContribution.user_id,
        SavingContribution.saving_id,
        func.sum(SavingContribution.contribution_i_intrs_xyz).label("total_monthly_balance")
    ).join(Saving, Saving.id == SavingContribution.saving_id) \
    .join(SavingMonthlyLog, SavingMonthlyLog.saving_id == Saving.id, isouter=True)\
    .filter(
        SavingContribution.month == current_month_str,  # Check exact YYYY-MM format
        Saving.deleted_at == None,  # Filter for deleted_at == None
        Saving.closed_at == None,   # Filter for closed_at == None
        SavingMonthlyLog.updated_at == None
    ).group_by(
        SavingContribution.user_id,
        SavingContribution.saving_id
    )

    # Execute the query
    saving_monthly_balance = saving_query.all()

    # print('Saving-level monthly balance query:', str(saving_query.statement))
    print('Saving-level monthly balance data:', saving_monthly_balance)

    for doc in saving_query:
        user_id = doc.user_id        
        total_monthly_balance = doc.total_monthly_balance
        saving_id = doc.saving_id

        saving_log = db.session.query(Saving).filter(Saving.id == saving_id).first()
        if saving_log:
            saving_log.total_monthly_balance = round(total_monthly_balance,2)            
       
        saving_monthly_log = db.session.query(SavingMonthlyLog).filter(SavingMonthlyLog.saving_id == saving_id).first()
        if saving_monthly_log:
            saving_monthly_log.total_monthly_balance = round(total_monthly_balance,2)            
            saving_monthly_log.updated_at = datetime.now()
            db.session.commit()  # Commit the change to IncomeYearlyLog

    
    

    


   
    
    
# with app.app_context():
#     saving_calculate_yearly_and_monthly_data_pg()

#saving_calculate_yearly_and_monthly_data()