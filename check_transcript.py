import sys
sys.stdout.reconfigure(encoding="utf-8")
from database import get_connection, init_db
init_db()
with get_connection() as conn:
    rows = conn.execute(
        "SELECT video_id, title FROM videos WHERE transcript != '' LIMIT 5"
    ).fetchall()
    print("Videos with transcripts (first 5):")
    for r in rows:
        print(f"  {r['video_id']} | {r['title'][:60]}")
    
    total = conn.execute("SELECT COUNT(*) as c FROM videos WHERE transcript != ''").fetchone()["c"]
    print(f"\nTotal: {total} videos have transcripts")
