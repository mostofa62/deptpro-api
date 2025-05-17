from collections import defaultdict
import os
from flask import Flask,request,jsonify, json
from sqlalchemy import Integer, case, cast, func
#from flask_cors import CORS, cross_origin
from models import Income, IncomeBoost
from incomeutil import calculate_breakdown_future, get_delta, get_remaining_frequency_with_next
from app import app
from util import *
from datetime import datetime,timedelta
from dbpg import db
from sqlalchemy.orm import aliased
import calendar
from sqlalchemy.exc import OperationalError, TimeoutError, DBAPIError
#from memory_profiler import profile
from dateutil.relativedelta import relativedelta
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
                        "id":row.income_boost_id,
                        "income_boost": row.income_boost,
                        "pay_date_boost": row.pay_date_boost,
                        "repeat_boost": row.repeat_boost,  # Parsed JSON
                        "next_pay_date_boost": row.next_pay_date_boost
                    })


    return list(income_dict.values())





'''
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

'''


def get_projection_list(projection_list,total_gross_income, total_net_income):
    projection = defaultdict(lambda: {
        "base_gross_income": 0.0, 
        "base_net_income": 0.0,
        "month_word": "",
        "month": None, 
        "earners": {}
    })

    start_date = datetime.now().replace(day=1)  # Start from the current month
    end_date = start_date + timedelta(days=365)  # Next 12 months

     

    for income in projection_list:
        pay_date = income["next_pay_date"]
        repeat_days = income["repeat"]["value"]
        gross_income, net_income = income["gross_income"], income["net_income"]
        income_id, earner_name = income["id"], income["earner"]

        # Initialize total incomes with previous values
        #total_gross_income = income.get("total_gross_income", 0.0)
        #total_net_income = income.get("total_net_income", 0.0)

        # Process Income Boosts and store them in a dict for quick lookup
        boost_dates = {}
        for boost in income.get("income_boosts", []):
            boost_date, boost_amount = boost["pay_date_boost"], boost["income_boost"]
            boost_repeat = boost["repeat_boost"]["value"]

            while boost_date < end_date:
                month_key = int(f"{boost_date.year}{boost_date.month:02d}")
                boost_dates[month_key] = boost_dates.get(month_key, 0) + boost_amount
                
                if boost_repeat == 0: 
                    break  # One-time boost
                boost_date += get_delta(boost_repeat)  # Apply boost frequency

        # Process Income (main salary payments)
        while pay_date < end_date:
            month_key = int(f"{pay_date.year}{pay_date.month:02d}")

            # Accumulate previous total + new income
            total_gross_income += gross_income
            total_net_income += net_income

            # Add base income (accumulated)
            projection[month_key]["base_gross_income"] += total_gross_income
            projection[month_key]["base_net_income"] += total_net_income

            # Apply Boost (if any for this month)
            if month_key in boost_dates:
                total_gross_income += boost_dates[month_key]
                total_net_income += boost_dates[month_key]
                projection[month_key]["base_gross_income"] += boost_dates[month_key]
                projection[month_key]["base_net_income"] += boost_dates[month_key]

            # Set month metadata only once
            if projection[month_key]["month"] is None:
                projection[month_key]["month"] = month_key
                projection[month_key]["month_word"] = convertDateTostring(pay_date, "%b, %Y")

            # Add earner details
            earner_data = projection[month_key]["earners"].setdefault(income_id, {
                "earner": earner_name,
                "earner_id": income_id,
                "gross_income": 0,
                "net_income": 0
            })
            earner_data["gross_income"] += total_gross_income
            earner_data["net_income"] += total_net_income

            pay_date += get_delta(repeat_days)  # Move to next pay cycle

    # Convert projection dict to sorted list
    return sorted(
        [{
            "month": month,
            "base_gross_income": round(data['base_gross_income'], 2),
            "base_net_income": round(data['base_net_income'], 2),
            "month_word": data['month_word'],
            "earners": list(data['earners'].values())
        } for month, data in projection.items()],
        key=lambda x: x['month']
    )

        
    

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
            IncomeBoost.id.label('income_boost_id'),
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

        result = session.query(
            func.sum(Income.total_gross_income),
            func.sum(Income.total_net_income)
        ).filter(
            Income.id == income_id,
            Income.deleted_at == None
        ).first()

        # Unpack and round the results, defaulting to 0 if None
        total_gross_income = round(result[0] or 0, 2)
        total_net_income = round(result[1] or 0, 2)        

        
        projection_list = process_projections(results)
        projection_list = generate_projection(projection_list, total_gross_income, total_net_income)                    

            
            
            

            
        
        
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


@app.route('/api/income-transactions-nextpguv/<int:user_id>', methods=['GET'])
#@profile
async def income_transactions_next_pguv(user_id:int):

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    projection_list = []
    projection = []    

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
            IncomeBoost.id.label('income_boost_id'),
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

        result = session.query(
            func.sum(Income.total_gross_income),
            func.sum(Income.total_net_income)
        ).filter(
            Income.user_id == user_id,
            Income.deleted_at == None
        ).first()

        # Unpack and round the results, defaulting to 0 if None
        total_gross_income = round(result[0] or 0, 2)
        total_net_income = round(result[1] or 0, 2)        

        
        projection = process_projections(results)
        projection_list = get_projection_list(projection, total_gross_income, total_net_income)                    

            
            
            

            
        
        
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
            'projection':projection,            
            'exception':None
        }
    })
    


def generate_projection(data, total_gross_amount=0, total_net_amount=0):
    start_dt = datetime.now().replace(day=1)
    end_dt = start_dt + relativedelta(years=1)

    start_year = start_dt.year
    start_month = start_dt.month

    months = [
        (start_year + (start_month + i - 1) // 12) * 100 + (start_month + i - 1) % 12 + 1
        for i in range((end_dt.year - start_year) * 12 + (end_dt.month - start_month) + 1)
    ]

    account_states = {f"{acc['id']}": acc["next_pay_date"].date() for acc in data}
    projection_list = []

    #print('account_states',account_states)
    
    progressive_gross_total = total_gross_amount
    progressive_net_total = total_net_amount
    for index, month_key in enumerate(months):
        results_by_month = {}
        year = month_key // 100
        month = month_key % 100

        label = f"{year}{month:02d}"
        results_by_month[index] = {}
        
        monthly_gross_total = 0
        monthly_net_total = 0
        results_by_month[index]["earners"] = []
        for acc in data:
            ac_id = f"{acc['id']}"            
            freq = acc["repeat"]["value"]
            gross_income = acc["gross_income"]
            net_income = acc["net_income"]
            acc_sd = account_states[ac_id]
            income_boosts = acc["income_boosts"]

            income_boost_gross = 0
            income_boost_net = 0

            if acc_sd.year == year and acc_sd.month == month:
                result = get_remaining_frequency_with_next(acc_sd, freq, gross_income, net_income)

                if len(income_boosts)> 0:

                    account_states_i_b = {
                        f"{acc_ibs['id']}": (
                            acc_ibs["next_pay_date_boost"].date()
                            if acc_ibs["next_pay_date_boost"] is not None
                            else acc_ibs["pay_date_boost"].date()
                        )
                        for acc_ibs in income_boosts                        
                    }

                    for i_b in income_boosts:
                        ac_id_i_b = f"{i_b['id']}"
                        freq_i_b =  i_b['repeat_boost']['value']
                        gross_income_i_b = i_b["income_boost"]
                        net_income_i_b = i_b["income_boost"]
                        acc_sd_i_b = account_states_i_b[ac_id_i_b]

                        if acc_sd_i_b.year == year and acc_sd_i_b.month == month:
                            if freq_i_b < 1:
                                income_boost_gross += gross_income_i_b
                                income_boost_net += net_income_i_b
                            else:
                                result_i_b = get_remaining_frequency_with_next(acc_sd_i_b, freq_i_b, gross_income_i_b, net_income_i_b)
                                income_boost_gross += result_i_b['gross_income']
                                income_boost_net += result_i_b['net_income']
                                account_states_i_b[ac_id_i_b] = result_i_b["next_pay_date"]
                        



                #print(month_key,'income_boost_total',income_boost_total)        
                
                if len(result) > 0:
                    result["earner"] = acc["earner"]
                    result["earner_id"] = acc['id']
                #print('result',result)
                account_states[ac_id] = result["next_pay_date"]
                result["gross_income"] += income_boost_gross
                result["net_income"] += income_boost_net
                results_by_month[index]["earners"].append(result)
                monthly_gross_total += result["gross_income"]
                monthly_net_total += result["net_income"]
                del result["next_pay_date"]
            
            #results_by_month[label]["monthly_gross_total"] = monthly_gross_total
            #results_by_month[label]["monthly_net_total"] = monthly_net_total

        progressive_gross_total += monthly_gross_total
        progressive_net_total += monthly_net_total
        results_by_month[index]["base_gross_income"] = progressive_gross_total
        results_by_month[index]["base_net_income"] = progressive_net_total
        results_by_month[index]["month"] = int(label)
        results_by_month[index]["month_word"] = convertDateTostring(datetime.strptime(label, "%Y%m"),"%b, %Y")
        projection_list.append(results_by_month[index])

    return projection_list
    



@app.route('/api/income-transactions-nextpgu/<int:user_id>', methods=['GET'])
#@profile
async def income_transactions_next_pgu(user_id:int):

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    projection_list = []
    projection = []    

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
            IncomeBoost.id.label('income_boost_id'),
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

        result = session.query(
            func.sum(Income.total_gross_income),
            func.sum(Income.total_net_income)
        ).filter(
            Income.user_id == user_id,
            Income.deleted_at == None
        ).first()

        # Unpack and round the results, defaulting to 0 if None
        total_gross_income = round(result[0] or 0, 2)
        total_net_income = round(result[1] or 0, 2)        

        
        projection = process_projections(results)
        projection_list = generate_projection(projection, total_gross_income, total_net_income)
        #print('projection_list',projection_list)

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
            'projection':projection,            
            'exception':None
        }
    })
    
