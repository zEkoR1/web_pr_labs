import socket
import ssl
from bs4 import BeautifulSoup
from functools import reduce
from datetime import datetime
import pytz

MDL_TO_EUR_RATE = 1 / 19.5
EUR_TO_MDL_RATE = 19.5

MIN_PRICE_EUR = 500
MAX_PRICE_EUR = 1000

HOST = "ultra.md"
PORT = 80
url = "/category/smartphones"


def fetch_http(host, port, url, use_https=False, max_redirects=5):
    if max_redirects == 0:
        raise Exception("Too many redirects")

    if use_https:
        port = 443

    request = (
        f"GET {url} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3\r\n"
        "Connection: close\r\n\r\n"
    )

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if use_https:
            context = ssl.create_default_context()
            s = context.wrap_socket(s, server_hostname=host)
        s.connect((host, port))
        s.sendall(request.encode('utf-8'))

        # Receive the response in chunks
        response = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            response += chunk

    response_text = response.decode('utf-8', errors='replace')
    headers, body = response_text.split('\r\n\r\n', 1)

    if "301 Moved Permanently" in headers or "302 Found" in headers:
        for line in headers.split('\r\n'):
            if line.startswith("Location:"):
                new_location = line.split("Location: ")[1].strip()
                # Handle relative redirects
                if new_location.startswith('/'):
                    new_location = f"http://{host}{new_location}"
                # If redirected to HTTPS, switch to HTTPS
                if new_location.startswith('https://'):
                    new_host = new_location.split('//')[1].split('/')[0]
                    new_url = '/' + '/'.join(new_location.split('//')[1].split('/')[1:])
                    return fetch_http(new_host, 443, new_url, use_https=True, max_redirects=max_redirects-1)
                # If redirected to HTTP, keep using HTTP
                elif new_location.startswith('http://'):
                    new_host = new_location.split('//')[1].split('/')[0]
                    new_url = '/' + '/'.join(new_location.split('//')[1].split('/')[1:])
                    return fetch_http(new_host, 80, new_url, use_https=False, max_redirects=max_redirects-1)

    return body

main_page_html = fetch_http(HOST, PORT, url)

soup = BeautifulSoup(main_page_html, 'html.parser')

all_links = soup.find_all('a', class_='product-text pt-4 font-semibold text-gray-900 transition duration-200 hover:text-red-500 dark:text-white sm:text-sm')
all_prices = soup.find_all('span', class_='text-blue text-xl font-bold dark:text-white')

products = []

for link, price in zip(all_links, all_prices):
    link_text = link.text.strip()
    link_href = link.get('href')

    if not link_text or len(link_text) < 5:
        continue

    if not link_href.startswith('http'):
        link_href = f"http://{HOST}{link_href}"

    product_page_html = fetch_http(HOST, PORT, link_href, use_https=True)
    product_soup = BeautifulSoup(product_page_html, 'html.parser')

    display_size = "N/A"
    summary_section = product_soup.find('div', class_='mt-[18px] lg:mt-6 mb-2 lg:mb-16')
    if summary_section:
        list_items = summary_section.find_all('li')
        for li in list_items:
            if "Diagonala ecranului" in li.text:
                display_size_span = li.find_next('span', class_='font-bold text-black')
                if display_size_span:
                    display_size = display_size_span.text.strip()
                break

    price_text = price.text.strip()
    price_int = ''.join(filter(str.isdigit, price_text))

    if price_int.isdigit():
        products.append({
            'name': link_text,
            'url': link_href,
            'price_mdl': int(price_int),
            'display_size': display_size
        })

def convert_to_eur(product):
    return {
        **product,
        'price_eur': round(product['price_mdl'] * MDL_TO_EUR_RATE, 2)
    }

mapped_products = list(map(convert_to_eur, products))

def filter_by_price_range(product):
    return MIN_PRICE_EUR <= product['price_eur'] <= MAX_PRICE_EUR

filtered_products = list(filter(filter_by_price_range, mapped_products))

total_sum_eur = reduce(lambda total, product: total + product['price_eur'], filtered_products, 0)

final_data_structure = {
    'filtered_products': filtered_products,
    'total_sum_eur': round(total_sum_eur, 2),
    'timestamp_utc': datetime.now(pytz.UTC).isoformat()
}


def serialize_to_json(data):
    json_string = "{"
    json_string += f'"filtered_products": ['
    for product in data['filtered_products']:
        json_string += '{'
        json_string += f'"name": "{product["name"]}", '
        json_string += f'"url": "{product["url"]}", '
        json_string += f'"price_mdl": {product["price_mdl"]}, '
        json_string += f'"display_size": "{product["display_size"]}", '
        json_string += f'"price_eur": {product["price_eur"]}'
        json_string += '},'
    if len(data['filtered_products']) > 0:
        json_string = json_string[:-1]
    json_string += '],'
    json_string += f'"total_sum_eur": {data["total_sum_eur"]}, '
    json_string += f'"timestamp_utc": "{data["timestamp_utc"]}"'
    json_string += "}"
    return json_string


def serialize_to_xml(data):
    xml_string = "<data>"
    xml_string += "<filtered_products>"
    for product in data['filtered_products']:
        xml_string += "<product>"
        xml_string += f'<name>{product["name"]}</name>'
        xml_string += f'<url>{product["url"]}</url>'
        xml_string += f'<price_mdl>{product["price_mdl"]}</price_mdl>'
        xml_string += f'<display_size>{product["display_size"]}</display_size>'
        xml_string += f'<price_eur>{product["price_eur"]}</price_eur>'
        xml_string += "</product>"
    xml_string += "</filtered_products>"
    xml_string += f'<total_sum_eur>{data["total_sum_eur"]}</total_sum_eur>'
    xml_string += f'<timestamp_utc>{data["timestamp_utc"]}</timestamp_utc>'
    xml_string += "</data>"
    return xml_string
def custom_serialize(data):
    if isinstance(data, dict):
        serialized = "D:{"
        for key, value in data.items():
            serialized += f'k:{custom_serialize(key)}:v:{custom_serialize(value)}; '
        serialized = serialized.rstrip("; ") + "}"
        return serialized
    elif isinstance(data, list):
        serialized = "L:["
        for item in data:
            serialized += f'{custom_serialize(item)}; '
        serialized = serialized.rstrip("; ") + "]"
        return serialized
    elif isinstance(data, int):
        return f"int({data})"
    elif isinstance(data, str):
        return f"str({data})"
    else:
        return str(data)

# Example usage
# Pass the final scraped data to custom_serialize
print("Custom Serialized Format:")
print(custom_serialize(final_data_structure))


# Print the manually constructed JSON and XML
print("JSON Format:")
print(serialize_to_json(final_data_structure))

print("\nXML Format:")
print(serialize_to_xml(final_data_structure))
