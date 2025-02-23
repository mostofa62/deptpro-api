from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError
import psycopg2  # Required for raw database creation
from dotenv import load_dotenv
import os
from urllib.parse import quote_plus

# Load environment variables
load_dotenv()

# Default values
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "1234")
PG_DB = os.getenv("PG_DB", "deptpro")


#PG_PASSWORD = quote_plus(PG_PASSWORD) # removed quota for live connection

#print(PG_PASSWORD)
# Connection string (without specifying database, connects to default `postgres`)
POSTGRES_URL = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/postgres"

# Ensure database exists
def create_database_if_not_exists():
    try:
        # Connect to default postgres database
        conn = psycopg2.connect(
            dbname="postgres",
            user=PG_USER,
            password=PG_PASSWORD,
            host=PG_HOST,
            port=PG_PORT
        )
        conn.autocommit = True
        cursor = conn.cursor()

        # Check if database exists
        cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{PG_DB}';")
        exists = cursor.fetchone()

        if not exists:
            print(f"Database '{PG_DB}' not found. Creating...")
            cursor.execute(f"CREATE DATABASE {PG_DB};")
            print(f"Database '{PG_DB}' created successfully!")

        # Close connection
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error checking/creating database: {e}")

# Run the function to ensure the database exists
##create_database_if_not_exists()

# Now use the actual database connection
DATABASE_URL = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"
# print(f"DATABASE_URL: {DATABASE_URL}")
# engine = create_engine(DATABASE_URL)
# print('Engine',engine)

# # Create a session factory
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# # Base model for all tables
# Base = declarative_base()

db = SQLAlchemy()

# # Function to get a database session
# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()
