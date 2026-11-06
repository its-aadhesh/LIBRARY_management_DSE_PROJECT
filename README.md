# Student Library Management System

A command-line application built with Python 3 and SQLite.

## Features
- Add, view and delete students
- Add, view, search and delete books
- Issue and return books (stock updates automatically)
- Late-return fine: Rs. 2 per day after a 14-day loan period
- Reports: currently issued books, overdue books, student borrowing history
- Input validation, so bad input does not crash the program

## Requirements
- Python 3.8 or newer
- No extra packages (sqlite3 is built into Python)

## How to run
```
python library.py
```
(Use `python3 library.py` on Mac/Linux.)

The database file `library.db` is created automatically on first run.
Delete it to start fresh.

## Database tables
- `students` (student_id, name, department, email)
- `books` (book_id, title, author, category, copies)
- `transactions` (txn_id, student_id, book_id, issue_date, due_date, return_date, fine)

## Settings
At the top of `library.py`:
- `LOAN_DAYS = 14`
- `FINE_PER_DAY = 2`
