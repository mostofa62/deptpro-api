
from datetime import datetime
import os
from flask_apscheduler import APScheduler

CALENDER_ENTRY_DURATION = os.environ["CALENDER_ENTRY_DURATION"]

def calender_entry():
    print('CALENER ENTRY RUNNING', datetime.now())


scheduler = APScheduler()
#scheduler.add_job(id = 'CALENDER_ENTRY', func=calender_entry, trigger="cron", minute='*/'+str(CALENDER_ENTRY_DURATION))
scheduler.add_job(id = 'CALENDER_ENTRY', func=calender_entry, trigger='interval',minutes=int(CALENDER_ENTRY_DURATION))
scheduler.start()