from flask import Flask, request, jsonify
from flask_restful import Api, Resource
from flask_sqlalchemy import SQLAlchemy
from marshmallow import Schema, fields, ValidationError
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite3"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = "super-secret-key"

db = SQLAlchemy(app)
api = Api(app)

product_tags = db.Table(
    "product_tags",
    db.Column("product_id", db.Integer, db.ForeignKey("products.id"), primary_key=True),
    db.Column("tag_id",     db.Integer, db.ForeignKey("tags.id"),     primary_key=True),
)

class User(db.Model):
    __tablename__ = "users"
    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)

class Product(db.Model):
    __tablename__ = "products"
    id      = db.Column(db.Integer, primary_key=True)
    title   = db.Column(db.String(80), unique=True, nullable=False)
    cost    = db.Column(db.Float, nullable=False)
    shop_id = db.Column(db.Integer, db.ForeignKey("shops.id"), nullable=False)
    shop    = db.relationship("Shop", back_populates="products")
    tags    = db.relationship(
        "Tag",
        secondary=product_tags,
        back_populates="products",
        lazy="dynamic"
    )

class Shop(db.Model):
    __tablename__ = "shops"
    id       = db.Column(db.Integer, primary_key=True)
    title    = db.Column(db.String(80), unique=True, nullable=False)
    products = db.relationship("Product", back_populates="shop", lazy="dynamic")

class Tag(db.Model):
    __tablename__ = "tags"
    id       = db.Column(db.Integer, primary_key=True)
    name     = db.Column(db.String(50), unique=True, nullable=False)
    products = db.relationship(
        "Product",
        secondary=product_tags,
        back_populates="tags",
        lazy="dynamic"
    )

class UserSchema(Schema):
    username = fields.Str(required=True)
    password = fields.Str(required=True, load_only=True)

class ShopSummarySchema(Schema):
    id    = fields.Int(dump_only=True)
    title = fields.Str(required=True)

class TagSchema(Schema):
    id   = fields.Int(dump_only=True)
    name = fields.Str(required=True)

class ProductSchema(Schema):
    id      = fields.Int(dump_only=True)
    title   = fields.Str(required=True)
    cost    = fields.Float(required=True)
    shop_id = fields.Int(load_only=True, required=True)
    tag_ids = fields.List(fields.Int(), load_only=True)
    shop    = fields.Nested(ShopSummarySchema, dump_only=True)
    tags    = fields.List(fields.Nested(TagSchema), dump_only=True)

class ShopSchema(ShopSummarySchema):
    products = fields.List(fields.Nested(ProductSchema), dump_only=True)

user_schema     = UserSchema()
product_schema  = ProductSchema()
products_schema = ProductSchema(many=True)
shop_schema     = ShopSchema()
shops_schema    = ShopSchema(many=True)
tag_schema      = TagSchema()
tags_schema     = TagSchema(many=True)

jwt = JWTManager(app)

@jwt.unauthorized_loader
def missing_token(error):
    return jsonify({"error": "Authorization header missing"}), 401

class RegisterResource(Resource):
    def post(self):
        json_data = request.get_json() or {}
        try:
            data = user_schema.load(json_data)
        except ValidationError as err:
            return err.messages, 400

        if User.query.filter_by(username=data["username"]).first():
            return {"message": "Username already exists"}, 409

        new_user = User(
            username=data["username"],
            password=generate_password_hash(data["password"])
        )
        db.session.add(new_user)
        db.session.commit()
        return {"message": "User registered"}, 201

class LoginResource(Resource):
    def post(self):
        json_data = request.get_json() or {}
        try:
            data = user_schema.load(json_data)
        except ValidationError as err:
            return err.messages, 400

        user = User.query.filter_by(username=data["username"]).first()
        if not user or not check_password_hash(user.password, data["password"]):
            return {"message": "Invalid credentials"}, 401

        access_token = create_access_token(identity=user.id)
        return {"access_token": access_token}, 200

class ProtectedResource(Resource):
    method_decorators = [jwt_required()]

class ProductResource(ProtectedResource):
    def get(self, title):
        prod = Product.query.filter_by(title=title).first()
        if not prod:
            return {"message": "Product not found"}, 404
        return product_schema.dump(prod), 200

    def delete(self, title):
        prod = Product.query.filter_by(title=title).first()
        if prod:
            db.session.delete(prod)
            db.session.commit()
        return {"message": "Product deleted"}, 200

class ProductListResource(ProtectedResource):
    def get(self):
        return products_schema.dump(Product.query.all()), 200

    def post(self):
        json_data = request.get_json() or {}
        try:
            data = product_schema.load(json_data)
        except ValidationError as err:
            return err.messages, 400

        if Product.query.filter_by(title=data["title"]).first():
            return {"message": "Product already exists"}, 400

        tag_ids = data.pop("tag_ids", [])
        new_prod = Product(**data)
        for tid in tag_ids:
            tag = Tag.query.get(tid)
            if tag:
                new_prod.tags.append(tag)

        db.session.add(new_prod)
        db.session.commit()
        return product_schema.dump(new_prod), 201

class ShopResource(ProtectedResource):
    def get(self, title):
        shop = Shop.query.filter_by(title=title).first()
        if not shop:
            return {"message": "Shop not found"}, 404
        return shop_schema.dump(shop), 200

    def delete(self, title):
        shop = Shop.query.filter_by(title=title).first()
        if shop:
            db.session.delete(shop)
            db.session.commit()
        return {"message": "Shop deleted"}, 200

class ShopListResource(ProtectedResource):
    def get(self):
        return shops_schema.dump(Shop.query.all()), 200

    def post(self):
        json_data = request.get_json() or {}
        try:
            data = shop_schema.load(json_data)
        except ValidationError as err:
            return err.messages, 400

        if Shop.query.filter_by(title=data["title"]).first():
            return {"message": "Shop already exists"}, 400

        new_shop = Shop(**data)
        db.session.add(new_shop)
        db.session.commit()
        return shop_schema.dump(new_shop), 201

class TagResource(ProtectedResource):
    def get(self, name):
        tag = Tag.query.filter_by(name=name).first()
        if not tag:
            return {"message": "Tag not found"}, 404
        return tag_schema.dump(tag), 200

    def delete(self, name):
        tag = Tag.query.filter_by(name=name).first()
        if tag:
            db.session.delete(tag)
            db.session.commit()
        return {"message": "Tag deleted"}, 200

class TagListResource(ProtectedResource):
    def get(self):
        return tags_schema.dump(Tag.query.all()), 200

    def post(self):
        json_data = request.get_json() or {}
        try:
            data = tag_schema.load(json_data)
        except ValidationError as err:
            return err.messages, 400

        if Tag.query.filter_by(name=data["name"]).first():
            return {"message": "Tag already exists"}, 400

        new_tag = Tag(**data)
        db.session.add(new_tag)
        db.session.commit()
        return tag_schema.dump(new_tag), 201

class ProductTagLinkResource(ProtectedResource):
    def post(self, title, tag_id):
        prod = Product.query.filter_by(title=title).first_or_404()
        tag  = Tag.query.get_or_404(tag_id)
        if not prod.tags.filter_by(id=tag_id).first():
            prod.tags.append(tag)
            db.session.commit()
        return {"message": "Tag linked to product"}, 200

    def delete(self, title, tag_id):
        prod = Product.query.filter_by(title=title).first_or_404()
        tag  = Tag.query.get_or_404(tag_id)
        if prod.tags.filter_by(id=tag_id).first():
            prod.tags.remove(tag)
            db.session.commit()
        return {"message": "Tag unlinked from product"}, 200

api.add_resource(RegisterResource,      "/register")
api.add_resource(LoginResource,         "/login")
api.add_resource(ProductResource,       "/product/<string:title>")
api.add_resource(ProductListResource,   "/products")
api.add_resource(ShopResource,          "/shop/<string:title>")
api.add_resource(ShopListResource,      "/shops")
api.add_resource(TagResource,           "/tag/<string:name>")
api.add_resource(TagListResource,       "/tags")
api.add_resource(ProductTagLinkResource,"/product/<string:title>/tags/<int:tag_id>")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
    