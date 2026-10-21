import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import SQLITE_PATH
import sqlite3

conn = sqlite3.connect(str(SQLITE_PATH))
deleted = conn.execute('DELETE FROM summaries').rowcount
conn.commit()
conn.close()
print(f'Cache cleared: {deleted} rows deleted. Next uploads will use new labeled format.')
