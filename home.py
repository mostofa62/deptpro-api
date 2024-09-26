from flask import jsonify, request
from app import app


#CORS(app)

@app.route('/api', methods=['GET'])
def home_page():
    return "<h1>Hello, we have started Debtpro, Testing Automated Deployment </h1>"


from util import *


@app.route('/api/calculateincome', methods=['POST'])
def calculateincome():
    if request.method == 'POST':
        data = json.loads(request.data)
        net_income = data.get('net_income',900)
        gross_income = data.get('gross_income',1000)
        income_boost = data.get('income_boost',200)
        repeat = data.get('repeat',7)
        repeat_boost = data.get('repeat_boost',14)
        pay_date = data.get('pay_date','2024-05-15')
        pay_date = convertStringTodate(pay_date)

        return jsonify({
            "data":{
                'net_income':net_income,
                'gross_income':gross_income,
                'income_boost': income_boost,
                'repeat':repeat,
                'repeat_boost':repeat_boost,
                'pay_date':pay_date  
            }
            
            })


