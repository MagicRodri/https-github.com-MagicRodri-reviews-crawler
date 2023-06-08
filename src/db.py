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
                "branch_name": "$branches.name"
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
            "user_ids": 1
        }
    }]
    return list(users_db.aggregate(pipeline))


if __name__ == '__main__':
    users_db = get_users_collection()
    # users_db.insert_one({
    #     'id': 1,
    #     'username': 'test2',
    #     'branches': [],
    #     'created_at': datetime.datetime.now()
    # })
    # users_db.insert_one({
    #     'id':
    #     2,
    #     'username':
    #     'test3',
    #     'branches': [{
    #         '_id': 1,
    #         'name': 'test',
    #         'company': 'test'
    #     }],
    #     'created_at':
    #     datetime.datetime.now()
    # })
    print(get_branches_with_users(users_db))