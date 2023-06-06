import os

from dotenv import load_dotenv

load_dotenv()

# General
REVIEW_API_URL = "https://public-api.reviews.2gis.com/2.0/branches"

# Telegram
TG_TOKEN = os.getenv('TG_TOKEN')
SECRET_KEY = os.getenv('SECRET_KEY')

# Database
MONGO_URI = os.getenv('MONGO_URI')
MONGO_DB_NAME = os.getenv('MONGO_DB_NAME')