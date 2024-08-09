
from app import app
import os
from home import *
from users import *
from bill import *
from billtype import *

#from datetime import datetime,timedelta

#import logging

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
    