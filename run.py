
from db import create_index_for_all
from app import app
import os
from home import *
from users import *
from userspg import *
from bill import *
from billpg import *
from billtype import *
from billtypepg import bill_type_dropdown_pg
from billextra import *
from billextrapg import *
from billtransactions import *
from billtransactionspg import *
from billpayments import *
from billpaymentspg import *
from billprojection import *
from billprojectionpg import *
from debt import *
from debtpg import *
from debtransactionspg import *
from debttype import *
from debttypepg import *
from debtpayoff import *
from debtpayoffpg import *
from debtusersetting import *
from debtusersettingpg import *
from debtprojectionpg import debt_projection_pg
from ammortization import *

from income import *
from incomeboost import *
from incomeSourceBoost import *
from incometransactions import *
from savings import *
from savingspg import *
from savingcategoryboostpg import *
from savingboost import *
from savingboostpg import *

from savingcontributions import *
from savingcontributionspg import *
from savingprojectionspg import *
from paymentboost import *
from paymentboostpg import *
from summarydata import *
from summarydatapg import *
from payoffstratagry import *
from payoffstratagrypg import *
#from datetime import datetime,timedelta
from savingfunctions import *
## removing scheduler from this sytem
##from scheduler import *
from schedulerpg import *
#import logging
from calenderdata import *
from calenderdatapg import *

from incometransactionspg import *
from incomesourceboostpg import *
from incomepg import *
from incomeboostpg import *
from incomeprojectionspg import *
#logging.basicConfig(filename='error.log',level=logging.DEBUG)
'''
token_expired_at = datetime.now().minute+120
print('Min',str(token_expired_at))
delta = timedelta(minutes=token_expired_at)
token_expired_at = datetime.now()+delta
print('now',datetime.now(),'later',token_expired_at)
'''
create_index_for_all()
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5002))
    app.run(debug=True, host='0.0.0.0', port=port)
    #create_index_for_all()