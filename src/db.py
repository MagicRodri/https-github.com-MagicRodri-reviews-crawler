import pymongo
from pymongo.collection import Collection
from pymongo.database import Database

import config


def get_db() -> Database:
    client = pymongo.MongoClient(config.MONGO_URI)
    db = client[config.MONGO_DB_NAME]
    return db


def get_reviews_collection(db: Database = get_db()) -> Collection:

    reviews_db = db.reviews
    if 'id' not in reviews_db.index_information():
        reviews_db.create_index(
            [('id', pymongo.ASCENDING)],
            unique=True,
        )
    return reviews_db


def get_branches_collection(db: Database = get_db()) -> Collection:
    branches_db = db.branches
    if 'id' not in branches_db.index_information():
        branches_db.create_index(
            [('id', pymongo.ASCENDING)],
            unique=True,
        )
    return branches_db


def get_companies_collection(db: Database = get_db()) -> Collection:
    companies_db = db.companies
    if 'name_text' not in companies_db.index_information():
        companies_db.create_index(
            [('name', 'text')],
            unique=True,
        )
    return companies_db


def get_users_collection(db: Database = get_db()) -> Collection:
    users_db = db.users
    if 'id' not in users_db.index_information():
        users_db.create_index(
            [('id', pymongo.ASCENDING)],
            unique=True,
        )
    return users_db


def insert_review(raw_review: dict):
    reviews_db = get_reviews_collection()
    inserted = reviews_db.insert_one(raw_review)
    return inserted.inserted_id


def insert_reviews(raw_reviews: list[dict]):

    reviews_db = get_reviews_collection()
    inserted = reviews_db.insert_many(raw_reviews)
    return inserted.inserted_ids


if __name__ == '__main__':
    a = {
        'id': 1,
        'text': 'text',
        'reply': None,
    }
    reviews_db = get_reviews_collection()

    print(reviews_db.index_information())