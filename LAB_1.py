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

# Function to create and send a raw HTTP request over TCP socket, with redirect handling and HTTPS support
def fetch_http(host, port, url, use_https=False, max_redirects=5):
    if max_redirects == 0:
        raise Exception("Too many redirects")

    if use_https:
        port = 443  # HTTPS port

    # Construct the HTTP request
    request = (
        f"GET {url} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3\r\n"
        "Connection: close\r\n\r\n"
    )

    # Create a TCP socket
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

    # Decode the response and separate headers from the body
    response_text = response.decode('utf-8', errors='replace')
    headers, body = response_text.split('\r\n\r\n', 1)

    # Check for redirection (301 or 302 status codes)
    if "301 Moved Permanently" in headers or "302 Found" in headers:
        for line in headers.split('\r\n'):
            if line.startswith("Location:"):
                new_location = line.split("Location: ")[1].strip()
                # print(f"Redirected to: {new_location}")
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

# Fetch the main page
main_page_html = fetch_http(HOST, PORT, url)

# Use BeautifulSoup to parse the response body
soup = BeautifulSoup(main_page_html, 'html.parser')

all_links = soup.find_all('a',
                          class_='product-text pt-4 font-semibold text-gray-900 transition duration-200 hover:text-red-500 dark:text-white sm:text-sm')
all_prices = soup.find_all('span', class_='text-blue text-xl font-bold dark:text-white')

products = []

for link, price in zip(all_links, all_prices):
    link_text = link.text.strip()
    link_href = link.get('href')

    if not link_text or len(link_text) < 5:
        print(f"Invalid product name for URL: {link_href}")
        continue

    # Ensure the link is absolute
    if not link_href.startswith('http'):
        link_href = f"http://{HOST}{link_href}"

    # Fetch the individual product page using the socket method
    product_page_html = fetch_http(HOST, PORT, link_href, use_https=True)

    # Use BeautifulSoup to parse the individual product page
    product_soup = BeautifulSoup(product_page_html, 'html.parser')

    # Extract product details like display size and price
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

    # Debug: Print raw HTML if something seems wrong
    if display_size == "N/A" or not display_size.endswith('"'):
        print(f"Invalid display size for product: {link_text}")
        print(f"Page content: {product_page_html[:500]}")  # Print first 500 characters of the HTML
        continue

    price_text = price.text.strip()
    price_int = ''.join(filter(str.isdigit, price_text))

    if not price_int.isdigit():
        print(f"Invalid price for product: {link_text}")
        continue

    # Add parsed product to the list
    products.append({
        'name': link_text,
        'url': link_href,
        'price_mdl': int(price_int),
        'display_size': display_size
    })

# Debug: Print products before filtering
for product in products:
    print(f"Product: {product['name']}, Price (MDL): {product['price_mdl']}, Display Size: {product['display_size']}")

# Convert MDL to EUR
def convert_to_eur(product):
    return {
        **product,
        'price_eur': round(product['price_mdl'] * MDL_TO_EUR_RATE, 2)
    }

mapped_products = list(map(convert_to_eur, products))

# Filter products by price range
def filter_by_price_range(product):
    return MIN_PRICE_EUR <= product['price_eur'] <= MAX_PRICE_EUR

filtered_products = list(filter(filter_by_price_range, mapped_products))

# Calculate the total sum in EUR
total_sum_eur = reduce(lambda total, product: total + product['price_eur'], filtered_products, 0)

# Final data structure
final_data_structure = {
    'filtered_products': filtered_products,
    'total_sum_eur': round(total_sum_eur, 2),
    'timestamp_utc': datetime.now(pytz.UTC).isoformat()
}

print(final_data_structure)
