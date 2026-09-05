def load_posts(db):
    return db.execute('SELECT title FROM "Post"')
