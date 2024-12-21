import socket
import os
import struct
import signal
import time
import threading

SERVER_PORT = 65432
CHUNK_SIZE = 60 * 1024
FORMAT = 'utf-8'
OUTPUT_FOLDER = 'UDP/downloads'
INPUT_FILE = 'UDP/input.txt'
FILE_LIST = 'files.txt'
TIMEOUT = 2
last_display_time = 0

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

files = {}
download_status = {}
stop_flag = False
lock = threading.Lock()
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def calculate_checksum(data):
    return sum(data) % (2**32)

def load_file_list():
    global files
    with open(FILE_LIST, "r") as f:
        for line in f:
            name, size = line.strip().split()
            if size.endswith("GB"):
                size_in_bytes = int(size.replace("GB", "")) * 1024 * 1024 * 1024
            elif size.endswith("MB"):
                size_in_bytes = int(size.replace("MB", "")) * 1024 * 1024
            else:
                size_in_bytes = int(size)
            files[name] = size_in_bytes

def display_progress():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("Available file: ")
    print("__________________")
    for filename, size in files.items():
        print(f"{filename}: {size / (1024 * 1024):.2f} MB")
    print("__________________")
    print("\nDownload Status: ")
    for filename, progress in download_status.items():
        if progress < 100:
            print(f"Downloading {filename} .... {progress}%")
        else:
            print(f"Downloaded {filename}")

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
                        if filename not in download_status:
                            download_status[filename] = 0
                            download_file(server_host, filename)
        except FileNotFoundError:
            pass
        time.sleep(1)

def download_file(server_ip, filename):
    client_socket.sendto(b'LIST', (server_ip, SERVER_PORT))
    bytes_received = 0
    chunk_index = 0

    file_path = os.path.join('server_files', filename)
    file_size = os.path.getsize(os.path.join(file_path))
    # file_size = int(files[filename])
    with open(os.path.join(OUTPUT_FOLDER, filename), 'wb') as file:
        while not stop_flag:
            request = b'REQF' + struct.pack("!256sI", filename.encode(FORMAT), bytes_received)
            client_socket.sendto(request, (server_ip, SERVER_PORT))

            try:
                packet, _ = client_socket.recvfrom(CHUNK_SIZE + 8)
                sequence_number, checksum = struct.unpack("!II", packet[:8])
                data = packet[8:]
                
                if checksum != calculate_checksum(data):
                    print(f"Checksum mismatch for chunk {sequence_number}. Retrying...")
                    continue
                
                if sequence_number == chunk_index:
                    file.write(data)
                    bytes_received += len(data)
                    # print(f"Received chunk {sequence_number}, size: {len(data)} bytes")
                    chunk_index += 1

                    progress = int(bytes_received / file_size * 100)
                    download_status[filename] = progress

                    global last_display_time
                    current_time = time.time()
                    if current_time - last_display_time >= 0.5:
                        last_display_time = current_time
                        display_progress()

                ack = struct.pack("!I", sequence_number)
                client_socket.sendto(ack, (server_ip, SERVER_PORT))

                if len(data) < CHUNK_SIZE:
                    print(f"Download {filename} complete!")
                    download_status[filename] = 100
                    display_progress()
                    break
            except Exception as e:
                print(f"Error downloading file: {e}")
                break

def signal_handler(signum, frame):
    global stop_flag
    stop_flag = True
    print("\nClosing client...")
    client_socket.close()
    exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    server_ip = input("INPUT SERVER_IP: ").strip()
    load_file_list()
    check_input_file(server_ip)
