# check_db.py
from app import create_app
import os

def check_database_info():
    app = create_app()
    with app.app_context():
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        
        info = {
            "database_uri": db_uri,
            "database_type": "SQLite" if "sqlite" in db_uri else "Other",
            "database_file": "bluewave.db" if "sqlite" in db_uri else "N/A",
            "file_exists": False,
            "file_size": 0
        }
        
        if "sqlite" in db_uri and os.path.exists("bluewave.db"):
            info["file_exists"] = True
            info["file_size"] = os.path.getsize("bluewave.db")
            
        return info

if __name__ == "__main__":
    info = check_database_info()
    print("=" * 50)
    print("DATABASE CONFIGURATION EVIDENCE")
    print("=" * 50)
    for key, value in info.items():
        print(f"{key:20}: {value}")
    print("=" * 50)
    
    if info["database_type"] == "SQLite":
        print("✅ CONFIRMED: Using SQLite database")
        if info["file_exists"]:
            print(f"✅ Database file exists: {info['file_size']} bytes")
        else:
            print(" Database file not found yet (will be created on first use)")
    else:
        print("Not using SQLite database")