import socket
import os
import threading
import time

# Cấu hình server
HOST = '127.0.0.1'
PORT = 8000

# Đọc danh sách các file từ input.txt
def load_files_to_download():
    files_to_download = []
    with open("input.txt", "r") as f:
        for line in f:
            files_to_download.append(line.strip())
    return files_to_download

def download_chunk(file_name, offset, length, client_socket):
    request = f"GET {file_name} {offset} {length}"
    client_socket.send(request.encode())
    data = client_socket.recv(length)
    return data

def download_file(file_name, server_address):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(server_address)
    client_socket.recv(1024)

    file_size = 1024 * 1024 * 5
    num_chunks = 4
    chunk_size = file_size

    chunks = []
    threads = []

    for i in range(num_chunks):
        offset = i * chunk_size
        length = chunk_size if i < num_chunks - 1 else file_size - offset
        thread = threading.Thread(target=download_chunk, args=(file_name, offset, length, client_socket))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    with open(file_name, "wb") as f:
        for chunk in chunks:
            f.write(chunk)
    
    client_socket.close()

def start_client(server_address):
    while True:
        files_to_download = load_files_to_download()
        for file_name in files_to_download:
            download_file(file_name, server_address)
            print(f"Download of {file_name} completed!")
        time.sleep(5)  # Kiểm tra lại sau mỗi 5s

if __name__ == "__main__":
    server_address = (HOST, PORT)  # Địa chỉ server
    start_client(server_address)