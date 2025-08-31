from flask import Flask, jsonify
from flask_smorest import Api
from flask_jwt_extended import JWTManager
from config import Config
from db import db
from models import *
from auth import blp as AuthBlueprint
from observations import blp as ObservationsBlueprint
from telemetry import blp as TelemetryBlueprint

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    api = Api(app)

    jwt = JWTManager(app)

    @app.errorhandler(422)
    def handle_unprocessable(err):
        # marshmallow validation errors
        exc = getattr(err, "exc", None)
        messages = exc.messages if exc else ["Invalid request"]
        return jsonify({"message": "Validation error", "errors": messages}), 422

    with app.app_context():
        db.create_all()

    api.register_blueprint(AuthBlueprint)
    api.register_blueprint(ObservationsBlueprint)
    api.register_blueprint(TelemetryBlueprint)

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app

if __name__ == "__main__":
    app = create_app()
    # Flask built-in server for local runs (US-05)
    app.run(host="0.0.0.0", port=5000, debug=True)
