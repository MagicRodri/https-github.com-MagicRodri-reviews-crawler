import json
import sqlite3


def get_db_connection() -> sqlite3.Connection:
    connection = sqlite3.connect('reviews.db')
    return connection


def create_db():
    conn = get_db_connection()
    db = conn.cursor()
    # Create the reviews table
    db.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filiale CHAR(50),
            name CHAR(50),
            date CHAR(50),
            images TEXT,
            comment TEXT,
            reply_name CHAR(50),
            reply_date CHAR(50),
            reply_text TEXT
        )
    ''')
    conn.commit()
    conn.close()


def save_reviews_to_db(filiale: str, reviews: list[dict]):
    conn = get_db_connection()
    db = conn.cursor()

    sql = '''
        INSERT INTO reviews (filiale, name, date, images, comment, reply_name, reply_date, reply_text)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)'''

    rows = []
    for review in reviews:
        values = (filiale, review['name'], review['date'],
                  json.dumps(review['images']), review['comment'],
                  review['reply'].get('name'), review['reply'].get('date'),
                  review['reply'].get('text'))
        rows.append(values)

    db.executemany(sql, rows)

    conn.commit()
