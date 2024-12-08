import socket
import ssl
from bs4 import BeautifulSoup
from functools import reduce
from datetime import datetime
import pytz
from urllib.parse import urljoin, urlparse


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
    # AF-NET указывает что используется IPv$4
    #sockStream показывается что используется потоковый сокет который обеспечивает надеждую передачу данных
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if use_https:
            context = ssl.create_default_context()
            s = context.wrap_socket(s, server_hostname=host)
        s.connect((host, port))
        s.sendall(request.encode('utf-8'))

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
                parsed_url = urlparse(new_location)
                new_host = parsed_url.netloc if parsed_url.netloc else host
                new_url = parsed_url.path if parsed_url.path else url
                use_https = parsed_url.scheme == 'https'
                return fetch_http(new_host, 443 if use_https else 80, new_url, use_https=use_https, max_redirects=max_redirects-1)

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
        link_href = urljoin(f"http://{HOST}", link_href)

    product_page_html = fetch_http(HOST, 443, link_href, use_https=True)
    product_soup = BeautifulSoup(product_page_html, 'html.parser')

    display_size = "N/A"
    summary_section = product_soup.find('div', class_='mt-[18px] lg:mt-6 mb-2 lg:mb-16')
    if summary_section:
        list_items = summary_section.find_all('li')
        for li in list_items:
            if "Rezolutia ecranului" in li.text:
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
        if product:
            json_string += '{'
            json_string += f'"name": "{product.get("name", "N/A")}", '
            json_string += f'"url": "{product.get("url", "N/A")}", '
            json_string += f'"price_mdl": {product.get("price_mdl", 0)}, '
            json_string += f'"display_size": "{product.get("display_size", "N/A")}", '
            json_string += f'"price_eur": {product.get("price_eur", 0.0)}'
            json_string += '},'
    if len(data['filtered_products']) > 0:
        json_string = json_string.rstrip(',')
    json_string += '],'
    json_string += f'"total_sum_eur": {data.get("total_sum_eur", 0.0)}, '
    json_string += f'"timestamp_utc": "{data.get("timestamp_utc", "N/A")}"'
    json_string += "}"
    return json_string


def serialize_to_xml(data):
    xml_string = "<data>"
    xml_string += "<filtered_products>"
    for product in data['filtered_products']:
        if product:
            xml_string += "<product>"
            xml_string += f'<name>{product.get("name", "N/A")}</name>'
            xml_string += f'<url>{product.get("url", "N/A")}</url>'
            xml_string += f'<price_mdl>{product.get("price_mdl", 0)}</price_mdl>'
            xml_string += f'<display_size>{product.get("display_size", "N/A")}</display_size>'
            xml_string += f'<price_eur>{product.get("price_eur", 0.0)}</price_eur>'
            xml_string += "</product>"
    xml_string += "</filtered_products>"
    xml_string += f'<total_sum_eur>{data.get("total_sum_eur", 0.0)}</total_sum_eur>'
    xml_string += f'<timestamp_utc>{data.get("timestamp_utc", "N/A")}</timestamp_utc>'
    xml_string += "</data>"
    return xml_string


def custom_serialize(data):
    if isinstance(data, dict):
        serialized = "Dict{"
        for key, value in data.items():
            serialized += f'Key-> {custom_serialize(key)}; Value-> {custom_serialize(value)}; '
        serialized = serialized.rstrip("; ") + "}"
        return serialized
    elif isinstance(data, list):
        serialized = "List["
        for item in data:
            serialized += f'{custom_serialize(item)}; '
        serialized = serialized.rstrip("; ") + "]"
        return serialized
    elif isinstance(data, (int, float, str)):
        return f"{type(data).__name__}({repr(data)})"
    else:
        return f"Unknown({repr(data)})"




def deserialize_custom(serialized):
    if serialized.startswith("Dict{"):
        data = {}
        serialized = serialized[5:-1]
        items = split_items(serialized, "; ")
        i = 0
        while i < len(items) - 1:
            if items[i].startswith("Key-> ") and items[i + 1].startswith("Value-> "):
                key = deserialize_custom(items[i].split("Key-> ", 1)[1])
                value = deserialize_custom(items[i + 1].split("Value-> ", 1)[1])
                data[key] = value
                i += 2
            else:
                i += 1
        return data
    elif serialized.startswith("List["):
        data = []
        serialized = serialized[5:-1]
        items = split_items(serialized, "; ")
        for item in items:
            if item:
                data.append(deserialize_custom(item))
        return data
    else:
        if serialized.startswith("int("):
            return int(serialized[4:-1])
        elif serialized.startswith("float("):
            return float(serialized[6:-1])
        elif serialized.startswith("str("):
            return serialized[4:-1]
        elif serialized.startswith("Unknown("):
            return serialized[8:-1]
        else:
            raise ValueError(f"Unknown type in serialized data: {serialized}")


def split_items(serialized, delimiter):
    items = []
    current = ""
    bracket_level = 0

    for char in serialized:
        if char == '{' or char == '[':
            bracket_level += 1
        elif char == '}' or char == ']':
            bracket_level -= 1

        if char == delimiter[0] and bracket_level == 0:
            items.append(current.strip())
            current = ""
        else:
            current += char

    if current:
        items.append(current.strip())

    return items




print (final_data_structure)
print("Custom Serialized Format:")
custom_serialized = custom_serialize(final_data_structure)
print(custom_serialized)

print("\nDeserialized Custom Format:")
deserialized_custom = deserialize_custom(custom_serialized)
print(deserialized_custom)

print("\nJSON Format:")
print(serialize_to_json(final_data_structure))

print("\nXML Format:")
print(serialize_to_xml(final_data_structure))
