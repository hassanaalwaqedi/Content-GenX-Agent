"""One-time migration: add strategic insight columns to existing database."""
import sqlite3

conn = sqlite3.connect("content_intelligence.db")
for col, default in [
    ("target_audience", "Analysis pending"),
    ("strategic_advice", "Analysis pending"),
    ("content_gap", "Analysis pending"),
]:
    try:
        conn.execute(f"ALTER TABLE videos ADD COLUMN {col} TEXT DEFAULT '{default}'")
        print(f"  Added column: {col}")
    except sqlite3.OperationalError as e:
        if "duplicate" in str(e).lower():
            print(f"  Column {col} already exists")
        else:
            raise
conn.commit()
conn.close()
print("Migration complete.")
