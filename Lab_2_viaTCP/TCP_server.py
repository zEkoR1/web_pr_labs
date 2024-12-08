
import socket
import threading
import json
from models import Product, Session
import sqlalchemy.exc

HOST = '127.0.0.1'  # Localhost
PORT = 65432  # Arbitrary non-privileged port


def handle_client(conn, addr):
    print(f"Connected by {addr}")
    session = Session()
    try:
        with conn:
            while True:
                data = conn.recv(4096)
                if not data:
                    break
                try:
                    request = json.loads(data.decode('utf-8'))
                    response = process_request(request, session)
                except json.JSONDecodeError:
                    response = {"status": "error", "message": "Invalid JSON format."}
                except Exception as e:
                    response = {"status": "error", "message": str(e)}
                # Send response
                response_bytes = json.dumps(response).encode('utf-8')
                conn.sendall(response_bytes)
    finally:
        session.close()
    print(f"Disconnected by {addr}")


def process_request(request, session):
    action = request.get('action')
    data = request.get('data', {})

    if action == 'create':
        return create_product(data, session)
    elif action == 'read':
        return read_products(data, session)
    elif action == 'update':
        return update_product(data, session)
    elif action == 'delete':
        return delete_product(data, session)
    else:
        return {"status": "error", "message": "Unknown action."}


def create_product(data, session):
    required_fields = ['name', 'url', 'price_mdl', 'display_size', 'price_eur']
    missing = [field for field in required_fields if field not in data]
    if missing:
        return {"status": "error", "message": f"Missing fields: {', '.join(missing)}"}

    product = Product(
        name=data['name'],
        url=data['url'],
        price_mdl=data['price_mdl'],
        display_size=data['display_size'],
        price_eur=data['price_eur']
    )
    session.add(product)
    try:
        session.commit()
        return {
            "status": "success",
            "message": "Product created successfully.",
            "data": product.to_dict()
        }
    except sqlalchemy.exc.IntegrityError:
        session.rollback()
        return {"status": "error", "message": "Product with this name already exists."}


def read_products(data, session):
    # Supports reading all or a specific product by id or name
    product_id = data.get('id')
    name = data.get('name')

    if product_id:
        product = session.query(Product).get(product_id)
        if product:
            return {"status": "success", "data": product.to_dict()}
        else:
            return {"status": "error", "message": "Product not found."}
    elif name:
        product = session.query(Product).filter_by(name=name).first()
        if product:
            return {"status": "success", "data": product.to_dict()}
        else:
            return {"status": "error", "message": "Product not found."}
    else:
        # Return all products with optional pagination
        offset = data.get('offset', 0)
        limit = data.get('limit', 10)
        try:
            offset = int(offset)
            limit = int(limit)
        except ValueError:
            return {"status": "error", "message": "Offset and limit must be integers."}

        products = session.query(Product).offset(offset).limit(limit).all()
        return {"status": "success", "data": [p.to_dict() for p in products]}


def update_product(data, session):
    # Identify product by id or name
    identifier = {}
    if 'id' in data:
        identifier['id'] = data['id']
    elif 'name' in data:
        identifier['name'] = data['name']
    else:
        return {"status": "error", "message": "Please provide 'id' or 'name' to update."}

    product = None
    if 'id' in identifier:
        product = session.query(Product).get(identifier['id'])
    else:
        product = session.query(Product).filter_by(name=identifier['name']).first()

    if not product:
        return {"status": "error", "message": "Product not found."}

    # Update fields
    updatable_fields = ['name', 'url', 'price_mdl', 'display_size', 'price_eur']
    for field in updatable_fields:
        if field in data:
            setattr(product, field, data[field])

    try:
        session.commit()
        return {
            "status": "success",
            "message": "Product updated successfully.",
            "data": product.to_dict()
        }
    except sqlalchemy.exc.IntegrityError:
        session.rollback()
        return {"status": "error", "message": "Product with this name already exists."}


def delete_product(data, session):
    # Identify product by id or name
    identifier = {}
    if 'id' in data:
        identifier['id'] = data['id']
    elif 'name' in data:
        identifier['name'] = data['name']
    else:
        return {"status": "error", "message": "Please provide 'id' or 'name' to delete."}

    product = None
    if 'id' in identifier:
        product = session.query(Product).get(identifier['id'])
    else:
        product = session.query(Product).filter_by(name=identifier['name']).first()

    if not product:
        return {"status": "error", "message": "Product not found."}

    session.delete(product)
    session.commit()
    return {"status": "success", "message": "Product deleted successfully."}


def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"TCP Server listening on {HOST}:{PORT}")
        while True:
            conn, addr = s.accept()
            client_thread = threading.Thread(target=handle_client, args=(conn, addr))
            client_thread.start()


if __name__ == "__main__":
    start_server()
