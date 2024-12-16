import socket
import os
import time
import json
import threading
import signal
import struct

SERVER_PORT = 65432
CHUNK_SIZE = 64 * 1024 
TIMEOUT = 2
FORMAT = 'utf8'
INPUT_FILE = 'UDP/input.txt'
OUTPUT_FOLDER = 'UDP/downloads'

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

files = {}
download_status = {}
stop_flag = False
lock = threading.Lock()

def calculate_checksum(data):
    return sum(data) % 2**32

def connect_to_server(server_host):
    max_retries = 4
    for attempt in range(max_retries):
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            print(f"Connected to server at {server_host}:{SERVER_PORT}")
            client_socket.sendto(b"LIST", (server_host, SERVER_PORT))
            return client_socket
        except Exception as e:
            print(f"Attempt {attempt + 1}/{max_retries}: Error connecting to server: {e}")
            if attempt < max_retries - 1:
                print("Retrying in 5 seconds...")
                time.sleep(5)
    print("Failed to connect after multiple attempts. Please check the server address and your internet connection.")
    return None

def get_file_list(client_socket, server_host):
    try:
        # client_socket.sendto(b"LIST", (server_host, SERVER_PORT))
        data, _ = client_socket.recvfrom(4096)
        global files
        files = json.loads(data.decode(FORMAT))
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
    global stop_flag
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

            try:
                request = struct.pack("!256sII", filename.encode(FORMAT), bytes_received, chunk_size)
                client_socket.sendto(request, (server_host, SERVER_PORT))
            except socket.error as e:
                print(f"Error sending request to server: {e}")
                break

            chunk = b""
            while len(chunk) < chunk_size:
                try:
                    # request = struct.pack("!256sII", filename.encode(FORMAT), bytes_received, chunk_size)
                    # client_socket.sendto(request, (server_host, SERVER_PORT))
                    # client_socket.settimeout(TIMEOUT)
                    packet, _ = client_socket.recvfrom(1024)
                    if len(packet) < 8:
                        print(f"Error: Received packet too short.")
                        break

                    sequence_number, checksum = struct.unpack("!II", packet[:8])
                    chunk_data = packet[8:]
                    chunk += chunk_data
                    # if checksum != calculate_checksum(chunk_data):
                    #     print(f"Checksum mismatch for chunk {sequence_number}. Retrying...")
                    #     continue
                    ack = struct.pack("!I", sequence_number)
                    client_socket.sendto(ack, (server_host, SERVER_PORT))
                    print(f"Chunk {sequence_number} received successfully.")

                except Exception as e:
                    print(f"Error receiving chunk: {e}")
                    break
            
            if not chunk:
                print(f"Error downloading {filename}")
                break
            file.write(chunk)
            bytes_received += len(chunk)
            
            progress = int(bytes_received / file_size * 100)
            with lock:
                download_status[filename] = progress
    with lock:
        download_status[filename] = 100
    print(f"Download completed: {filename}")
    client_socket.close()

def display_progress():
    while not stop_flag:
        # os.system('cls' if os.name == 'nt' else 'clear')
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
    exit(0)

def start_client():
    global stop_flag
    
    signal.signal(signal.SIGINT, signal_handler)
    
    server_host = input("INPUT SERVER_IP: ").strip()
    
    initial_client_socket = connect_to_server(server_host)
    
    if not initial_client_socket:
        print("Failed to connect to server. Exiting...")
        return
    
    get_file_list(initial_client_socket, server_host)
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