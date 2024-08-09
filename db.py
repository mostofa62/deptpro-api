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

mydb = myclient["deptpro-data"]

try:
    myclient.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

def my_col(name):
    return mydb[name]