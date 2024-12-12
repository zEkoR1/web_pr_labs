from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
import logging
import json
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# DATABASE_URI = 'sqlite:///products.db'

DATABASE_URI = os.getenv('DATABASE_URI', 'postgresql://postgres:password@db:5432/products_db')
app_http = Flask(__name__)
app_http.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
app_http.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app_http)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    url = db.Column(db.String(200), nullable=False)
    price_mdl = db.Column(db.Float, nullable=False)
    display_size = db.Column(db.String(50), nullable=False)
    price_eur = db.Column(db.Float, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'url': self.url,
            'price_mdl': self.price_mdl,
            'display_size': self.display_size,
            'price_eur': self.price_eur
        }


with app_http.app_context():
    db.create_all()


@app_http.route('/products', methods=['POST'])
def create_products():
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    products_data = data if isinstance(data, list) else [data]
    required_fields = ['name', 'url', 'price_mdl', 'display_size', 'price_eur']
    added_products, errors = [], []

    for idx, product_data in enumerate(products_data, start=1):
        missing = [field for field in required_fields if field not in product_data]
        if missing:
            errors.append({
                "product_index": idx,
                "error": f"Missing fields: {', '.join(missing)}"
            })
            continue

        product = Product(
            name=product_data['name'],
            url=product_data['url'],
            price_mdl=product_data['price_mdl'],
            display_size=product_data['display_size'],
            price_eur=product_data['price_eur']
        )

        db.session.add(product)
        added_products.append(product)

    if not added_products and errors:
        return jsonify({"errors": errors}), 400

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        errors.append({
            "error": "Product with this name already exists."
        })
        return jsonify({"errors": errors}), 400

    response = {
        "message": f"{len(added_products)} products added successfully.",
        "added_products": [product.to_dict() for product in added_products]
    }

    if errors:
        response["errors"] = errors

    return jsonify(response), 201


@app_http.route('/products', methods=['GET'])
def get_products():
    try:
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 10))
    except ValueError:
        return jsonify({"error": "Offset and limit must be integers"}), 400

    products = Product.query.offset(offset).limit(limit).all()
    return jsonify([product.to_dict() for product in products]), 200


@app_http.route('/product', methods=['GET'])
def get_product():
    product_id = request.args.get('id')
    name = request.args.get('name')

    if not product_id and not name:
        return jsonify({"error": "Please provide 'id' or 'name' as query parameter"}), 400

    product = Product.query.get(product_id) if product_id else Product.query.filter_by(name=name).first()

    if not product:
        return jsonify({"error": "Product not found"}), 404

    return jsonify(product.to_dict()), 200


@app_http.route('/product', methods=['PUT'])
def update_product():
    product_id = request.args.get('id')
    name = request.args.get('name')

    if not product_id and not name:
        return jsonify({"error": "Please provide 'id' or 'name' as query parameter"}), 400

    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    product = Product.query.get(product_id) if product_id else Product.query.filter_by(name=name).first()

    if not product:
        return jsonify({"error": "Product not found"}), 404

    for key in ['name', 'url', 'price_mdl', 'display_size', 'price_eur']:
        if key in data:
            setattr(product, key, data[key])

    try:
        db.session.commit()
        return jsonify(product.to_dict()), 200
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Product with this name already exists"}), 400


@app_http.route('/product', methods=['DELETE'])
def delete_product():
    product_id = request.args.get('id')
    name = request.args.get('name')

    if not product_id and not name:
        return jsonify({"error": "Please provide 'id' or 'name' as query parameter"}), 400

    product = Product.query.get(product_id) if product_id else Product.query.filter_by(name=name).first()

    if not product:
        return jsonify({"error": "Product not found"}), 404

    db.session.delete(product)
    db.session.commit()
    return jsonify({"message": "Product deleted successfully"}), 200

@app_http.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files['file']
    # Process the file as needed
    # Return a success response
    return jsonify({"message": "File uploaded"}), 201


if __name__ == '__main__':
    app_http.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)