
from app import app
import os
from home import *
from users import *
from bill import *
from billtype import *
from billextra import *
from billtransactions import *
from billpayments import *
from billprojection import *
from debt import *
from debttype import *
from debtpayoff import *
from debtusersetting import *
from ammortization import *

from income import *
from incomeboost import *
from incomeSourceBoost import *
from incometransactions import *
from savings import *
from savingboost import *
from savingcontributions import *
from paymentboost import *
from summarydata import *
from payoffstratagry import *
#from datetime import datetime,timedelta
from savingfunctions import *
## removing scheduler from this sytem
##from scheduler import *
#import logging
from calenderdata import *
#logging.basicConfig(filename='error.log',level=logging.DEBUG)
'''
token_expired_at = datetime.now().minute+120
print('Min',str(token_expired_at))
delta = timedelta(minutes=token_expired_at)
token_expired_at = datetime.now()+delta
print('now',datetime.now(),'later',token_expired_at)
'''
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5002))
    app.run(debug=True, host='0.0.0.0', port=port)
    