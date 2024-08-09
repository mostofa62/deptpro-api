import os
from flask import Flask,request,jsonify
from flask_cors import CORS, cross_origin



app = Flask(__name__)
CORS(app)
'''
cors = CORS(app, resource={
    r"/*":{
        "origins":"*"
    }
})
'''


#if __name__ == '__main__':
#   app.run(debug = True)
