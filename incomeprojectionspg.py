from collections import defaultdict
import os
from flask import Flask,request,jsonify, json
from sqlalchemy import Integer, case, cast, func
#from flask_cors import CORS, cross_origin
from models import Income, IncomeBoost
from incomeutil import calculate_breakdown_future, get_delta
from app import app
from util import *
from datetime import datetime,timedelta
from dbpg import db
from sqlalchemy.orm import aliased
import calendar
from sqlalchemy.exc import OperationalError, TimeoutError, DBAPIError
#from memory_profiler import profile

def process_projections(results=None):

    income_dict = {}

    if results:
        
        for row in results:
            income_id = row.id
            if income_id not in income_dict:
                income_dict[income_id] = {
                    "id": row.id,
                    "earner": row.earner,
                    "gross_income": row.gross_income,
                    "net_income": row.net_income,
                    "total_gross_income": row.total_gross_income,
                    "total_net_income": row.total_net_income,
                    "pay_date": row.pay_date,
                    "next_pay_date": row.next_pay_date,
                    "repeat": row.repeat,
                    "user_id": row.user_id,
                    "income_boosts": []  # Initialize nested list
                }

            if income_id in income_dict:
                # Append income_boost only if it exists
                if row.income_boost is not None:                    
                    income_dict[income_id]["income_boosts"].append({
                        "income_boost": row.income_boost,
                        "pay_date_boost": row.pay_date_boost,
                        "repeat_boost": row.repeat_boost,  # Parsed JSON
                        "next_pay_date_boost": row.next_pay_date_boost
                    })


    return list(income_dict.values())






def get_projection_list(projection_list):


    projection = defaultdict(lambda: {
        "base_gross_income": 0.0, 
        "base_net_income": 0.0,
        "month_word": "",
        "month":None, 
        "earners": {}
    })

    start_date = datetime.now().replace(day=1)  # Start from the current month
    end_date = start_date + timedelta(days=365)  # Next 12 months

    for income in projection_list:
        pay_date = income["next_pay_date"]
        repeat_days = income["repeat"]["value"]
        gross_income = income["gross_income"]
        net_income = income["net_income"]
        total_gross_income = income['total_gross_income']
        total_net_income = income['total_net_income']

                
        while pay_date < end_date:
            #print('pay_date',pay_date)
            month_key = int(f"{pay_date.year}{pay_date.month:02d}")
            projection[month_key]["month"] = month_key
            projection[month_key]["month_word"] = convertDateTostring(pay_date,"%b, %Y")
            total_gross_income += gross_income
            total_net_income += net_income
            projection[month_key]["base_gross_income"] += total_gross_income
            projection[month_key]["base_net_income"] += total_net_income
            # Add earner details (only if the earner hasn't been added yet for this month)
            if income["id"] not in projection[month_key]["earners"]:
                projection[month_key]["earners"][income["id"]] = {
                    "earner": income["earner"],
                    "earner_id": income["id"],
                    "gross_income": total_gross_income,
                    "net_income": total_net_income
                }
            # else:
            #     projection[month_key]["earners"][income["id"]]["gross_income"]+=gross_income
            #     projection[month_key]["earners"][income["id"]]["net_income"]+=net_income

            delta = get_delta(repeat_days)
            pay_date += delta


                
        # Process Income Boosts
        for boost in income["income_boosts"]:
            boost_date = boost["pay_date_boost"]
            boost_repeat = boost["repeat_boost"]["value"]
            boost_amount = boost["income_boost"]
            
            while boost_date < end_date:
                month_key = int(f"{boost_date.year}{boost_date.month:02d}")
                projection[month_key]["month"] = month_key
                projection[month_key]["month_word"] = convertDateTostring(pay_date,"%b, %Y")
                projection[month_key]["base_gross_income"] += boost_amount
                projection[month_key]["base_net_income"] += boost_amount  # Assuming net impact is same
                # Add earner details for the boost (only if the earner hasn't been added yet for this month)
                if income["id"] in projection[month_key]["earners"]:
                    projection[month_key]["earners"][income["id"]]["gross_income"]+=boost_amount
                    projection[month_key]["earners"][income["id"]]["net_income"]+=boost_amount
                
                if boost_repeat == 0:
                    break  # One-time boost

                delta = get_delta(boost_repeat)                        
                boost_date += delta


    
    result = sorted(
        [
            {
                "month": month,
                "base_gross_income": round(data['base_gross_income'], 2),
                "base_net_income": round(data['base_net_income'], 2),
                "month_word": data['month_word'],
                "earners": list(data['earners'].values())
            }
            for month, data in projection.items()
        ],
        key=lambda x: x['month']
    )

    return result


        
    

# Aliasing the IncomeBoost table to avoid conflict in the joins
income_boosts_1 = aliased(IncomeBoost)
income_boosts_2 = aliased(IncomeBoost)

@app.route('/api/income-transactions-nextpg/<int:income_id>', methods=['GET'])
async def income_transactions_next_pg(income_id:int):

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    projection_list = []    

    session = None

    
    try:
        
        session = db.session

        # Check if the session is connected (optional, but a good practice)
        if not session.is_active:
            raise Exception("Database session is not active.")

        
        query = session.query(
            Income.id,
            Income.earner,
            Income.gross_income,
            Income.net_income,
            Income.total_gross_income,
            Income.total_net_income,
            Income.pay_date,
            Income.next_pay_date,
            Income.repeat,
            Income.user_id,
            IncomeBoost.income_boost,
            IncomeBoost.pay_date_boost,
            IncomeBoost.repeat_boost,
            IncomeBoost.next_pay_date_boost
        ).outerjoin(
            IncomeBoost, 
            (IncomeBoost.income_id == Income.id) &            
            (IncomeBoost.deleted_at.is_(None)) &
            (IncomeBoost.closed_at.is_(None)) &
            #(IncomeBoost.pay_date_boost >= today) &
            (func.coalesce(IncomeBoost.next_pay_date_boost, IncomeBoost.pay_date_boost) >= today) #&  # Use pay_date_boost if next_pay_date_boost is None
            #(func.coalesce(IncomeBoost.next_pay_date_boost, IncomeBoost.pay_date_boost) >= Income.next_pay_date)  # Check if pay_date_boost or next_pay_date_boost is >= income's next pay date
        ).filter(
            Income.id == income_id,
            Income.deleted_at.is_(None),
            Income.closed_at.is_(None),
            Income.next_pay_date >=today
        ).order_by(
            Income.id,  # Order by income ID
            Income.next_pay_date.asc(),
            func.coalesce(IncomeBoost.next_pay_date_boost, IncomeBoost.pay_date_boost).asc()  # Order boosts by pay_date in ascending order
        )

        results = query.all()        

        
        projection_list = process_projections(results)
        projection_list = get_projection_list(projection_list)                    

            
            
            

            
        
        
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


@app.route('/api/income-transactions-nextpgu/<int:user_id>', methods=['GET'])
#@profile
async def income_transactions_next_pgu(user_id:int):

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    projection_list = []    

    session = None

    try:

        session = db.session

        # Check if the session is connected (optional, but a good practice)
        if not session.is_active:
            raise Exception("Database session is not active.")

        
        query = session.query(
            Income.id,
            Income.earner,
            Income.gross_income,
            Income.net_income,
            Income.total_gross_income,
            Income.total_net_income,
            Income.pay_date,
            Income.next_pay_date,
            Income.repeat,
            Income.user_id,
            IncomeBoost.income_boost,
            IncomeBoost.pay_date_boost,
            IncomeBoost.repeat_boost,
            IncomeBoost.next_pay_date_boost
        ).outerjoin(
            IncomeBoost, 
            (IncomeBoost.income_id == Income.id) &
            (IncomeBoost.user_id == user_id) &
            (IncomeBoost.deleted_at.is_(None)) &
            (IncomeBoost.closed_at.is_(None)) &
            #(IncomeBoost.pay_date_boost >= today) &
            (func.coalesce(IncomeBoost.next_pay_date_boost, IncomeBoost.pay_date_boost) >= today) #&  # Use pay_date_boost if next_pay_date_boost is None
            #(func.coalesce(IncomeBoost.next_pay_date_boost, IncomeBoost.pay_date_boost) >= Income.next_pay_date)  # Check if pay_date_boost or next_pay_date_boost is >= income's next pay date
        ).filter(
            Income.user_id == user_id,
            Income.deleted_at.is_(None),
            Income.closed_at.is_(None),
            Income.next_pay_date >=today
        ).order_by(
            Income.id,  # Order by income ID
            Income.next_pay_date.asc(),
            func.coalesce(IncomeBoost.next_pay_date_boost, IncomeBoost.pay_date_boost).asc()  # Order boosts by pay_date in ascending order
        )

        results = query.all()        

        
        projection_list = process_projections(results)
        projection_list = get_projection_list(projection_list)                    

            
            
            

            
        
        
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
    



   
    
