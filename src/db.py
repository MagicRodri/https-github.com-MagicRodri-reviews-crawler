from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

import config


def get_db() -> Database:
    client = MongoClient(config.MONGO_URI)
    db = client[config.MONGO_DB_NAME]
    return db


def get_reviews_collection() -> Collection:
    db = get_db()
    reviews = db.reviews
    if 'id_text' not in reviews.index_information():
        reviews.create_index(
            [('id', 'text')],
            unique=True,
        )
    return reviews


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
    b = [a, a]
    reviews_db = get_reviews_collection()

    print(reviews_db.count_documents({}))