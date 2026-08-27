"""Create the sample SQLite database used by the Streamlit application."""

from __future__ import annotations

import sqlite3
from pathlib import Path


DATABASE_PATH = Path(__file__).resolve().with_name("Student.db")

USERS = [
    ("Ashitosh", "ashitosh@example.com", 21, "Mumbai"),
    ("Rahul", "rahul@example.com", 22, "Pune"),
    ("Priya", "priya@example.com", 20, "Surat"),
    ("Amit", "amit@example.com", 24, "Ahmedabad"),
    ("Sneha", "sneha@example.com", 23, "Nashik"),
    ("Rohan", "rohan@example.com", 25, "Nagpur"),
    ("Neha", "neha@example.com", 21, "Mumbai"),
    ("Karan", "karan@example.com", 26, "Pune"),
    ("Pooja", "pooja@example.com", 22, "Vadodara"),
    ("Vikas", "vikas@example.com", 27, "Delhi"),
    ("Anjali", "anjali@example.com", 23, "Bangalore"),
    ("Saurabh", "saurabh@example.com", 28, "Hyderabad"),
    ("Kavita", "kavita@example.com", 24, "Jaipur"),
    ("Manish", "manish@example.com", 29, "Kolkata"),
    ("Riya", "riya@example.com", 20, "Surat"),
    ("Akash", "akash@example.com", 25, "Indore"),
    ("Meera", "meera@example.com", 22, "Chennai"),
    ("Nikhil", "nikhil@example.com", 26, "Mumbai"),
    ("Simran", "simran@example.com", 21, "Pune"),
    ("Varun", "varun@example.com", 30, "Ahmedabad"),
]


def initialize_database() -> int:
    """Create the users table and seed it once; return the current row count."""
    with sqlite3.connect(DATABASE_PATH) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                name VARCHAR(100) NOT NULL,
                email VARCHAR(150) NOT NULL,
                age INTEGER NOT NULL,
                city VARCHAR(100) NOT NULL
            )
            """
        )

        row_count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if row_count == 0:
            cursor.executemany(
                "INSERT INTO users (name, email, age, city) VALUES (?, ?, ?, ?)",
                USERS,
            )
            row_count = len(USERS)

    return row_count


if __name__ == "__main__":
    count = initialize_database()
    print(f"Sample database ready: {DATABASE_PATH} ({count} users)")
