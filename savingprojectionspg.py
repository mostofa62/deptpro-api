from collections import defaultdict
import os
from flask import jsonify,render_template_string
from sqlalchemy import Integer, and_, case, cast, func
from savingutil import get_delta, get_freq_month
from app import app
from util import *
from datetime import datetime,timedelta

from models import AppData, Saving, SavingBoost
from dbpg import db
from sqlalchemy.orm import aliased
from sqlalchemy.exc import OperationalError, TimeoutError, DBAPIError
import math


# Aliasing the SavingBoost table to avoid conflict in the joins
saving_boosts_1 = aliased(SavingBoost)
saving_boosts_2 = aliased(SavingBoost)


def process_projections(results=None):

    saving_dict = {}
    #goal_amount = 0

    saving_account_names = {}

    if results:
        
        for row in results:
            #goal_amount += row.goal_amount
            saving_id = row.id
            print('saving_id',saving_id)
            if saving_id not in saving_dict:
                saving_account_names[f"{saving_id}"] = row.saver
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


    #return (list(saving_dict.values()),goal_amount)
    return (list(saving_dict.values()),saving_account_names)


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



def get_projection_list(projection_list, goal_amount, total_balance_xyz):
    # Dictionary to store merged results
    projection = defaultdict(lambda: {
        "total_balance": 0,
        "contribution": 0,       
        "month_word": "",
        "month": None,
    })

    initial_balance = total_balance_xyz
    initial_contribution = total_balance_xyz
    for saving in projection_list:
        pay_date = saving["next_pay_date"]
        frequency = saving["repeat"]["value"]
        #contribution = initial_contribution+saving['contribution']
        #balance = initial_balance + saving['total_balance']
        balance = initial_balance
        contribution = initial_contribution
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
    

def generate_projection(data):
    month_wise_projection = defaultdict(dict)
    all_account_ids = set()
    

    for acc in data:
        ac_id = str(acc['id'])
        all_account_ids.add(ac_id)
        saver = acc['saver']   
        freq = acc["repeat"]["value"]
        contribution = acc['contribution']
        increase_contribution_by = acc['increase_contribution_by']
        interest = acc['interest']
        balance = acc['total_balance']        
        goal_amount = acc['goal_amount']
        pay_date = acc["next_pay_date"].date()
        saving_boosts = acc["saving_boosts"]
        

        # Initialize saving boost tracker
        boost_states = []
        for s_b in saving_boosts:
            next_boost_date = s_b["next_pay_date_boost"].date() if s_b["next_pay_date_boost"] else s_b["pay_date_boost"].date()
            boost_states.append({
                "amount": s_b["saving_boost"],
                "freq": s_b["repeat_boost"]["value"],
                "next_date": next_boost_date,
                "op_type":s_b["op_type"],
                "applied": False  # default for one-time
            })

       

        while balance < goal_amount:

            
            result = get_freq_month(
                balance,
                contribution,
                interest,
                freq,
                pay_date,
                increase_contribution_by
            )

            pay_date = result["next_pay_date"]
            balance = result["balance"]
            period = result["period"]
            total_contribution = result['total_contribution']
            total_interest = result['total_interest']
            interest_rate = result['interest_rate']
            i_contribution = result['i_contribution']
            total_i_contribution = result['total_i_contribution']

            

            month_label = int(f"{pay_date.year}{pay_date.month:02d}")
            month_word = convertDateTostring(pay_date, "%b, %Y")

            if 'data' not in month_wise_projection[month_label]:
                month_wise_projection[month_label]['data'] = {}

            if ac_id not in month_wise_projection[month_label]['data']:
                month_wise_projection[month_label]['data'][ac_id] = {}

            if 'month_word' not in month_wise_projection[month_label]:
                month_wise_projection[month_label]['month_word'] = month_word

            if ac_id not in month_wise_projection[month_label]:
                
                month_wise_projection[month_label][ac_id] = 0

            

            # Apply eligible boosts
            total_boost = 0
            for b in boost_states:
                
                
                if b["freq"] == 0:
                    if not b.get("applied", False) and b["next_date"] <= pay_date:
                        if b["op_type"] < 2:
                            balance += b["amount"]
                            total_boost += b["amount"]
                        else:
                            balance -= b["amount"]
                            total_boost -= b["amount"]
                        b["applied"] = True
                else:
                    month_label_n_d = int(f"{b['next_date'].year}{b['next_date'].month:02d}")
                    
                    if month_label_n_d == month_label:
                        if b["op_type"] < 2:
                            balance += b["amount"]
                            total_boost += b["amount"]
                        else:
                            balance -= b["amount"]
                            total_boost -= b["amount"]
                        b["next_date"] += get_delta(b["freq"])

            
           
            if(balance > goal_amount):
                del month_wise_projection[month_label][ac_id]                
                balance = goal_amount
            
            month_wise_projection[month_label][ac_id] = round(balance,2)
            month_wise_projection[month_label]['month_word'] = month_word
            month_wise_projection[month_label]['data'][ac_id]["total_boosts"] = round(total_boost, 2)
            month_wise_projection[month_label]['data'][ac_id]['balance'] = round(balance, 2)            
            month_wise_projection[month_label]['data'][ac_id]['contribution'] = contribution
            month_wise_projection[month_label]['data'][ac_id]['total_contribution'] = total_contribution
            month_wise_projection[month_label]['data'][ac_id]['total_interest'] = total_interest
            month_wise_projection[month_label]['data'][ac_id]['interest_rate'] = interest_rate
            month_wise_projection[month_label]['data'][ac_id]['period'] = period
            month_wise_projection[month_label]['data'][ac_id]['saver'] = saver
            month_wise_projection[month_label]['data'][ac_id]['increase_contribution'] = i_contribution
            month_wise_projection[month_label]['data'][ac_id]['total_period_contribution'] = total_i_contribution
            month_wise_projection[month_label]['data'][ac_id]['goal_amount'] = goal_amount
            month_wise_projection[month_label]['data'][ac_id]['frequency'] = acc["repeat"]["label"]

    

    # Normalize: fill missing accounts with None
    all_months = sorted(month_wise_projection.keys())
    for month in all_months:
        for ac_id in all_account_ids:
            if ac_id not in month_wise_projection[month]:
                month_wise_projection[month][ac_id] = None  # use None so Recharts shows a line break

    return [{'month': month, **month_wise_projection[month]} for month in all_months]


  

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
        

        app_data = session.query(AppData).filter(AppData.user_id == user_id).first()

        result = session.query(
            func.sum(Saving.total_balance_xyz),
            func.sum(Saving.goal_amount)
        ).filter(
            Saving.user_id == user_id,
            Saving.deleted_at == None
        ).first()

        # Unpack and round the results, defaulting to 0 if None
        total_balance_xyz = round(result[0] or 0, 2)
        total_goal_amount = round(result[1] or 0, 2)

        next_pay_date = case(
            (Saving.starting_date >= today, Saving.starting_date),
            (
                and_(
                    Saving.next_contribution_date.isnot(None),
                    Saving.next_contribution_date >= today
                ),
                Saving.next_contribution_date
            ),
            else_=None  # or func.null() if needed explicitly
        ).label("next_pay_date")


        next_pay_date_boost = case(
            (SavingBoost.pay_date_boost >= today, SavingBoost.pay_date_boost),
            (
                and_(
                    SavingBoost.next_contribution_date.isnot(None),
                    SavingBoost.next_contribution_date >= today
                ),
                SavingBoost.next_contribution_date
            ),
            else_=None  # or func.null() if needed explicitly
        ).label("next_pay_date_boost")


        saving_boost_next_pay_date_expr = case(
            (SavingBoost.pay_date_boost >= today, SavingBoost.pay_date_boost),
            (
                and_(
                    SavingBoost.next_contribution_date.isnot(None),
                    SavingBoost.next_contribution_date >= today
                ),
                SavingBoost.next_contribution_date
            ),
            else_=None
        )
        
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
            next_pay_date,

            Saving.repeat,            
            Saving.user_id,
            Saving.total_balance,
            Saving.total_balance_xyz,
            Saving.total_monthly_balance,
            SavingBoost.saving_boost,
            SavingBoost.pay_date_boost,
            SavingBoost.repeat_boost,
            #SavingBoost.next_contribution_date.label('next_pay_date_boost'),
            next_pay_date_boost,
            SavingBoost.boost_operation_type,
            SavingBoost.total_balance.label('total_balance_boost'),
            SavingBoost.total_monthly_balance.label('total_monthly_balance_boost')
        ).outerjoin(
                SavingBoost,
                and_(
                    SavingBoost.saving_id == Saving.id,
                    SavingBoost.deleted_at.is_(None),
                    SavingBoost.closed_at.is_(None),
                    saving_boost_next_pay_date_expr.isnot(None),           # ✅ makes CASE usable
                    saving_boost_next_pay_date_expr >= today               # ✅ explicit comparison
                )
            ).filter(
            Saving.user_id == user_id,
            Saving.deleted_at.is_(None),
            Saving.closed_at.is_(None),
            Saving.goal_reached.is_(None),
            next_pay_date.isnot(None), 
            next_pay_date >= today
        ).order_by(
            Saving.id,
            next_pay_date.asc(),
            #func.coalesce(SavingBoost.next_contribution_date, SavingBoost.pay_date_boost).asc()
            next_pay_date_boost.asc()
        )

        results = query.all()
        process_projection = process_projections(results)
        projections = process_projection[0]
        projection_list = generate_projection(projections)
        saving_account_names = process_projection[1]
        #projection_list = get_projection_list(projections[0],projections[1])
        #projection_list = get_projection_list(projections,total_goal_amount, total_balance_xyz)

        financial_freedom_month = projection_list[-1]['month'] if projection_list else None
        #financial_freedom_target = int(round(projection_list[-1]['total_balance'],0)) if projection_list else None
        financial_freedom_target = total_goal_amount
        print(financial_freedom_month,financial_freedom_target, app_data.financial_freedom_target,app_data.financial_freedom_target!=financial_freedom_target )
        if app_data \
        and \
        (app_data.financial_freedom_month!=financial_freedom_month \
        or \
        app_data.financial_freedom_target!=financial_freedom_target)\
        :
            print('saving new data')
            app_data.financial_freedom_month = financial_freedom_month
            app_data.financial_freedom_target = financial_freedom_target
            session.add(app_data)
            session.commit()
            
            

        

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
            'projections':projections,
            'saving_account_names':saving_account_names,
            #'gen_projections':gen_projections,            
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




    

import pandas as pd
import random

def random_dark_color():
    dark_colors = [
        "#8B0000",  # Dark Red
        "#800000",  # Maroon
        "#A52A2A",  # Brown
        "#5F9EA0",  # Cadet Blue
        "#2F4F4F",  # Dark Slate Gray
        "#008080",  # Teal
        "#006400",  # Dark Green
        "#556B2F",  # Dark Olive Green
        "#228B22",  # Forest Green
        "#2E8B57",  # Sea Green
        "#191970",  # Midnight Blue
        "#00008B",  # Dark Blue
        "#000080",  # Navy
        "#483D8B",  # Dark Slate Blue
        "#4B0082",  # Indigo
        "#8B008B",  # Dark Magenta
        "#800080",  # Purple
        "#9932CC",  # Dark Orchid
        "#6A5ACD",  # Slate Blue
        "#8B4513",  # Saddle Brown
        "#B22222",  # Firebrick
        "#CD5C5C",  # Indian Red
        "#DC143C",  # Crimson
        "#7B68EE",  # Medium Slate Blue
        "#4682B4",  # Steel Blue
        "#4169E1",  # Royal Blue
        "#708090",  # Slate Gray
        "#696969",  # Dim Gray
    ]
    return random.choice(dark_colors)
@app.route('/api/saving-contributions-nextpgdata/<int:user_id>', methods=['GET'])
def saving_contributions_next_pg_data(user_id:int):

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    projection_list = []    

    session = None


    
    try:
        
        session = db.session

        # Check if the session is connected (optional, but a good practice)
        if not session.is_active:
            raise Exception("Database session is not active.")
        

        # app_data = session.query(AppData).filter(AppData.user_id == user_id).first()

        # result = session.query(
        #     func.sum(Saving.total_balance_xyz),
        #     func.sum(Saving.goal_amount)
        # ).filter(
        #     Saving.user_id == user_id,
        #     Saving.deleted_at == None
        # ).first()

        # # Unpack and round the results, defaulting to 0 if None
        # total_balance_xyz = round(result[0] or 0, 2)
        # total_goal_amount = round(result[1] or 0, 2)

        next_pay_date = case(
            (Saving.starting_date >= today, Saving.starting_date),
            (
                and_(
                    Saving.next_contribution_date.isnot(None),
                    Saving.next_contribution_date >= today
                ),
                Saving.next_contribution_date
            ),
            else_=None  # or func.null() if needed explicitly
        ).label("next_pay_date")


        next_pay_date_boost = case(
            (SavingBoost.pay_date_boost >= today, SavingBoost.pay_date_boost),
            (
                and_(
                    SavingBoost.next_contribution_date.isnot(None),
                    SavingBoost.next_contribution_date >= today
                ),
                SavingBoost.next_contribution_date
            ),
            else_=None  # or func.null() if needed explicitly
        ).label("next_pay_date_boost")


        saving_boost_next_pay_date_expr = case(
            (SavingBoost.pay_date_boost >= today, SavingBoost.pay_date_boost),
            (
                and_(
                    SavingBoost.next_contribution_date.isnot(None),
                    SavingBoost.next_contribution_date >= today
                ),
                SavingBoost.next_contribution_date
            ),
            else_=None
        )
        
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
            next_pay_date,

            Saving.repeat,            
            Saving.user_id,
            Saving.total_balance,
            Saving.total_balance_xyz,
            Saving.total_monthly_balance,
            SavingBoost.saving_boost,
            SavingBoost.pay_date_boost,
            SavingBoost.repeat_boost,
            #SavingBoost.next_contribution_date.label('next_pay_date_boost'),
            next_pay_date_boost,
            SavingBoost.boost_operation_type,
            SavingBoost.total_balance.label('total_balance_boost'),
            SavingBoost.total_monthly_balance.label('total_monthly_balance_boost')
        ).outerjoin(
                SavingBoost,
                and_(
                    SavingBoost.saving_id == Saving.id,
                    SavingBoost.deleted_at.is_(None),
                    SavingBoost.closed_at.is_(None),
                    saving_boost_next_pay_date_expr.isnot(None),           # ✅ makes CASE usable
                    saving_boost_next_pay_date_expr >= today               # ✅ explicit comparison
                )
            ).filter(
            Saving.user_id == user_id,
            Saving.deleted_at.is_(None),
            Saving.closed_at.is_(None),
            Saving.goal_reached.is_(None),
            next_pay_date.isnot(None), 
            next_pay_date >= today
        ).order_by(
            Saving.id,
            next_pay_date.asc(),
            #func.coalesce(SavingBoost.next_contribution_date, SavingBoost.pay_date_boost).asc()
            next_pay_date_boost.asc()
        )

        results = query.all()
        process_projection = process_projections(results)
        projections = process_projection[0]
        projection_list = generate_projection(projections)
        

        rows = []
        for month_data in projection_list:
            month = month_data["month_word"]
            for saver_id, details in month_data.get("data", {}).items():
                row = {
                    "Month": month,
                    "Saver ID": saver_id,
                    "Saver Name": details["saver"],
                    "Balance": details["balance"],
                    "Goal Amount":details["goal_amount"],
                    "Interest Rate": details["interest_rate"],
                    "Total Interest":details["total_interest"],
                    "Contribution":details["contribution"],
                    "Total Contribution": details["total_contribution"],
                    "Total Period": details["period"],
                    "Incresase Contribution":details["increase_contribution"],
                    "Total Period Contribution":details["total_period_contribution"],
                    "Total Boost":details["total_boosts"]

                    
                }
                rows.append(row)

    

        df = pd.DataFrame(rows)

        # Get unique Saver IDs
        unique_savers = df["Saver ID"].unique()

        color_map = {str(saver): random_dark_color() for saver in unique_savers}


        # Build HTML table with Tailwind and custom background
        table_html = """
        <div class="overflow-x-auto rounded shadow">
        <table class="table-auto w-full text-sm text-left text-gray-700 border border-gray-300">
            <thead class="bg-gray-200">
                <tr>
                    """ + "".join(f"<th class='px-4 py-2'>{col}</th>" for col in df.columns) + """
                </tr>
            </thead>
            <tbody>
        """

        for _, row in df.iterrows():
            bg = color_map.get(str(row["Saver ID"]), "#ffffff")
            table_html += f"<tr style='background-color:{bg};color:#ffffff;'>"
            for val in row:
                if isinstance(val, float):
                    table_html += f"<td class='px-4 py-2'>{val:,.2f}</td>"
                else:
                    table_html += f"<td class='px-4 py-2'>{val}</td>"
            table_html += "</tr>"

        table_html += "</tbody></table></div>"

        return render_template_string(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Projection Data</title>
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-gray-50 p-6">
            <h2 class="text-2xl font-bold mb-4">Projection Data</h2>
            {table_html}
        </body>
        </html>
        """)
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

    
    
   