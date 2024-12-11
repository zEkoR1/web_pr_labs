import requests
from bs4 import BeautifulSoup
from functools import reduce
from datetime import datetime
import pytz
from urllib.parse import urljoin
import pika
import json
import time
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversion rates
MDL_TO_EUR_RATE = 1 / 19.5
EUR_TO_MDL_RATE = 19.5

# Price range in EUR
MIN_PRICE_EUR = 500
MAX_PRICE_EUR = 1000

# Target website
PROTOCOL = "https://"
HOST = "ultra.md"
url = "/category/smartphones"

# RabbitMQ configuration
RABBITMQ_HOST = 'rabbitmq'  # Hostname as defined in docker-compose.yml
QUEUE_NAME = 'scraped_data'

# Retry configuration
MAX_RETRIES = 10
RETRY_DELAY = 5  # seconds


def fetch_http(full_url):
    """
    Fetches a web page using the requests library.
    """
    try:
        response = requests.get(full_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/58.0.3029.110 Safari/537.3"
        })
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching {full_url}: {e}")
        raise


def connect_rabbitmq():
    attempt = 0
    while attempt < MAX_RETRIES:
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RABBITMQ_HOST)
            )
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_NAME, durable=True)
            logger.info("Connected to RabbitMQ")
            return connection, channel
        except pika.exceptions.AMQPConnectionError as e:
            logger.error(f"Connection to RabbitMQ failed: {e}. Retrying in {RETRY_DELAY} seconds...")
            attempt += 1
            time.sleep(RETRY_DELAY)
    logger.critical("Failed to connect to RabbitMQ after multiple attempts.")
    sys.exit(1)


def publish_to_rabbitmq(channel, data):
    message = json.dumps(data)
    channel.basic_publish(
        exchange='',
        routing_key=QUEUE_NAME,
        body=message,
        properties=pika.BasicProperties(
            delivery_mode=2,  # Make message persistent
        )
    )
    logger.info(f"Scraper published data to RabbitMQ: {data}")


def scrape_and_publish():
    # Scraping logic as provided in the original task
    try:
        main_page_url = f"{PROTOCOL}{HOST}{url}"
        main_page_html = fetch_http(main_page_url)
    except Exception as e:
        logger.error(f"Error fetching main page: {e}")
        return None

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
            link_href = urljoin(f"{PROTOCOL}{HOST}", link_href)

        try:
            product_page_html = fetch_http(link_href)
        except Exception as e:
            logger.error(f"Error fetching product page {link_href}: {e}")
            continue

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

    logger.info(f"Scraped and filtered data: {final_data_structure}")
    return final_data_structure


def main():
    connection, channel = connect_rabbitmq()
    try:
        while True:
            data = scrape_and_publish()
            if data and data['filtered_products']:
                publish_to_rabbitmq(channel, data)
            else:
                logger.warning("No data scraped or all products filtered out. Skipping publish.")
            time.sleep(60)  # Scrape every 60 seconds
    except KeyboardInterrupt:
        logger.info("Scraper stopped by user.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        connection.close()
        logger.info("RabbitMQ connection closed.")


if __name__ == '__main__':
    main()
