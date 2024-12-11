import pika
import json
import requests
import time
import logging
import signal
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# RabbitMQ configuration
RABBITMQ_HOST = 'rabbitmq'
QUEUE_NAME = 'scraped_data'

# Webserver configuration
WEBSERVER_URL = 'http://webserver:5000/products'

# Retry configuration
MAX_RETRIES = 5
RETRY_DELAY = 5  # seconds

def connect_rabbitmq():
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST)
    )
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    return connection, channel

def callback(ch, method, properties, body):
    try:
        data = json.loads(body)
        logger.info(f"Manager received data: {data}")

        # Extract 'filtered_products' from the data structure
        filtered_products = data.get('filtered_products', [])
        if not isinstance(filtered_products, list):
            logger.error("Invalid data format: 'filtered_products' should be a list.")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

        # Send the list of products to the webserver
        attempt = 0
        while attempt < MAX_RETRIES:
            try:
                response = requests.post(WEBSERVER_URL, json=filtered_products, timeout=10)
                if response.status_code == 201:
                    logger.info("Data successfully sent to webserver.")
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    break
                else:
                    logger.error(f"Failed to send data to webserver. Status Code: {response.status_code}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Error sending data to webserver: {e}")

            attempt += 1
            logger.info(f"Retrying in {RETRY_DELAY} seconds... (Attempt {attempt}/{MAX_RETRIES})")
            time.sleep(RETRY_DELAY)
        else:
            logger.error("Max retries reached. Message will be requeued.")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def signal_handler(sig, frame):
    logger.info("Received shutdown signal.")
    sys.exit(0)

def main():
    # Handle graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    connection, channel = connect_rabbitmq()
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)

    logger.info("Manager started consuming messages.")
    try:
        channel.start_consuming()
    except Exception as e:
        logger.error(f"Manager encountered an error: {e}")
    finally:
        connection.close()

if __name__ == '__main__':
    main()