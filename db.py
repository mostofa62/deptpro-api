import pymongo
from dotenv import load_dotenv
import os
from pymongo.server_api import ServerApi

load_dotenv()

#MONGO_HOST=os.getenv("MONGO_HOST") #'192.168.10.55
#MONGO_PORT=os.getenv("MONGO_PORT") #'64000

MONGO_HOST = os.environ["MONGO_HOST"]
MONGO_PORT = os.environ["MONGO_PORT"]
MONGO_USER = os.environ["MONGO_USER"]
MONGO_PASSWORD = os.environ["MONGO_PASSWORD"]
#MONGO_URI = os.environ["MONGO_URI"]
#print(MONGO_PORT)
#exit()

myclient = pymongo.MongoClient(
    host = f"{MONGO_HOST}:{MONGO_PORT}",
    username=MONGO_USER,
    password=MONGO_PASSWORD
)

#myclient = pymongo.MongoClient(MONGO_URI, server_api=ServerApi('1'))
'''
mydb = myclient["deptpro-data"]

try:
    myclient.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

def my_col(name):
    return mydb[name]


def ensure_index(collection, index_fields, unique=False):
    """ Create an index only if it does not exist """
    collection_name = collection.name  # Get the collection name
    existing_indexes = [idx["key"] for idx in collection.list_indexes()]
    index_tuple = dict(index_fields)

    if index_tuple not in existing_indexes:
        collection.create_index(index_fields, unique=unique)
        print(f"[{collection_name}] Index created: {index_fields}")
    else:
        print(f"[{collection_name}] Index already exists: {index_fields}")


def create_index_for_all():
    # Create indexes for all collections
    print('...creating indexes...')

    # Unique indexes
    ensure_index(my_col('users'), [("email", 1)], unique=True)
    ensure_index(my_col('user_settings'), [("user_id", 1)], unique=True)
    ensure_index(my_col('app_data'), [("user_id", 1)], unique=True)

    # Heavy indexes for bill_transactions
    ensure_index(my_col('bill_transactions'), [("bill_acc_id", 1), ("type", 1), ("deleted_at", 1), ("created_at", -1)])
    ensure_index(my_col('bill_transactions'), [("user_id", 1), ("deleted_at", 1)])
    ensure_index(my_col('bill_transactions'), [("latest_payment_id", 1)])

    ensure_index(my_col('bill_transactions'), [("bill_acc_id", 1),("deleted_at", 1), ("due_date", -1), ("updated_at", -1)])

    # Indexes for bill_payment
    ensure_index(my_col('bill_payment'), [("bill_trans_id", 1)])
    ensure_index(my_col('bill_payment'), [("bill_trans_id", 1), ("pay_date", -1),("deleted_at", 1)])
    ensure_index(my_col('bill_payment'), [("bill_account_id", 1)])


    # Index for Income
    ensure_index(my_col('income'), [("deleted_at", 1),("closed_at", 1)])
    ensure_index(my_col('income_boost'), [
        ("income.value", 1),
        ("deleted_at", 1),
        ("closed_at", 1),
        ("repeat_boost.value", 1),
        ("income_boost", 1)  # Helps `$sum` aggregation
    ])
    ensure_index(my_col('income_transactions'),[
        ("income_id", 1),
        ("deleted_at", 1),
        ("closed_at", 1),
        ("pay_date", 1),
        ("base_input_boost", 1),  # Used in $sum
        ("month_word", 1),  # Used in $group and $project
        ("month", 1)  # Used in $group
    ])

    ensure_index(my_col('income_transactions'),[
        ("income_id", 1), 
        ("income_boost_id", 1), 
        ("deleted_at", 1), 
        ("closed_at", 1)
    ])


    print('...finished creating indexes...')

'''