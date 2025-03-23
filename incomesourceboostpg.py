from flask import jsonify, request
from sqlalchemy import func, select, update
from models import Income, IncomeBoost, IncomeBoostType, IncomeSourceType
from app import app
from util import *
from dbpg import db
from pgutils import *


@app.route('/api/delete-incomeboost-sourcepg', methods=['POST'])
def delete_income_boost_source_pg():
    if request.method == 'POST':
        data = json.loads(request.data)

        id = data['id']                   

        income_source_id = id
        message = None
        error = 0
        deleted_done = 0

        auto_assigned_id = None
        
        try:
            income_count = db.session.query(func.count()).filter(IncomeBoost.income_boost_source_id == id).scalar()
            if income_count > 0:
                auto_assigned_id = db.session.execute(
                    select(IncomeBoostType.id).where(IncomeBoostType.auto_assigned == 1).limit(1)
                ).scalar_one_or_none()

            if auto_assigned_id:
                stmt_update = update(IncomeBoost)\
                        .where(IncomeBoost.income_boost_source_id == id)\
                        .values(
                        income_boost_source_id=auto_assigned_id                                    
                        )
                db.session.execute(stmt_update)

            

            stmt_update = update(IncomeBoostType)\
                        .where(IncomeBoostType.id == id)\
                        .values(
                        deleted_at=datetime.now()                                    
                        )
            db.session.execute(stmt_update)
            db.session.commit()
            income_source_id = id
            error = 0
            deleted_done = 1
            message = f'Income boost type deleted Successfully'

        except Exception as ex:

            income_source_id = None
            error = 1
            deleted_done = 0
            message = f'Income boost type deleted Failed'


           


        return jsonify({
            "income_source_id":income_source_id,
            "message":message,
            "error":error,
            "deleted_done":deleted_done
        })

        

   

@app.route('/api/delete-income-sourcepg', methods=['POST'])
def delete_income_source_pg():
    if request.method == 'POST':
        data = json.loads(request.data)

        id = data['id']                   

        income_source_id = id
        message = None
        error = 0
        deleted_done = 0

        auto_assigned_id = None
        
        try:
            income_count = db.session.query(func.count()).filter(Income.income_source_id == id).scalar()
            if income_count > 0:
                auto_assigned_id = db.session.execute(
                    select(IncomeSourceType.id).where(IncomeSourceType.auto_assigned == 1).limit(1)
                ).scalar_one_or_none()

            if auto_assigned_id:
                stmt_update = update(Income)\
                        .where(Income.income_source_id == id)\
                        .values(
                        income_source_id=auto_assigned_id                                    
                        )
                db.session.execute(stmt_update)

            

            stmt_update = update(IncomeSourceType)\
                        .where(IncomeSourceType.id == id)\
                        .values(
                        deleted_at=datetime.now()                                    
                        )
            db.session.execute(stmt_update)
            db.session.commit()
            income_source_id = id
            error = 0
            deleted_done = 1
            message = f'Income source deleted Successfully'

        except Exception as ex:

            income_source_id = None
            error = 1
            deleted_done = 0
            message = f'Income source deleted Failed'


           


        return jsonify({
            "income_source_id":income_source_id,
            "message":message,
            "error":error,
            "deleted_done":deleted_done
        })

        

        
        
        


@app.route("/api/incomesourceboostpg-dropdown/<int:user_id>/<string:boost>", methods=['GET'])
@app.route("/api/incomesourceboostpg-dropdown/<int:user_id>", methods=['GET'])
async def incomesourceboostpg_dropdown(user_id: int, boost:str=None):
    
    income_source_types_list = []
    income_boost_types_list = []
    income_list = []

    if boost:
        income_boost_types = (
            db.session.query(IncomeBoostType.id, IncomeBoostType.name, IncomeBoostType.bysystem)
            .filter((IncomeBoostType.user_id == None) | (IncomeBoostType.user_id == user_id))
            .filter(IncomeBoostType.auto_assigned == 0)
            .filter(IncomeBoostType.deleted_at == None)
            .all()
        )

        income_boost_types_list = [
            {"value": boost.id, "label": boost.name, "bysystem": boost.bysystem}
            for boost in income_boost_types
        ]

        incomes = (
        db.session.query(Income.id, Income.earner, Income.repeat, Income.pay_date)
        .filter(Income.user_id == user_id, Income.deleted_at == None, Income.closed_at == None)
        .all()
        )
        
        income_list = [
            {
                "value": str(inc.id),
                "label": inc.earner,
                "repeat_boost": inc.repeat,  # Enum value as name
                "pay_date_boost": convertDateTostring(inc.pay_date,"%Y-%m-%d")
            }
            for inc in incomes
        ] 

    else:   
    
        # Fetch income source types
        income_source_types = (
            db.session.query(IncomeSourceType.id, IncomeSourceType.name, IncomeSourceType.bysystem)
            .filter((IncomeSourceType.user_id == None) | (IncomeSourceType.user_id == user_id))
            .filter(IncomeSourceType.auto_assigned == 0)
            .filter(IncomeSourceType.deleted_at == None)
            .all()
        )
        
        income_source_types_list = [
            {"value": src.id, "label": src.name, "bysystem": src.bysystem}
            for src in income_source_types
        ]


    
    # Fetch income boost types
    
    
    # Fetch incomes
    
    
    return jsonify({
        "payLoads": {
            "income_source": income_source_types_list,
            "income_boost_source": income_boost_types_list,
            "repeat_frequency":RepeatFrequency,
            "income_list": income_list
        }
    })



