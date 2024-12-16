import socket
import os
import time
import json
import threading
import signal

SERVER_PORT = 65432
CHUNK_SIZE = 512 * 1024 
FORMAT = 'utf8'
INPUT_FILE = 'TCP/input.txt'
OUTPUT_FOLDER = 'TCP/downloads'

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

files = {}
download_status = {}
stop_flag = False
lock = threading.Lock()

def connect_to_server(server_host):
    max_retries = 4
    for attempt in range(max_retries):
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
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

def get_file_list(client_socket):
    try:
        data = client_socket.recv(4096).decode(FORMAT)
        global files
        files = json.loads(data)
        print("Available files:")
        for filename, size in files.items():
            print(f"{filename}: {size / (1024 * 1024)} MB")
    except Exception as e:
        print(f"Error getting file list: {e}")

def check_input_file(server_host):
    last_motified = 0
    while not stop_flag:
        try:
            mtime = os.path.getmtime(INPUT_FILE)
            if mtime - last_motified >= 5:
                last_motified = mtime
                with open(INPUT_FILE, "r") as file:
                    lines = file.readlines()
                with lock:
                    for filename in lines:
                        filename = filename.strip()
                        if filename in files and filename not in download_status:
                            download_status[filename] = 0
                            threading.Thread(target=download_file, args=(server_host, filename)).start()

        except FileNotFoundError:
            pass
        time.sleep(1)

def download_file(server_host, filename):
    client_socket = connect_to_server(server_host)
    if not client_socket:
        print(f"Failed to connect to server for downloading {filename}")
        return
    
    file_size = int(files[filename])
    
    with open(os.path.join(OUTPUT_FOLDER, filename), "wb") as file:
        bytes_received = 0
        while bytes_received < file_size and not stop_flag:
            remaining = file_size - bytes_received
            chunk_size = min(CHUNK_SIZE, remaining)
            request = f"{filename}  {bytes_received} {chunk_size}"
            try:
                client_socket.sendall(request.encode(FORMAT))
            except socket.error as e:
                print(f"Error sending request to server: {e}")
                break

            chunk = b""
            while len(chunk) < chunk_size:
                try:
                    part = client_socket.recv(chunk_size - len(chunk))
                    if not part:
                        print("Connection lost while downloading.")
                        break
                    chunk += part
                except socket.error as e:
                    print(f"Error receiving data: {e}")
                    break

            if not chunk:
                print(f"Error downloading {filename}")
                break
            
            file.write(chunk)
            bytes_received += len(chunk)
            
            progress = int(bytes_received / file_size * 100)
            with lock:
                download_status[filename] = progress
            # time.sleep(0.1)
    with lock:
        download_status[filename] = 100
    print(f"Download completed: {filename}")
    client_socket.close()

def display_progress():
    while not stop_flag:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("Available file: ")
        print("__________________")
        for filename, size in files.items():
            print(f"{filename}: {size / (1024 * 1024):.2f} MB")
        print("__________________")
        print("\nDownload Status: ")
        with lock:
            for filename, progress in download_status.items():
                if progress < 100:
                    print(f"Downloading {filename} .... {progress}%")
                else:
                    print(f"Downloaded {filename}")

        time.sleep(1)

def signal_handler(signum, frame):
    global stop_flag
    stop_flag = True
    print("\nClosing client...")

def start_client():
    global stop_flag
    
    signal.signal(signal.SIGINT, signal_handler)
    
    server_host = input("INPUT SERVER_IP: ").strip()
    
    initial_client_socket = connect_to_server(server_host)
    
    if not initial_client_socket:
        print("Failed to connect to server. Exiting...")
        return

    get_file_list(initial_client_socket)
    initial_client_socket.close()
    
    input_thread = threading.Thread(target=check_input_file, args=(server_host,))
    input_thread.start()
    
    progress_thread = threading.Thread(target=display_progress)
    progress_thread.start()
    
    try:
        while not stop_flag:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        stop_flag = True
        input_thread.join()
        progress_thread.join()

if __name__ == "__main__":
    start_client()