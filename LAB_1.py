import requests
from bs4 import BeautifulSoup

# url = "https://ultra.md/category/smartphones"

# test_url_sizeValidation
url = "https://ultra.md/category/fans-ventiliatory"
response = requests.get(url)

if response.status_code != 200:
    print(f"Failed to retrieve the main page, status code: {response.status_code}")
    exit()

soup = BeautifulSoup(response.text, 'html.parser')

all_links = soup.find_all('a', class_='product-text pt-4 font-semibold text-gray-900 transition duration-200 hover:text-red-500 dark:text-white sm:text-sm')
all_prices = soup.find_all('span', class_='text-blue text-xl font-bold dark:text-white')

for link, price in zip(all_links, all_prices):
    link_text = link.text.strip()
    link_href = link.get('href')

    product_response = requests.get(link_href)

    if product_response.status_code != 200:
        print(f"Failed to retrieve the product page for {link_text}, status code: {product_response.status_code}")
        continue

    product_soup = BeautifulSoup(product_response.text, 'html.parser')

    display_size = "N/A"
    table_rows = product_soup.find_all('tr')

    for row in table_rows:
        label_span = row.find('span', string="Diagonala ecranului")
        if label_span:
            td = row.find('td', class_='font-bold')
            if td:
                display_size = td.text.strip()
            break
    else:
        print(f"There is no Display size found for {link_text}")

    price_text = price.text.strip()
    price_int = ''.join(filter(str.isdigit, price_text))

    if not price_int:
        print(f"No valid price found for product: {link_text}")

    print(f"Product: {link_text}, URL: {link_href}, Price: {price_int} lei, Display Size: {display_size}")
