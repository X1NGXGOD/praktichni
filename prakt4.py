from flask import Flask
from flask_smorest import Api, Blueprint, abort
from flask.views import MethodView
from flask_sqlalchemy import SQLAlchemy
from marshmallow import Schema, fields

app = Flask(__name__)
app.config["PROPAGATE_EXCEPTIONS"] = True
app.config["API_TITLE"] = "Stores REST API"
app.config["API_VERSION"] = "v1"
app.config["OPENAPI_VERSION"] = "3.0.3"
app.config["OPENAPI_URL_PREFIX"] = "/"
app.config["OPENAPI_SWAGGER_UI_PATH"] = "/swagger-ui"
app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///data.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
api = Api(app)

class StoreModel(db.Model):
    __tablename__ = "stores"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    items = db.relationship("ItemModel", back_populates="store", lazy="dynamic")

class ItemModel(db.Model):
    __tablename__ = "items"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    price = db.Column(db.Float(precision=2), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False)
    store = db.relationship("StoreModel", back_populates="items")

class PlainItemSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)
    price = fields.Float(required=True)

class PlainStoreSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)

class ItemSchema(PlainItemSchema):
    store_id = fields.Int(required=True, load_only=True)
    store = fields.Nested(PlainStoreSchema(), dump_only=True)

class StoreSchema(PlainStoreSchema):
    items = fields.List(fields.Nested(PlainItemSchema()), dump_only=True)

store_blp = Blueprint("Stores", "stores", description="Операції з магазинами")
item_blp  = Blueprint("Items",  "items",  description="Операції з товарами")

@store_blp.route("/store/<int:store_id>")
class StoreResource(MethodView):
    @store_blp.response(200, StoreSchema)
    def get(self, store_id):
        return StoreModel.query.get_or_404(store_id)

    def delete(self, store_id):
        store = StoreModel.query.get_or_404(store_id)
        db.session.delete(store)
        db.session.commit()
        return {"message": "Store deleted"}, 200

@store_blp.route("/store")
class StoreListResource(MethodView):
    @store_blp.arguments(StoreSchema)
    @store_blp.response(201, StoreSchema)
    def post(self, store_data):
        if StoreModel.query.filter_by(name=store_data["name"]).first():
            abort(400, message="Store with that name already exists.")
        store = StoreModel(**store_data)
        db.session.add(store)
        db.session.commit()
        return store

    @store_blp.response(200, StoreSchema(many=True))
    def get(self):
        return StoreModel.query.all()

@item_blp.route("/item/<int:item_id>")
class ItemResource(MethodView):
    @item_blp.response(200, ItemSchema)
    def get(self, item_id):
        return ItemModel.query.get_or_404(item_id)

    def delete(self, item_id):
        item = ItemModel.query.get_or_404(item_id)
        db.session.delete(item)
        db.session.commit()
        return {"message": "Item deleted"}, 200

    @item_blp.arguments(ItemSchema)
    @item_blp.response(200, ItemSchema)
    def put(self, item_data, item_id):
        item = ItemModel.query.get_or_404(item_id)
        item.name = item_data.get("name", item.name)
        item.price = item_data.get("price", item.price)
        db.session.commit()
        return item

@item_blp.route("/item")
class ItemListResource(MethodView):
    @item_blp.arguments(ItemSchema)
    @item_blp.response(201, ItemSchema)
    def post(self, item_data):
        if not StoreModel.query.get(item_data["store_id"]):
            abort(400, message="Store not found.")
        item = ItemModel(**item_data)
        db.session.add(item)
        db.session.commit()
        return item

    @item_blp.response(200, PlainItemSchema(many=True))
    def get(self):
        return ItemModel.query.all()

api.register_blueprint(store_blp)
api.register_blueprint(item_blp)

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
