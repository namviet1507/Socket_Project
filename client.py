import socket
import json
import os
import time
import re
import threading
import signal

SERVER_PORT = 65432
CHUNK_SIZE = 1024 * 1024 
INPUT_FILE = 'input.txt'
OUTPUT_FOLDER = './downloads'

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

file_list = {}
download_queue = []
download_status = {}
stop_flag = False
lock = threading.Lock()

def connect_to_server(server_host):
    max_retries = 5
    for attempt in range(max_retries):
        try:
            client_socket =  client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((server_host, SERVER_PORT))
            print(f"Connected to server at {server_host}")
            return client_socket
        except Exception as e:
            print(f"Attempt {attempt + 1}/{max_retries}: Error connecting to server: {e}")
            if attempt < max_retries - 1:
                print("Retrying in 5 seconds...")
                time.sleep(5)
    print("Failed to connect after multiple attempts. Please check the server address and your internet connection.")
    return None
