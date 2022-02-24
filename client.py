#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""
About: Simple client using the service.
"""
import socket
import time

SERVICE_IP = "10.0.0.3"
SERVICE_PORT = 9999

if __name__ == "__main__":
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(10)
    data = b"Show me the counter, please!"
    time.sleep(10)
    while True:
        try:
            print("Sending message to server\n")
            sock.sendto(data, (SERVICE_IP, SERVICE_PORT))
            counter, _ = sock.recvfrom(SERVICE_PORT)
            print("Current counter: {}\n".format(counter.decode("utf-8")))
            time.sleep(1)
        except socket.timeout:
            print("\n!Socket Timeout\n\n")