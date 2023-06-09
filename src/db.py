import datetime

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
            unique=False,
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


def get_branches_with_users(users_db: Database):
    """Get branches along with users subscribed to them"""
    pipeline = [{
        "$unwind": "$branches"
    }, {
        "$match": {
            "branches.company": {
                "$exists": True
            }
        }
    }, {
        "$group": {
            "_id": {
                "branch_id": "$branches.id",
                "branch_name": "$branches.name",
                "company": "$branches.company.name"
            },
            "user_ids": {
                "$addToSet": "$id"
            }
        }
    }, {
        "$project": {
            "_id": 0,
            "branch_id": "$_id.branch_id",
            "branch_name": "$_id.branch_name",
            "company": "$_id.company",
            "user_ids": 1
        }
    }]
    return list(users_db.aggregate(pipeline))


if __name__ == '__main__':
    users_db = get_users_collection()
    companies_db = get_companies_collection()
    # print(get_branches_with_users(users_db))
    input_text = 'быстро'
    company = companies_db.find_one({"$text": {"$search": input_text}})
    print(company)