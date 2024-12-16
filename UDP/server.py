import socket
import os
import json
import threading
import signal
import struct

# Cấu hình server
PORT = 65432
TIMEOUT = 2  # 2 seconds
FILE_LIST = 'files.txt'
FORMAT = 'utf8'
SERVER_FILES = 'server_files'
CHUNK_SIZE = 64 * 1024 
lock = threading.Lock()
stop_flag = False

os.makedirs(SERVER_FILES, exist_ok=True)

files = {}
    
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
    return sum(data) % 2**32

def send_file_chunk(server_socket, client_address, file_path, chunk_index, chunk_size):
    print(f"Client requested chunk starting at {chunk_index} for {file_path}")
    global stop_flag
    try:
        with open(file_path, 'rb') as file:
            file.seek(chunk_index)
            data = file.read(chunk_size)
        
            sequence_number = chunk_index + chunk_size
            checksum = calculate_checksum(data)
            packet = struct.pack("!II", sequence_number, checksum) + data
            while not stop_flag:
                try:
                    server_socket.sendto(packet, client_address)
                    server_socket.settimeout(TIMEOUT)
                    ack, _ = server_socket.recvfrom(1024)
                    ack_number, = struct.unpack("!I", ack)
                    if ack_number == sequence_number:
                        print(f"Chunk {sequence_number} acknowledged by client.")
                        break
                    else:
                        print(f"Invalid ACK received: {ack_number}. Expected: {sequence_number}.")
                except socket.timeout:
                    print(f"Timeout! Resending chunk {sequence_number}.")
                    continue
        return len(data)
    except Exception as e:
        print(f"Error sending file chunk: {e}")
        server_socket.sendto(f"Error: {str(e)}".encode(FORMAT), client_address)
        return 0
        
def handle_client(server_socket, address):
    global stop_flag
    print(f"CONNECTED BY CLIENT ON {address}")
    send_file_list(server_socket, address)
    server_socket.settimeout(60)  # Timeout 60 giây
    while not stop_flag:
        try:
            request, client_address = server_socket.recvfrom(1024)
            if len(request) < struct.calcsize("!256sII"):
                server_socket.sendto(b"ERROR: Invalid request format", client_address)
                continue

            file_name, start_index, chunk_size = struct.unpack("!256sII", request)
            file_name = file_name.decode(FORMAT).strip('\x00')
            start_index = int(start_index)
            chunk_size = min(int(chunk_size), CHUNK_SIZE)
            
            if file_name not in files:
                server_socket.sendto(b"Invalid file", client_address)
                continue

            file_path = os.path.join(SERVER_FILES, file_name)
            if not os.path.exists(file_path):
                print(f"File not found: {file_name}")
                server_socket.sendto(b"ERROR: File not found", client_address)
                continue
            
            print(f"Client requested chunk starting at {start_index} for {file_name}")
            bytes_sent = send_file_chunk(server_socket, client_address, file_path, start_index, chunk_size)

            print(f"Sending {file_name}")
            total_size = os.path.getsize(os.path.join(SERVER_FILES, file_name))

            with lock:
                if bytes_sent > 0:
                    percentage = min((start_index + bytes_sent) / total_size * 100, 100)
                    print(f"Sent {file_name} ... {percentage:.1f}%", end = '\r')

                if start_index + bytes_sent >= total_size:
                    print(f"\nFile sent: {file_name}")
                    print("_______________________________")
                    break
        except socket.timeout:
            print(f"Connection with {address} timed out")
            break
        except Exception as e:
            print(f"Error handling request from {address}: {e}")
            break
    print(f"Client disconnected")
    server_socket.close()

def signal_handler(sig, frame):
    global stop_flag
    stop_flag = True
    print("\nShutting down server...")
    exit(0)

def start_server():
    global stop_flag
    SERVER_HOST = socket.gethostname()
    try:
        SERVER_IP = socket.gethostbyname(SERVER_HOST)
    except socket.gaierror:
        SERVER_IP = '127.0.0.1'

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
        
    load_file_list()

    print(f"Server hostname: {SERVER_HOST}")
    print(f"Server IP address: {SERVER_IP}")
    print(f"Server port: {PORT}")

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
        server_socket.settimeout(1)
        server_socket.bind((SERVER_IP, PORT))
        print(f"Server {SERVER_HOST} is ready for connecting on {SERVER_IP}:{PORT}")

        while not stop_flag:
            try:
                request, client_address = server_socket.recvfrom(1024)
                # print(f"Received {request.decode(FORMAT)} from {client_address}")
                client_thread = threading.Thread(target=handle_client, args=(server_socket, client_address))
                client_thread.start()

            except socket.timeout:
                continue
            except Exception as e:
                print(f"Error receiving data: {e}")

if __name__ == "__main__":
    start_server()