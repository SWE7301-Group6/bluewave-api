# app.py
from flask import Flask, jsonify
from flask_smorest import Api
from flask_jwt_extended import JWTManager
from config import Config
from db import db
# Import models so SQLAlchemy knows about all tables before create_all()
from models import *  # noqa: F401,F403
from auth import blp as AuthBlueprint
from observations import blp as ObservationsBlueprint
from telemetry import blp as TelemetryBlueprint


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Show SQL emitted by SQLAlchemy (good for demos / proof)
    app.config["SQLALCHEMY_ECHO"] = True

    # Initialize extensions
    db.init_app(app)
    api = Api(app)
    JWTManager(app)

    # Marshmallow / request validation errors -> consistent JSON
    @app.errorhandler(422)
    def handle_unprocessable(err):
        exc = getattr(err, "exc", None)
        messages = exc.messages if exc else ["Invalid request"]
        return jsonify({"message": "Validation error", "errors": messages}), 422

    # Create tables (for local/demo runs; in prod you'd use migrations)
    with app.app_context():
        db.create_all()

    # Register blueprints (endpoints)
    api.register_blueprint(AuthBlueprint)
    api.register_blueprint(ObservationsBlueprint)
    api.register_blueprint(TelemetryBlueprint)

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app


if __name__ == "__main__":
    app = create_app()
    # Dev server (debug on for hot reload + better tracebacks)
    app.run(host="0.0.0.0", port=5000, debug=True)
