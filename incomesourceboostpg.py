from flask import jsonify
from models import Income, IncomeBoostType, IncomeSourceType
from app import app
from util import *
from dbpg import db
from pgutils import *





@app.route("/api/incomesourceboostpg-dropdown/<int:user_id>/<string:boost>", methods=['GET'])
@app.route("/api/incomesourceboostpg-dropdown/<int:user_id>", methods=['GET'])
def incomesourceboostpg_dropdown(user_id: int, boost:str=None):
    
    income_source_types_list = []
    income_boost_types_list = []
    income_list = []

    if boost:
        income_boost_types = (
            db.session.query(IncomeBoostType.id, IncomeBoostType.name, IncomeBoostType.bysystem)
            .filter((IncomeBoostType.user_id == None) | (IncomeBoostType.user_id == user_id))
            .filter(IncomeBoostType.deleted_at == None)
            .all()
        )

        income_boost_types_list = [
            {"value": boost.id, "label": boost.name, "bysystem": boost.bysystem}
            for boost in income_boost_types
        ]

        incomes = (
        db.session.query(Income.id, Income.earner, Income.repeat, Income.next_pay_date)
        .filter(Income.user_id == user_id, Income.deleted_at == None, Income.closed_at == None)
        .all()
        )
        
        income_list = [
            {
                "value": str(inc.id),
                "label": inc.earner,
                "repeat_boost": inc.repeat,  # Enum value as name
                "pay_date_boost": convertDateTostring(inc.next_pay_date,"%Y-%m-%d")
            }
            for inc in incomes
        ] 

    else:   
    
        # Fetch income source types
        income_source_types = (
            db.session.query(IncomeSourceType.id, IncomeSourceType.name, IncomeSourceType.bysystem)
            .filter((IncomeSourceType.user_id == None) | (IncomeSourceType.user_id == user_id))
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



