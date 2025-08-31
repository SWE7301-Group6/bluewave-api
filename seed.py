from app import create_app, db
from models import User
from werkzeug.security import generate_password_hash

app = create_app()
with app.app_context():
    # Create default users
    if not User.query.filter_by(email="admin@bluewave.io").first():
        admin = User(
            email="admin@bluewave.io",
            password_hash=generate_password_hash("AdminPass123!"),
            role="admin",
            tier="raw"
        )
        db.session.add(admin)
    if not User.query.filter_by(email="researcher@bluewave.io").first():
        researcher = User(
            email="researcher@bluewave.io",
            password_hash=generate_password_hash("Research123!"),
            role="researcher",
            tier="processed"
        )
        db.session.add(researcher)
    if not User.query.filter_by(email="buoy01@bluewave.io").first():
        device = User(
            email="buoy01@bluewave.io",
            password_hash=generate_password_hash("BuoyToken01!"),
            role="device",
            tier="raw",
            buoy_id="BW-BOUY-0001"
        )
        db.session.add(device)
    db.session.commit()
    print("Seeded users: admin@bluewave.io / Researcher / Device")
