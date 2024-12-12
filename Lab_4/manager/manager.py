import pika
import json
import requests
import time
import logging
import signal
import sys
import threading
import os
from ftplib import FTP
from io import BytesIO

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# RabbitMQ configuration
RABBITMQ_HOST = 'rabbitmq'
QUEUE_NAME = 'scraped_data'

# Webserver configuration (LAB2 webserver for products)
WEBSERVER_URL = 'http://webserver:5000/products'

# LAB2 webserver endpoint for file uploads (multipart)
# Adjust if you have a different endpoint for file uploads.
WEBSERVER_FILE_UPLOAD_URL = 'http://webserver:5000/upload'  # Example endpoint

# FTP Server Configuration
FTP_HOST = os.getenv('FTP_HOST', 'ftp_server')
FTP_USER = os.getenv('FTP_USER', 'user')
FTP_PASS = os.getenv('FTP_PASS', 'password')
FTP_FILENAME = 'processed_data.json'  #
FTP_FETCH_INTERVAL = 30  # seconds

# Retry configuration for sending data to webserver
MAX_RETRIES = 5
RETRY_DELAY = 5  # seconds

stop_thread = False  # To gracefully stop threads


def connect_rabbitmq():
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST)
    )
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    return connection, channel


def upload_file_to_ftp(content: bytes):
    """
    Upload the given content to the FTP server as FTP_FILENAME.
    """
    try:
        ftp = FTP(FTP_HOST)
        ftp.login(FTP_USER, FTP_PASS)
        # Store content as a file in the FTP server
        bio = BytesIO(content)
        ftp.storbinary(f'STOR {FTP_FILENAME}', bio)
        ftp.quit()
        logger.info("Successfully uploaded file to FTP server.")
    except Exception as e:
        logger.error(f"Error uploading file to FTP: {e}")


def fetch_file_from_ftp():
    """
    Fetch the file from the FTP server and return its content as bytes.
    """
    try:
        ftp = FTP(FTP_HOST)
        ftp.login(FTP_USER, FTP_PASS)
        bio = BytesIO()
        ftp.retrbinary(f'RETR {FTP_FILENAME}', bio.write)
        ftp.quit()
        bio.seek(0)
        return bio.read()
    except Exception as e:
        logger.error(f"Error fetching file from FTP: {e}")
        return None


def send_file_to_webserver(file_content: bytes):
    """
    Send the fetched file as a multipart/form-data request to the LAB2 webserver.
    """
    files = {
        'file': (FTP_FILENAME, file_content, 'application/json')
    }
    try:
        response = requests.post(WEBSERVER_FILE_UPLOAD_URL, files=files, timeout=10)
        if response.status_code == 201:
            logger.info("File successfully sent to webserver.")
        else:
            logger.error(
                f"Failed to send file to webserver. Status Code: {response.status_code} Response: {response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending file to webserver: {e}")


def ftp_fetch_thread_func():
    """
    Thread function that periodically fetches a file from the FTP server and sends it to the webserver.
    """
    while not stop_thread:
        file_content = fetch_file_from_ftp()
        if file_content:
            send_file_to_webserver(file_content)
        time.sleep(FTP_FETCH_INTERVAL)


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

        # Attempt to send data to webserver
        attempt = 0
        while attempt < MAX_RETRIES:
            try:
                response = requests.post(WEBSERVER_URL, json=filtered_products, timeout=10)
                if response.status_code == 201:
                    logger.info("Data successfully sent to webserver.")

                    # Once data is successfully sent, write to file and upload to FTP
                    file_content = json.dumps(data, indent=2).encode('utf-8')
                    upload_file_to_ftp(file_content)

                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    break
                else:
                    logger.error(
                        f"Failed to send data to webserver. Status Code: {response.status_code} Response: {response.text}")
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
    global stop_thread
    logger.info("Received shutdown signal.")
    stop_thread = True
    sys.exit(0)


def main():
    # Handle graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start the FTP fetch thread
    thread = threading.Thread(target=ftp_fetch_thread_func, daemon=True)
    thread.start()

    connection, channel = connect_rabbitmq()
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)

    logger.info("Manager started consuming messages and FTP thread started.")
    try:
        channel.start_consuming()
    except Exception as e:
        logger.error(f"Manager encountered an error: {e}")
    finally:
        connection.close()
        stop_thread = True
        thread.join()


if __name__ == '__main__':
    main()
