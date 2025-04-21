from flask import Flask, request
from flask_restful import Api, Resource
from flask_sqlalchemy import SQLAlchemy
from marshmallow import Schema, fields, ValidationError

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite3"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
api = Api(app)


class Product(db.Model):
    __tablename__ = "products"
    id      = db.Column(db.Integer, primary_key=True)
    title   = db.Column(db.String(80), unique=True, nullable=False)
    cost    = db.Column(db.Float, nullable=False)
    shop_id = db.Column(db.Integer, db.ForeignKey("shops.id"), nullable=False)
    shop    = db.relationship("Shop", back_populates="products")


class Shop(db.Model):
    __tablename__ = "shops"
    id       = db.Column(db.Integer, primary_key=True)
    title    = db.Column(db.String(80), unique=True, nullable=False)
    products = db.relationship("Product", back_populates="shop", lazy="dynamic")


class ShopSummarySchema(Schema):
    id    = fields.Int(dump_only=True)
    title = fields.Str(required=True)


class ProductSchema(Schema):
    id      = fields.Int(dump_only=True)
    title   = fields.Str(required=True)
    cost    = fields.Float(required=True)
    shop_id = fields.Int(load_only=True, required=True)
    shop    = fields.Nested(ShopSummarySchema, dump_only=True)


class ShopSchema(ShopSummarySchema):
    products = fields.List(fields.Nested(ProductSchema), dump_only=True)


product_schema = ProductSchema()
products_schema = ProductSchema(many=True)
shop_schema    = ShopSchema()
shops_schema   = ShopSchema(many=True)


class ProductResource(Resource):
    def get(self, title):
        prod = Product.query.filter_by(title=title).first()
        if not prod:
            return {"message": "Product not found"}, 404
        return product_schema.dump(prod)

    def delete(self, title):
        prod = Product.query.filter_by(title=title).first()
        if prod:
            db.session.delete(prod)
            db.session.commit()
        return {"message": "Product deleted"}


class ProductListResource(Resource):
    def get(self):
        all_prods = Product.query.all()
        return products_schema.dump(all_prods)

    def post(self):
        json_data = request.get_json()
        try:
            data = product_schema.load(json_data)
        except ValidationError as err:
            return err.messages, 400

        if Product.query.filter_by(title=data["title"]).first():
            return {"message": "Product already exists"}, 400

        new_prod = Product(**data)
        db.session.add(new_prod)
        db.session.commit()
        return product_schema.dump(new_prod), 201


class ShopResource(Resource):
    def get(self, title):
        shop = Shop.query.filter_by(title=title).first()
        if not shop:
            return {"message": "Shop not found"}, 404
        return shop_schema.dump(shop)

    def delete(self, title):
        shop = Shop.query.filter_by(title=title).first()
        if shop:
            db.session.delete(shop)
            db.session.commit()
        return {"message": "Shop deleted"}


class ShopListResource(Resource):
    def get(self):
        all_shops = Shop.query.all()
        return shops_schema.dump(all_shops)

    def post(self):
        json_data = request.get_json()
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



api.add_resource(ProductResource,     "/product/<string:title>")
api.add_resource(ProductListResource, "/products")
api.add_resource(ShopResource,        "/shop/<string:title>")
api.add_resource(ShopListResource,    "/shops")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
