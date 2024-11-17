import socket
import os
import threading
import schedule
import time
import sys
import tkinter as tk
from datetime import datetime
from tkinter import messagebox
from tkinter import ttk
from tkinter import *
from tkinter.ttk import *
import tkinter.scrolledtext as tkscrolled
from PIL import ImageTk, Image  # Install Pillow

# Cấu hình server
HOST = '127.0.0.1'
PORT = 8000
FILE_LIST = "files.txt"
FORMAT = 'utf8'
FILES_DIRECTORY = "./server_files"

# s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# s.bind((socket.gethostname(), PORT))
# s.listen()
# HOST = s.getsockname()[0]

def exit(page):
    sys.exit()

def receive_account_password(conn):
    acc = conn.recv(1024).decode(FORMAT)
    psw = conn.revc(1024).decode(FORMAT)
    return acc, psw

def load_file_list():
    file = {}
    with open("files.txt", "r") as f:
        for line in f:
            name, size = line.strip().split()
            file[name] = int(size.replace("MB", "").replace("GB", "")) * 1024 * 1024
    return file

def handle_client(client_socket, files):
    try:
        client_socket.send(str(files).encode(FORMAT))
        while True:
            request = client_socket.recv(1024).decode(FORMAT)
            if not request:
                break
            if request.startswith('GET'):
                file_name, offset, length = request[4:].split()
                offset = int(offset)
                length = int(length)

                if file_name in files:
                    file_size = files[file_name]
                    if offset < file_size:
                        with open(file_name, "rb") as file:
                            file.seek(offset)
                            data = file.read(length)
                            client_socket.send(data)
                    else:
                        client_socket.send(b"Invalid offset")
                else:
                    client_socket.send(b"File not found")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client_socket.close()

def start_server():
    files = load_file_list()
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f"Server listening on {HOST}:{PORT}")

    while True:
        client_socket, addr = server_socket.accept()
        print(f"Accepted connection from {addr}")
        client_thread = threading.Thread(target=handle_client, args=(client_socket, files))
        client_thread.start()

if __name__ == "__main__":
    start_server()