from flask import Blueprint
from flask_smorest import Blueprint as SmorestBlueprint, abort
from werkzeug.security import generate_password_hash, check_password_hash
from flask import request
from db import db
from models import User
from schemas import UserSchema, UserRegisterSchema, UserLoginSchema
from flask_jwt_extended import create_access_token, jwt_required, get_jwt
from utils import require_roles

blp = SmorestBlueprint("Auth", "auth", url_prefix="/auth", description="Authentication endpoints")

@blp.route("/register", methods=["POST"])
@require_roles("admin")
@blp.arguments(UserRegisterSchema)
@blp.response(201, UserSchema)
def register(body):
    if User.query.filter_by(email=body["email"]).first():
        abort(409, message="User already exists")
    user = User(
        email=body["email"],
        password_hash=generate_password_hash(body["password"]),
        role=body["role"],
        tier=body["tier"],
        buoy_id=body.get("buoy_id"),
    )
    db.session.add(user)
    db.session.commit()
    return user

@blp.route("/login", methods=["POST"])
@blp.doc(security=[]) 
@blp.arguments(UserLoginSchema)
def login(body):
    user = User.query.filter_by(email=body["email"]).first()
    if not user or not check_password_hash(user.password_hash, body["password"]):
        abort(401, message="Invalid credentials")
    claims = {"role": user.role, "tier": user.tier, "user_id": user.id, "buoy_id": user.buoy_id}
    token = create_access_token(identity=str(user.id), additional_claims=claims)
    return {"access_token": token}

@blp.route("/me", methods=["GET"])
@jwt_required()
@blp.response(200, UserSchema)
def me():
    jwt = get_jwt()
    user = User.query.get(jwt.get("user_id"))
    return user
