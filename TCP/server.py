import socket
import os
import json
import threading
import signal
import psutil

# Cấu hình server
PORT = 65432
FILE_LIST = 'files.txt'
FORMAT = 'utf8'
SERVER_FILES = 'server_files'
CHUNK_SIZE = 1024 * 1024 
lock = threading.Lock()
stop_flag = True

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

def send_file_list(client_socket):
    try:
        data = json.dumps(files).encode()
        client_socket.sendall(data)
    except Exception as e:
        print(f"Error sending file list: {e}")

def send_file_chunk(client_socket, filename, chunk_index, chunk_size):
    file_path = os.path.join(SERVER_FILES, filename)
    try:
        with open(file_path, 'rb') as file:
            file.seek(chunk_index)
            data = file.read(chunk_size)
            if not data:
                return 0
            client_socket.sendall(data)
        return len(data)
    except FileNotFoundError:
        print(f"File not found: {filename}")
        client_socket.sendall(b"File not found")
        return 0
    except socket.error as e:
        print(f"Socket error while sending file: {e}")
        client_socket.sendall(f"Error: {str(e)}".encode(FORMAT))
        return 0
    except Exception as e:
        print(f"Error sending file chunk: {e}")
        client_socket.sendall(f"Error: {str(e)}".encode(FORMAT))
        return 0
        
def handle_client(client_socket, address):
    global stop_flag
    print(f"CONNECTED BY CLIENT ON {address}")
    # send_file_list(client_socket)
    client_socket.settimeout(60)
    while stop_flag:
        try:
            request = client_socket.recv(1024).decode(FORMAT)
            if not request:
                break

            parts = request.split()
            if len(parts) != 3:
                client_socket.sendall(b"Invalid request format !")
                continue

            file_name, chunk_index, chunk_size = parts
            chunk_index = int(chunk_index)
            chunk_size = min(int(chunk_size), CHUNK_SIZE)

            if file_name == 'DISCONNECT':
                break
            if file_name not in files:
                client_socket.sendall(b"Invalid file")
                continue

            print(f"Sending {file_name}")
            total_size = os.path.getsize(os.path.join(SERVER_FILES, file_name))
            bytes_sent = send_file_chunk(client_socket, file_name, chunk_index, chunk_size)

            with lock:
                if bytes_sent > 0:
                    percentage = min((chunk_index + bytes_sent) / total_size * 100, 100)
                    print(f"Sent {file_name} ... {percentage:.1f}%", end = '\r')

                if chunk_index + bytes_sent >= total_size:
                    print(f"\nFile sent: {file_name}")
                    print("_______________________________")
                    break
        except socket.timeout:
            print(f"Connection with {address} timed out")
        except Exception as e:
            print(f"Error handling request from {address}: {e}")
            break

    print(f"Client disconnected")
    client_socket.close()

def signal_handler(sig, frame):
    global stop_flag
    print("\nShutting down server...")
    stop_flag = False
    exit(0)

def start_server():
    global stop_flag
    SERVER_IP = get_wireless_ip() or '127.0.0.1'

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
        
    load_file_list()

    print(f"Server IP address: {SERVER_IP}")
    print(f"Server port: {PORT}")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.settimeout(1)
        server_socket.bind((SERVER_IP, PORT))
        server_socket.listen()
        print(f"Server is ready for connecting on {SERVER_IP}:{PORT}")
        # send_file_list(server_socket)
        sentFileList = True
        while stop_flag:
            try:
                client_socket, addr = server_socket.accept()
                if sentFileList:
                    send_file_list(client_socket)
                    sentFileList = False
                client_thread = threading.Thread(target=handle_client, args=(client_socket, addr))
                client_thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Error accepting connection: {e}")


if __name__ == "__main__":
    start_server()