FROM python:3.10.11

WORKDIR /app

# Copy requirements and install dependencies
COPY ./requirements.txt /app
RUN pip install -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the port
EXPOSE 5002

# Set environment variables
ENV FLASK_APP=run.py
#Change to production for production environment
ENV FLASK_ENV=production
#Set debug to 0 in production  
ENV FLASK_DEBUG=0  
ENV FLASK_RUN_PORT=5002
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=UTF-8

# MongoDB and other configuration settings
ENV MONGO_HOST=localhost
ENV MONGO_PORT=27017
ENV MONGO_USER=EdCoachAI
ENV MONGO_PASSWORD=edcoach#2023@july
ENV TOKEN_EXPIRATION=3600
ENV PORT=5002

# Use Gunicorn for production
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5002", "run:app"]
