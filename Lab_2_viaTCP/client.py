# tcp_client.py

import socket
import json

HOST = '127.0.0.1'  # The server's hostname or IP address
PORT = 65432  # The port used by the server


def send_request(request):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        s.sendall(json.dumps(request).encode('utf-8'))
        data = s.recv(4096)
    response = json.loads(data.decode('utf-8'))
    return response


if __name__ == "__main__":
    create_request = {
        "action": "create",
        "data": {
            "name": "Product A",
            "url": "http://example.com/product-a",
            "price_mdl": 100.0,
            "display_size": "1920x10",
            "price_eur": 85.0
        }
    }
    print("Creating Product:", create_request)
    response = send_request(create_request)
    print("Response:", response)

    # Example: Read all products
    read_request = {
        "action": "read",
        "data": {
            "offset": 0,
            "limit": 10
        }
    }
    print("\nReading Products:", read_request)
    response = send_request(read_request)
    print("Response:", response)

    # Example: Update a product
    update_request = {
        "action": "update",
        "data": {
            "name": "Product A",
            "price_eur": 90.0
        }
    }
    print("\nUpdating Product:", update_request)
    response = send_request(update_request)
    print("Response:", response)

    # Example: Delete a product
    delete_request = {
        "action": "delete",
        "data": {
            "name": "Product A"
        }
    }
    print("\nDeleting Product:", delete_request)
    response = send_request(delete_request)
    print("Response:", response)
