"""
Student Library Management System
---------------------------------
A command-line application built with Python and SQLite.

Features:
  - Add / view / delete students
  - Add / view / search / delete books
  - Issue a book to a student and return it
  - Automatic fine calculation for late returns
  - Reports: issued books, overdue books, student history
"""

import sqlite3
from datetime import date, datetime, timedelta

DB_NAME = "library.db"
LOAN_DAYS = 14          # days a book can be kept
FINE_PER_DAY = 2        # fine in rupees per late day


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------
def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create the tables if they do not exist yet."""
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                student_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                department TEXT NOT NULL,
                email      TEXT
            );

            CREATE TABLE IF NOT EXISTS books (
                book_id  INTEGER PRIMARY KEY AUTOINCREMENT,
                title    TEXT NOT NULL,
                author   TEXT NOT NULL,
                category TEXT,
                copies   INTEGER NOT NULL DEFAULT 1 CHECK (copies >= 0)
            );

            CREATE TABLE IF NOT EXISTS transactions (
                txn_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id  INTEGER NOT NULL,
                book_id     INTEGER NOT NULL,
                issue_date  TEXT NOT NULL,
                due_date    TEXT NOT NULL,
                return_date TEXT,
                fine        INTEGER DEFAULT 0,
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (book_id)    REFERENCES books(book_id)
            );
            """
        )


# ---------------------------------------------------------------------------
# Input helpers (keep the program from crashing on bad input)
# ---------------------------------------------------------------------------
def ask_text(prompt, required=True):
    while True:
        value = input(prompt).strip()
        if value or not required:
            return value
        print("  This field cannot be empty.")


def ask_int(prompt, minimum=None):
    while True:
        raw = input(prompt).strip()
        try:
            number = int(raw)
        except ValueError:
            print("  Please enter a whole number.")
            continue
        if minimum is not None and number < minimum:
            print(f"  Number must be at least {minimum}.")
            continue
        return number


def print_table(headers, rows):
    """Print rows as a simple aligned table."""
    if not rows:
        print("  (no records found)")
        return
    table = [headers] + [[str(c) if c is not None else "-" for c in r] for r in rows]
    widths = [max(len(row[i]) for row in table) for i in range(len(headers))]
    line = "+-" + "-+-".join("-" * w for w in widths) + "-+"
    print(line)
    print("| " + " | ".join(h.ljust(w) for h, w in zip(table[0], widths)) + " |")
    print(line)
    for row in table[1:]:
        print("| " + " | ".join(c.ljust(w) for c, w in zip(row, widths)) + " |")
    print(line)


# ---------------------------------------------------------------------------
# Student operations
# ---------------------------------------------------------------------------
def add_student():
    name = ask_text("Student name: ")
    department = ask_text("Department: ")
    email = ask_text("Email (optional): ", required=False)
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO students (name, department, email) VALUES (?, ?, ?)",
            (name, department, email or None),
        )
    print(f"  Student added with ID {cur.lastrowid}.")


def view_students():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT student_id, name, department, email FROM students ORDER BY student_id"
        ).fetchall()
    print_table(["ID", "Name", "Department", "Email"], rows)


def delete_student():
    student_id = ask_int("Student ID to delete: ", minimum=1)
    with get_connection() as conn:
        pending = conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE student_id = ? AND return_date IS NULL",
            (student_id,),
        ).fetchone()[0]
        if pending:
            print("  Cannot delete: this student still has unreturned books.")
            return
        # remove history first so the foreign key does not block deletion
        conn.execute("DELETE FROM transactions WHERE student_id = ?", (student_id,))
        cur = conn.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
    print("  Student deleted." if cur.rowcount else "  No student with that ID.")


# ---------------------------------------------------------------------------
# Book operations
# ---------------------------------------------------------------------------
def add_book():
    title = ask_text("Book title: ")
    author = ask_text("Author: ")
    category = ask_text("Category (optional): ", required=False)
    copies = ask_int("Number of copies: ", minimum=1)
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO books (title, author, category, copies) VALUES (?, ?, ?, ?)",
            (title, author, category or None, copies),
        )
    print(f"  Book added with ID {cur.lastrowid}.")


def view_books():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT book_id, title, author, category, copies FROM books ORDER BY book_id"
        ).fetchall()
    print_table(["ID", "Title", "Author", "Category", "Available"], rows)


def search_books():
    keyword = ask_text("Search by title, author or category: ")
    like = f"%{keyword}%"
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT book_id, title, author, category, copies FROM books
               WHERE title LIKE ? OR author LIKE ? OR category LIKE ?""",
            (like, like, like),
        ).fetchall()
    print_table(["ID", "Title", "Author", "Category", "Available"], rows)


def delete_book():
    book_id = ask_int("Book ID to delete: ", minimum=1)
    with get_connection() as conn:
        pending = conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE book_id = ? AND return_date IS NULL",
            (book_id,),
        ).fetchone()[0]
        if pending:
            print("  Cannot delete: copies of this book are currently issued.")
            return
        conn.execute("DELETE FROM transactions WHERE book_id = ?", (book_id,))
        cur = conn.execute("DELETE FROM books WHERE book_id = ?", (book_id,))
    print("  Book deleted." if cur.rowcount else "  No book with that ID.")


# ---------------------------------------------------------------------------
# Issue and return
# ---------------------------------------------------------------------------
def issue_book():
    student_id = ask_int("Student ID: ", minimum=1)
    book_id = ask_int("Book ID: ", minimum=1)
    with get_connection() as conn:
        student = conn.execute(
            "SELECT name FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
        if not student:
            print("  No student with that ID.")
            return
        book = conn.execute(
            "SELECT title, copies FROM books WHERE book_id = ?", (book_id,)
        ).fetchone()
        if not book:
            print("  No book with that ID.")
            return
        if book[1] <= 0:
            print("  Sorry, no copies of this book are available right now.")
            return
        already = conn.execute(
            """SELECT COUNT(*) FROM transactions
               WHERE student_id = ? AND book_id = ? AND return_date IS NULL""",
            (student_id, book_id),
        ).fetchone()[0]
        if already:
            print("  This student already has a copy of this book.")
            return

        today = date.today()
        due = today + timedelta(days=LOAN_DAYS)
        conn.execute(
            """INSERT INTO transactions (student_id, book_id, issue_date, due_date)
               VALUES (?, ?, ?, ?)""",
            (student_id, book_id, today.isoformat(), due.isoformat()),
        )
        conn.execute("UPDATE books SET copies = copies - 1 WHERE book_id = ?", (book_id,))
    print(f"  '{book[0]}' issued to {student[0]}. Due date: {due.isoformat()}")


def return_book():
    student_id = ask_int("Student ID: ", minimum=1)
    book_id = ask_int("Book ID: ", minimum=1)
    with get_connection() as conn:
        txn = conn.execute(
            """SELECT txn_id, due_date FROM transactions
               WHERE student_id = ? AND book_id = ? AND return_date IS NULL""",
            (student_id, book_id),
        ).fetchone()
        if not txn:
            print("  No matching issued book found for this student.")
            return

        today = date.today()
        due = datetime.strptime(txn[1], "%Y-%m-%d").date()
        late_days = max((today - due).days, 0)
        fine = late_days * FINE_PER_DAY

        conn.execute(
            "UPDATE transactions SET return_date = ?, fine = ? WHERE txn_id = ?",
            (today.isoformat(), fine, txn[0]),
        )
        conn.execute("UPDATE books SET copies = copies + 1 WHERE book_id = ?", (book_id,))
    if fine:
        print(f"  Book returned {late_days} day(s) late. Fine: Rs. {fine}")
    else:
        print("  Book returned on time. No fine.")


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
def report_issued():
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT s.name, b.title, t.issue_date, t.due_date
               FROM transactions t
               JOIN students s ON s.student_id = t.student_id
               JOIN books b ON b.book_id = t.book_id
               WHERE t.return_date IS NULL
               ORDER BY t.due_date"""
        ).fetchall()
    print_table(["Student", "Book", "Issued", "Due"], rows)


def report_overdue():
    today = date.today().isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT s.name, b.title, t.due_date
               FROM transactions t
               JOIN students s ON s.student_id = t.student_id
               JOIN books b ON b.book_id = t.book_id
               WHERE t.return_date IS NULL AND t.due_date < ?
               ORDER BY t.due_date""",
            (today,),
        ).fetchall()
    print_table(["Student", "Book", "Was due on"], rows)


def report_student_history():
    student_id = ask_int("Student ID: ", minimum=1)
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT b.title, t.issue_date, t.return_date, t.fine
               FROM transactions t
               JOIN books b ON b.book_id = t.book_id
               WHERE t.student_id = ?
               ORDER BY t.issue_date""",
            (student_id,),
        ).fetchall()
    print_table(["Book", "Issued", "Returned", "Fine (Rs.)"], rows)


# ---------------------------------------------------------------------------
# Menus
# ---------------------------------------------------------------------------
def run_menu(title, options):
    """Show a sub-menu. options is a list of (label, function)."""
    while True:
        print(f"\n--- {title} ---")
        for i, (label, _) in enumerate(options, start=1):
            print(f"{i}. {label}")
        print("0. Back")
        choice = input("Choose an option: ").strip()
        if choice == "0":
            return
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            options[int(choice) - 1][1]()
        else:
            print("  Invalid choice, try again.")


def main():
    init_db()
    print("=" * 40)
    print("  STUDENT LIBRARY MANAGEMENT SYSTEM")
    print("=" * 40)

    while True:
        print("\n===== MAIN MENU =====")
        print("1. Students")
        print("2. Books")
        print("3. Issue a book")
        print("4. Return a book")
        print("5. Reports")
        print("0. Exit")
        choice = input("Choose an option: ").strip()

        if choice == "1":
            run_menu("Students", [
                ("Add student", add_student),
                ("View all students", view_students),
                ("Delete student", delete_student),
            ])
        elif choice == "2":
            run_menu("Books", [
                ("Add book", add_book),
                ("View all books", view_books),
                ("Search books", search_books),
                ("Delete book", delete_book),
            ])
        elif choice == "3":
            issue_book()
        elif choice == "4":
            return_book()
        elif choice == "5":
            run_menu("Reports", [
                ("Currently issued books", report_issued),
                ("Overdue books", report_overdue),
                ("Student borrowing history", report_student_history),
            ])
        elif choice == "0":
            print("Goodbye!")
            break
        else:
            print("  Invalid choice, try again.")


if __name__ == "__main__":
    main()
