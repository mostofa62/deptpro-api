from collections import defaultdict
import os
from flask import jsonify
from sqlalchemy import Integer, case, cast, func
from savingutil import get_delta
from app import app
from util import *
from datetime import datetime

from models import Saving, SavingBoost
from dbpg import db
from sqlalchemy.orm import aliased
from sqlalchemy.exc import OperationalError, TimeoutError, DBAPIError
import math

# Aliasing the SavingBoost table to avoid conflict in the joins
saving_boosts_1 = aliased(SavingBoost)
saving_boosts_2 = aliased(SavingBoost)


def process_projections(results=None):

    saving_dict = {}
    goal_amount = 0

    if results:
        
        for row in results:
            goal_amount += row.goal_amount
            saving_id = row.id
            if saving_id not in saving_dict:
                saving_dict[saving_id] = {
                    "id": row.id,
                    "saver": row.saver,
                    "contribution": row.contribution,
                    "starting_amount": row.starting_amount,
                    "goal_amount": row.goal_amount,
                    "increase_contribution_by": row.increase_contribution_by, 
                    "interest": row.interest,                   
                    "total_balance": row.total_balance_xyz,
                    "period": row.period,
                    "starting_date": row.starting_date,
                    "next_pay_date": row.next_pay_date,
                    "repeat": row.repeat,
                    "user_id": row.user_id,
                    "saving_boosts": []  # Initialize nested list
                }

            if saving_id in saving_dict:
                # Append saving_boost only if it exists
                if row.saving_boost is not None:                    
                    saving_dict[saving_id]["saving_boosts"].append({
                        "saving_boost": row.saving_boost,
                        "pay_date_boost": row.pay_date_boost,
                        "repeat_boost": row.repeat_boost,  # Parsed JSON
                        "next_pay_date_boost": row.next_pay_date_boost,
                        "total_balance_boost": row.total_balance_boost,
                        "total_monthly_balance_boost": row.total_monthly_balance_boost,
                        "op_type": row.boost_operation_type['value'],

                    })


    return (list(saving_dict.values()),goal_amount)


def calculate_end_date(start_date, initial_balance, contribution, daily_rate, goal_amount, frequency):
    if initial_balance >= goal_amount:
        return start_date, 0  # Already reached the goal

    delta = get_delta(frequency)  # Get time difference based on contribution frequency
    period_days = delta.days  # Convert timedelta to days

    # Calculate the periodic rate
    periodic_rate = daily_rate * period_days  # Interest applied per contribution period

    if periodic_rate == 0:
        # No interest; use simple accumulation
        if contribution == 0:
            return None, None  # No way to reach the goal
        
        n = (goal_amount - initial_balance) / contribution
    else:
        # Compute number of periods using logarithmic formula
        term1 = goal_amount - (contribution / periodic_rate) + initial_balance
        term2 = initial_balance + (contribution / periodic_rate)

        # Ensure valid log input
        if term1 <= 0 or term2 <= 0:
            return None, None  # Invalid input to log
        
        numerator = math.log(term1 / term2)
        denominator = math.log(1 + periodic_rate)

        if denominator == 0:
            return None, None  # Avoid division by zero
        
        n = numerator / denominator

    # Convert to integer periods
    n = max(1, math.ceil(n))

    # Compute the end date
    end_date = start_date + (n * delta)

    return end_date, n



def get_projection_list(projection_list, goal_amount):
    # Dictionary to store merged results
    projection = defaultdict(lambda: {
        "total_balance": 0,
        "contribution": 0,       
        "month_word": "",
        "month": None,
    })

    initial_balance = 0
    initial_contribution = 0
    for saving in projection_list:
        pay_date = saving["next_pay_date"]
        frequency = saving["repeat"]["value"]
        contribution = initial_contribution+saving['contribution']
        balance = initial_balance + saving['total_balance']
        #goal_amount = saving['goal_amount']
        interest_rate = saving['interest'] / 100
        daily_rate = interest_rate / 365
        period = saving['period']
        i_contribution = saving['increase_contribution_by']
        delta = get_delta(frequency)

        next_contribution_date = pay_date + delta
        current_datetime_now = datetime.now()

        end_date, num_periods = calculate_end_date(pay_date, balance, contribution, daily_rate, goal_amount, frequency)
        #print('end date and periods',end_date, num_periods)

        boost_dates = {}
        for boost in saving.get("saving_boosts", []):
            boost_date, boost_amount, op_type = boost["pay_date_boost"], boost["saving_boost"], boost["op_type"]
            boost_repeat = boost["repeat_boost"]["value"]

            while boost_date < end_date:
                month_key = int(f"{boost_date.year}{boost_date.month:02d}")
                
                if month_key not in boost_dates:
                    boost_dates[month_key] = {}
                
                boost_dates[month_key] = {"amount": boost_amount, "op_type": op_type}

                if boost_repeat == 0: 
                    break  # One-time boost
                boost_date += get_delta(boost_repeat)  # Apply boost frequency
        
        if next_contribution_date >= current_datetime_now and balance:
            while balance < goal_amount:

                month_key = int(f"{pay_date.year}{pay_date.month:02d}")
                next_contribution_date = pay_date + delta            
                days_in_period = (next_contribution_date - pay_date).days
                interest = balance * (daily_rate * days_in_period)
                
                balance += interest + contribution 
                
                inc_contri = period * i_contribution

                contribution_i = inc_contri+contribution

                balance += inc_contri

                period += 1

                

                projection[month_key]["total_balance"] = balance
                projection[month_key]["contribution"] = contribution_i

                if month_key in boost_dates:
                    #print('yes',boost_dates[month_key])
                    op_type = boost_dates[month_key]['op_type']
                    if op_type > 1:
                        balance -= boost_dates[month_key]['amount']
                        projection[month_key]["total_balance"] -= boost_dates[month_key]['amount']
                    else:
                        projection[month_key]["total_balance"] += boost_dates[month_key]['amount']
                        balance += boost_dates[month_key]['amount']

                

                if projection[month_key]["month"] is None:
                    projection[month_key]["month"] = month_key
                    projection[month_key]["month_word"] = convertDateTostring(pay_date, "%b, %Y")

                initial_balance = balance
                initial_contribution = contribution_i

                pay_date = next_contribution_date
                

   

    
    return sorted(
        [{
            "month": month,
            "total_balance": round(data['total_balance'], 2),
            "contribution": round(data['contribution'], 2),
            "month_word": data['month_word'],
        } for month, data in projection.items()],
        key=lambda x: x['month']
    )
    

  

@app.route('/api/saving-contributions-nextpgu/<int:user_id>', methods=['GET'])
def saving_contributions_next_pgu(user_id:int):

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    projection_list = []    

    session = None

    
    try:
        
        session = db.session

        # Check if the session is connected (optional, but a good practice)
        if not session.is_active:
            raise Exception("Database session is not active.")
        
        query = session.query(
            Saving.id,
            Saving.saver,
            Saving.contribution,
            Saving.increase_contribution_by,
            Saving.interest,
            Saving.starting_amount,
            Saving.period,
            Saving.goal_amount,
            Saving.starting_date,
            Saving.next_contribution_date.label('next_pay_date'),
            Saving.repeat,            
            Saving.user_id,
            Saving.total_balance,
            Saving.total_balance_xyz,
            Saving.total_monthly_balance,
            SavingBoost.saving_boost,
            SavingBoost.pay_date_boost,
            SavingBoost.repeat_boost,
            SavingBoost.next_contribution_date.label('next_pay_date_boost'),
            SavingBoost.boost_operation_type,
            SavingBoost.total_balance.label('total_balance_boost'),
            SavingBoost.total_monthly_balance.label('total_monthly_balance_boost')
        ).outerjoin(
            SavingBoost, 
            (SavingBoost.saving_id == Saving.id) &            
            (SavingBoost.deleted_at.is_(None)) &
            (SavingBoost.closed_at.is_(None)) &
            #(SavingBoost.pay_date_boost >= today) &
            (func.coalesce(SavingBoost.next_contribution_date, SavingBoost.pay_date_boost) >= today) #&  # Use pay_date_boost if next_pay_date_boost is None
            #(func.coalesce(SavingBoost.next_pay_date_boost, SavingBoost.pay_date_boost) >= Saving.next_pay_date)  # Check if pay_date_boost or next_pay_date_boost is >= saving's next pay date
        ).filter(
            Saving.user_id == user_id,
            Saving.deleted_at.is_(None),
            Saving.closed_at.is_(None),
            Saving.goal_reached.is_(None),
            Saving.next_contribution_date >=today
        ).order_by(
            Saving.id,  # Order by saving ID
            Saving.next_contribution_date.asc(),
            func.coalesce(SavingBoost.next_contribution_date, SavingBoost.pay_date_boost).asc()  # Order boosts by pay_date in ascending order
        )

        results = query.all()
        projections = process_projections(results)
        projection_list = get_projection_list(projections[0],projections[1])
    except OperationalError as e:
        print(f"Operational error: {str(e)}")
        return jsonify({
            "payLoads": {
                'projection_list': [],
                'projection': [],
                'exception': "Database operational error. Please try again later."
            }
        })
    except TimeoutError as e:
        print(f"Timeout error: {str(e)}")
        return jsonify({
            "payLoads": {
                'projection_list': [],
                'projection': [],
                'exception': "Database timeout error. Please try again later."
            }
        })
    except DBAPIError as e:
        print(f"DBAPI error: {str(e)}")
        return jsonify({
            "payLoads": {
                'projection_list': [],
                'projection': [],
                'exception': "Database API error. Please try again later."
            }
        })
    except ConnectionError as e:
        print(f"Connection error: {str(e)}")
        return jsonify({
            "payLoads": {
                'projection_list': [],
                'projection': [],
                'exception': "Unable to connect to the database. Please try again later."
            }
        })
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        if session:
            session.rollback()
        return jsonify({
            "payLoads": {
                'projection_list': [],
                'projection': [],
                'exception': f"Unexpected error: {str(e)}"
            }
        })

    finally:
        if session:
            session.close()
    
    return jsonify({
        "payLoads": {
            'projection_list': projection_list,            
            'exception':None
        }
    })



@app.route('/api/saving-contributions-nextpg/<int:saving_id>', methods=['GET'])
def saving_contributions_next_pg(saving_id:int):

    
    result =[]

    return jsonify({
        "payLoads":{                                     
            'projection_list':result
        }        
    })