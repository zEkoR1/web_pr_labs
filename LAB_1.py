import requests
from bs4 import BeautifulSoup
from functools import reduce
from datetime import datetime
import pytz

MDL_TO_EUR_RATE = 1 / 19.5
EUR_TO_MDL_RATE = 19.5

MIN_PRICE_EUR = 500
MAX_PRICE_EUR = 1000

url = "https://ultra.md/category/smartphones"

response = requests.get(url)

if response.status_code != 200:
    print(f"Failed to retrieve the main page, status code: {response.status_code}")
    exit()

soup = BeautifulSoup(response.text, 'html.parser')

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

    product_response = requests.get(link_href)

    if product_response.status_code != 200:
        print(f"Failed to retrieve the product page for {link_text}, status code: {product_response.status_code}")
        continue

    product_soup = BeautifulSoup(product_response.text, 'html.parser')

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

    if display_size == "N/A" or not display_size.endswith('"'):
        print(f"Invalid display size for product: {link_text}")
        continue

    price_text = price.text.strip()
    price_int = ''.join(filter(str.isdigit, price_text))

    if not price_int.isdigit():
        print(f"Invalid price for product: {link_text}")
        continue

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

print(final_data_structure)
