"""Set the passcode that opens locked notes. Stored hashed in MongoDB (settings._id = "passcode").

Usage: cd backend && ../.venv/bin/python scripts/set_passcode.py
"""
import getpass
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from werkzeug.security import generate_password_hash

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
code = sys.argv[1] if len(sys.argv) > 1 else getpass.getpass("New passcode: ")
if not code:
    raise SystemExit("Passcode can't be empty")
db = MongoClient(os.environ["MONGODB_URI"])[os.environ.get("MONGODB_DB", "copeemachine")]
db.settings.update_one({"_id": "passcode"}, {"$set": {"hash": generate_password_hash(code)}}, upsert=True)
print("Passcode saved.")
