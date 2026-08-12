import sqlite3
from datetime import date, timedelta


def fix_ids():
    conn = sqlite3.connect("attendance.db")
    cur = conn.cursor()

    cur.execute("SELECT id, full_name FROM students ORDER BY id")
    students = cur.fetchall()

    id_map = {old_id: new_id for new_id, (old_id, name) in enumerate(students, start=1)}

    cur.execute("CREATE TABLE students_new (id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL)")
    for old_id, name in students:
        cur.execute("INSERT INTO students_new (id, full_name) VALUES (?, ?)", (id_map[old_id], name))

    cur.execute("SELECT id, student_id FROM attendance")
    for att_id, old_student_id in cur.fetchall():
        new_student_id = id_map.get(old_student_id)
        if new_student_id:
            cur.execute("UPDATE attendance SET student_id = ? WHERE id = ?", (new_student_id, att_id))

    cur.execute("DROP TABLE students")
    cur.execute("ALTER TABLE students_new RENAME TO students")
    cur.execute("DELETE FROM sqlite_sequence WHERE name='students'")
    cur.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('students', ?)", (len(students),))

    conn.commit()
    conn.close()
    print("ID'lar 1 dan qayta raqamlandi ✅")


def init_db():
    conn = sqlite3.connect("attendance.db")
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        status TEXT NOT NULL,       -- 'present' yoki 'absent'
        reason TEXT,                -- 'sababli', 'sababsiz' yoki NULL (kelgan bo'lsa)
        FOREIGN KEY (student_id) REFERENCES students(id)
    )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY
        )
        """)
    conn.commit()
    conn.close()


def get_weekly_report():
    week_ago = str(date.today() - timedelta(days=7))
    conn = sqlite3.connect("attendance.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT students.full_name, attendance.date, attendance.reason
        FROM attendance
        JOIN students ON attendance.student_id = students.id
        WHERE attendance.date >= ? AND attendance.status = 'absent'
        ORDER BY students.full_name, attendance.date
    """, (week_ago,))
    result = cur.fetchall()
    conn.close()
    return result


def add_student(full_name):
    conn = sqlite3.connect("attendance.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO students (full_name) VALUES (?)", (full_name,))
    conn.commit()
    conn.close()


def get_all_students():
    conn = sqlite3.connect("attendance.db")
    cur = conn.cursor()
    cur.execute("SELECT id, full_name FROM students")
    result = cur.fetchall()
    conn.close()
    return result


def mark_attendance(student_id, date, status, reason=None):
    conn = sqlite3.connect("attendance.db")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO attendance (student_id, date, status, reason) VALUES (?, ?, ?, ?)",
        (student_id, date, status, reason)
    )
    conn.commit()
    conn.close()


def delete_student(student_id):
    conn = sqlite3.connect("attendance.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
    cur.execute("DELETE FROM students WHERE id = ?", (student_id,))
    conn.commit()
    conn.close()


def get_attendance_summary():
    conn = sqlite3.connect("attendance.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT students.full_name, attendance.date, attendance.status, attendance.reason
        FROM attendance
        JOIN students ON attendance.student_id = students.id
        ORDER BY attendance.date
    """)
    result = cur.fetchall()
    conn.close()
    return result


# --- AI function-calling uchun qo'shilgan funksiyalar ---

def get_absentees(query_date):
    """Berilgan sanada kelmagan (status='absent') o'quvchilar ro'yxati."""
    conn = sqlite3.connect("attendance.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT students.full_name, attendance.reason
        FROM attendance
        JOIN students ON attendance.student_id = students.id
        WHERE attendance.date = ? AND attendance.status = 'absent'
        ORDER BY students.full_name
    """, (query_date,))
    result = cur.fetchall()
    conn.close()
    return result


def get_presentees(query_date):
    """Berilgan sanada kelgan (status='present') o'quvchilar ro'yxati."""
    conn = sqlite3.connect("attendance.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT students.full_name
        FROM attendance
        JOIN students ON attendance.student_id = students.id
        WHERE attendance.date = ? AND attendance.status = 'present'
        ORDER BY students.full_name
    """, (query_date,))
    result = cur.fetchall()
    conn.close()
    return result

def get_attendance_percentage():
    conn = sqlite3.connect("attendance.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT students.full_name,
               SUM(CASE WHEN attendance.status='present' THEN 1 ELSE 0 END) as present,
               COUNT(*) as total
        FROM attendance
        JOIN students ON attendance.student_id = students.id
        GROUP BY students.id
        ORDER BY students.full_name
    """)
    result = cur.fetchall()
    conn.close()
    return result

def add_user(chat_id):
    conn = sqlite3.connect("attendance.db")
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (chat_id) VALUES (?)", (chat_id,))
    conn.commit()
    conn.close()


def get_all_users():
    conn = sqlite3.connect("attendance.db")
    cur = conn.cursor()
    cur.execute("SELECT chat_id FROM users")
    result = [row[0] for row in cur.fetchall()]
    conn.close()
    return result


def is_attendance_marked(query_date):
    """Berilgan sanada davomat umuman belgilanganmi yoki yo'qmi."""
    conn = sqlite3.connect("attendance.db")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM attendance WHERE date = ?", (query_date,))
    count = cur.fetchone()[0]
    conn.close()
    return count > 0


init_db()