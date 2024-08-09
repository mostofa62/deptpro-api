from app import app

#CORS(app)

@app.route('/api', methods=['GET'])
def home_page():
    return "<h1>Hello, we have started Debtpro, Testing Automated Deployment </h1>"


