import sqlite3


def connect_to_db(db_name):
    conn = sqlite3.connect(db_name)
    return conn


def create_tables(conn):
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS user_incidents (
                        incident_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_email INTEGER,
                        priority TEXT,
                        title TEXT,
                        description TEXT)
                        ''')
    conn.commit()


def add_or_update_user_incidents(conn, user_email, priority, title, description):
    cursor = conn.cursor()
    cursor.execute('''INSERT OR REPLACE INTO user_incidents (user_email, priority, title, description)
                      VALUES (?, ?, ?, ?)''', (user_email, priority, title, description))
    conn.commit()


def get_user_incident(conn, user_email):
    cursor = conn.cursor()
    cursor.execute('SELECT priority, title, description FROM user_incidents WHERE user_email=?', (user_email,))
    output = cursor.fetchall()
    if len(output) == 0:
        return 'Dear, ' + user_email + ' your incidents: Not Found'
    s = ''
    for i in output:
        for j in i:
            s += str(j) + ' '
        s += '\n'
    return 'Dear, ' + user_email + ' your incidents:\nPriority Title Description\n' + s


# Форма обратной связи. Обращение к БД для того чтобы оставить отзыв

def add_feedback_tables(conn):
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS feedback_table (
                        message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        message TEXT)
                        ''')


def add_feedback(conn, message):
    cursor = conn.cursor()
    cursor.execute('''INSERT OR REPLACE INTO feedback_table (message)
                      VALUES (?)''', (message,))
    conn.commit()



