
#from db import create_index_for_all
from app import app
import os
from home import home_page
from userspg import *
from billpg import *
from billtypepg import bill_type_dropdown_pg
from billextrapg import *
from billtransactionspg import *
from billpaymentspg import *
from billprojectionpg import *
from debtpg import *
from debtransactionspg import *
from debttypepg import *
from debtpayoffpg import *
from debtusersettingpg import *
from debtprojectionpg import debt_projection_pg
from ammortization import get_dept_amortization_dynamic

from savingspg import *
from savingcategoryboostpg import *
from savingboostpg import *
from savingcontributionspg import *
from savingprojectionspg import *

from paymentboostpg import *

from summarydatapg import *
from payoffstratagrypg import *
#from datetime import datetime,timedelta
#from savingfunctions import *
## removing scheduler from this sytem
##from scheduler import *
#from schedulerpg import *
#import logging
#from calenderdatapg import *
from calenderdata import calender_data_list
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
#create_index_for_all()
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5002))
    app.run(debug=True, host='0.0.0.0', port=port)
    #create_index_for_all()