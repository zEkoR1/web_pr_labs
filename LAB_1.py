import requests
from bs4 import BeautifulSoup


url = "https://ultra.md/ru/category/smartphones"
response = requests.get(url)
soup = BeautifulSoup(response.text, 'html.parser')
all_links = soup.find_all('a', class_= 'product-text pt-4 font-semibold text-gray-900 transition duration-200 hover:text-red-500 dark:text-white sm:text-sm')
all_prices = soup.find_all('span', class_= 'text-blue text-xl font-bold dark:text-white')

for link, price in zip(all_links, all_prices):
    link_text = link.text.strip()
    link_href = link.get('href')
    # print (link_href)
    product_response = requests.get(link_href)

    product_soup = BeautifulSoup(product_response.text, 'html.parser')

    memory = product_soup.find('span', class_='font-bold text-gray-800')
    price_text = price.text.strip()

    print(f"Link Text: {link_text}, URL: {link_href}, Price: {price_text} Memory: {memory}")



# print(soup.text)
# print (link_text, link_href)

