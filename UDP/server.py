import socket
import os
import struct
import threading
import signal
import sys
import json
import time
import psutil

PORT = 65432
SERVER_FILES = 'server_files'
CHUNK_SIZE = 60 * 1024
TIMEOUT = 2 
FORMAT = 'utf-8'
FILE_LIST = 'files.txt'
lock = threading.Lock()
stop_flag = False
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

os.makedirs(SERVER_FILES, exist_ok=True)

files = {}

def get_wireless_ip():
    wireless_ip = None
    for interface, addrs in psutil.net_if_addrs().items():
        if "Wi-Fi" in interface or "Wireless" in interface or "wlan" in interface:
            for addr in addrs:
                if addr.family == socket.AF_INET:  # IPv4
                    wireless_ip = addr.address
                    break
    return wireless_ip

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

def send_file_list(server_socket, client_address):
    try:
        data = json.dumps(files).encode(FORMAT)
        server_socket.sendto(data, client_address)
    except Exception as e:
        print(f"Error sending file list: {e}")

def calculate_checksum(data):
    return sum(data) % (2**32)

def send_file_chunk(server_socket, client_address, filename, chunk_index):
    file_path = os.path.join(SERVER_FILES, filename)
    try:
        with open(file_path, 'rb') as file:
            file.seek(chunk_index)
            data = file.read(CHUNK_SIZE)
            sequence_number = chunk_index // CHUNK_SIZE
            checksum = calculate_checksum(data)
            packet = struct.pack("!II", sequence_number, checksum) + data
            while not stop_flag:
                server_socket.sendto(packet, client_address)
                # print(f"Sent chunk {sequence_number} to {client_address}")
                try:
                    server_socket.settimeout(TIMEOUT)
                    ack, _ = server_socket.recvfrom(8)
                    ack_number, = struct.unpack("!I", ack)
                    if ack_number == sequence_number:
                        # print(f"ACK received for chunk {sequence_number}")
                        break
                except socket.timeout:
                    print(f"Timeout! Resending chunk {sequence_number}")
                    continue
    except FileNotFoundError:
        print(f"File not found: {filename}")
        server_socket.sendto(b"ERROR: File not found", client_address)
    except Exception as e:
        print(f"Error sending file chunk: {e}")

def signal_handler(sig, frame):
    global stop_flag
    stop_flag = True
    print("\nShutting down server...")
    server_socket.close()
    sys.exit(0)

def start_server():
    # server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # SERVER_HOST = socket.gethostname()
    # SERVER_IP = socket.gethostbyname(SERVER_HOST) or '127.0.0.1'
    SERVER_IP = get_wireless_ip() or '127.0.0.1'
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    load_file_list()

    # print(f"Server hostname: {SERVER_HOST}")
    print(f"Server IP address: {SERVER_IP}")
    print(f"Server port: {PORT}")

    server_socket.bind(('', PORT))
    print(f"Server is ready for connecting on {SERVER_IP}:{PORT}")
    
    while not stop_flag:
        try:
            # server_socket.settimeout(10)
            request, client_address = server_socket.recvfrom(1024)
            header = request[:4].decode(FORMAT)
            if header == 'LIST':
                send_file_list(server_socket, client_address)
                print(f"Sent file list to {client_address}")
            elif header == 'REQF':
                while not stop_flag:
                    try:
                        request, _ = server_socket.recvfrom(1024)
                        filename, chunk_index = struct.unpack("!256sI", request[4:])
                        filename = filename.decode(FORMAT).strip('\x00')
                        # print(f"Client requested file: {filename}, chunk_index: {chunk_index}")
                        if filename not in files:
                            error_msg = f"ERROR: File {filename} not found"
                            server_socket.sendto(error_msg.encode(FORMAT), client_address)
                            continue
                        send_file_chunk(server_socket, client_address, filename, chunk_index)
                        if chunk_index > 0:
                            percentage = min((chunk_index) / int(files[filename]) * 100, 100)
                            print(f"Sent {filename} ... {percentage:.1f}%", end = '\r')

                        if chunk_index + CHUNK_SIZE >= files[filename]:
                            print(f"Sent {filename} ... 100 %", end = '\r')
                            print(f"\nFile sent: {filename}")
                            print("_______________________________")
                            break
                        # time.sleep(0.05)
                    except Exception as e:
                        print(f"Error handling client {client_address}: {e}")
                        break
        except Exception as e:
            print(f"Server error: {e}")

if __name__ == "__main__":
    start_server()
