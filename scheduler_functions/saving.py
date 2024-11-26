from datetime import datetime
import time
import os
from db import my_col,myclient
from util import *

saving = my_col('saving')
saving_contributions = my_col('saving_contributions')
saving_boost_contribution = my_col('saving_boost_contributions')
app_data = my_col('app_data')

def calculate_yearly_and_monthly_data():
    now = datetime.now()
    current_month = convertDateTostring(now, '%Y-%m')
    current_year = now.year
