
from datetime import datetime
from dbpg import db
from sqlalchemy.exc import IntegrityError


RepeatFrequency = [
        {'label':'Daily','value':1},
        {'label':'Weekly','value':7},
        {'label':'BiWeekly','value':14},
        {'label':'Monthly','value':30},
        {'label': 'Quarterly', 'value': 90},
        {'label':'Annually','value':365}           
]


SavingInterestType = [
    {'label':'Simple','value':1},
    {'label':'Compound','value':2}
]

SavingStrategyType = [
    {'label':'Fixed Contribution','value':1},
    {'label':'Savings Challenge','value':2},
]

BoostOperationType = [

    {'label':'Deposit','value':1},
    {'label':'Withdraw','value':2},
]

ReminderDays = [
    {'value':0, 'label':'Disabled'},
    {'value':1, 'label':'1 days before'},
    {'value':2, 'label':'2 days before'},
    {'value':3, 'label':'3 days before'},
    {'value':4, 'label':'4 days before'},
    {'value':5, 'label':'5 days before'},
    {'value':6, 'label':'6 days before'},
    {'value':7, 'label':'7 days before'},
    {'value':8, 'label':'8 days before'},
    {'value':9, 'label':'9 days before'},
    {'value':10, 'label':'10 days before'},    

]

ExtraType = [   
    {'value':1, 'label':'Bill Purchase'},
    {'value':2, 'label':'Withdrawl'},
    

]

PayoffOrder = [
    {'value':0, 'label':'0'},
    {'value':1, 'label':'1'}    

]

TransactionType = [
    {'value':0, 'label':'None'},
    {'value':1, 'label':'Payment'},
    {'value':2, 'label':'Purchase'}    

]

TransactionMonth = [
    {'value': i, 'label': month}
    for i, month in enumerate([
        'January', 'February', 'March', 'April', 'May', 'June', 
        'July', 'August', 'September', 'October', 'November', 'December'
    ], start=1)
]

PreviousYear = datetime.now().year - 1
YearRange = 12

TransactionYear = [
    {'value': year, 'label': str(year)}
    for year in range(PreviousYear, PreviousYear + YearRange + 1)
]

def new_entry_option_data(data_obj: any, model_class, user_id: str) -> dict:
    """
    Function to create a new entry or return existing based on data.

    :param data_obj: The data object containing information for entry.
    :param model_class: The model class where the data should be inserted.
    :param user_id: The user ID to associate with the entry.
    :return: A dictionary with the entry's value or None.
    """
    if data_obj is None:
        return None

    # Assuming db.session provides the active session
    session = db.session

    try:
        if '__isNew__' in data_obj:
            # Insert new record
            new_record = model_class(
                name=data_obj.get('label'),                
                deleted_at=None,
                bysystem=False,
                user_id=user_id
            )
            
            session.add(new_record)
            session.commit()
            session.refresh(new_record)
            
            return new_record.id

        else:
            # If not new, return the existing record by its value (assumed to be an ID)
            if data_obj.get('value') == '':
                return None
            else:
                return int(data_obj['value'])

    except IntegrityError as ex:
        print('new option data save error',ex)
        session.rollback()
        return None
    finally:
        # No need to manually close the session if db.session handles it
        pass