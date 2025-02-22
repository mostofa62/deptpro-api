from flask import request,jsonify
#from flask_cors import CORS, cross_origin
from app import app

from util import *
from models import UserSettings, DebtAccounts
from dbpg import db


#save debt user settings 
@app.route("/api/get-user-settingspg/<int:user_id>", methods=['GET'])
def get_user_settings_pg(user_id:int):

    # Get user settings for the given user_id
    usersetting = (
        db.session.query(UserSettings.debt_payoff_method, UserSettings.monthly_budget)
        .filter(UserSettings.user_id == user_id)
        .first()
    )

    # Calculate total monthly payments
    total_monthly_payment = (
        db.session.query(db.func.coalesce(db.func.sum(DebtAccounts.monthly_payment), 0))
        .filter(DebtAccounts.user_id == user_id, DebtAccounts.deleted_at.is_(None))
        .scalar()
    )
    
    
    user_setting = {
        'user_id':user_id,
        'debt_payoff_method':usersetting.debt_payoff_method if usersetting else None,
        'monthly_budget':usersetting.monthly_budget if usersetting else 0,
        'minimum_payments': total_monthly_payment
    }

    return jsonify({
           
            "user_setting":user_setting            
        })


from flask import request, jsonify
from models import UserSettings
from dbpg import db


# Save user settings
@app.route("/api/save-user-settingspg", methods=['POST'])
def save_user_settings_pg():
    if request.method == 'POST':
        data = request.get_json()  # Using get_json() is safer and cleaner
        
        user_id = data['user_id']
        message = ''
        result = 0
        user_setting_id = None
        
        try:
            # Check if the user setting already exists
            user_setting = (
                db.session.query(UserSettings)
                .filter(UserSettings.user_id == user_id)
                .first()
            )

            if user_setting:
                # Update existing user setting
                user_setting.monthly_budget = float(data['monthly_budget'])
                user_setting.debt_payoff_method = data['debt_payoff_method']
                message = 'Settings updated!'
                user_setting_id = user_setting.id
            else:
                # Create a new user setting
                new_user_setting = UserSettings(
                    user_id=user_id,
                    monthly_budget=float(data['monthly_budget']),
                    debt_payoff_method=data['debt_payoff_method']
                )
                db.session.add(new_user_setting)
                message = 'Settings saved!'
                user_setting_id = new_user_setting.user_id
            
            # Commit changes to the database
            db.session.commit()
            result = 1
        
        except Exception as ex:
            print('DEBT EXP:', ex)
            db.session.rollback()
            user_setting_id = None
            result = 0
            message = 'Debt transaction addition Failed!'

        return jsonify({
            "user_setting_id": user_setting_id,
            "message": message,
            "result": result
        })


        

            


        return jsonify({
           
            "user_setting_id":user_setting_id,
            "message":message,
            "result":result
        })