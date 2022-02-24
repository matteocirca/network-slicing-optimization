#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""
About: Simple server for counting.
"""

import os
import argparse
import socket
import time
import threading

#Service infos
SERVICE_IP = "10.0.0.3"
SERVICE_PORT = 9999

#Threaded function listening for host packets and responding (simulated service)
def listen_host(counter_init):
    global end_thread
    global counter
    print("Get the init counter state: {}".format(counter_init))
    counter = counter_init

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((SERVICE_IP, SERVICE_PORT))

    while not end_thread:
        # Block here waiting for data input
        _, addr = sock.recvfrom(SERVICE_PORT)
        counter += 1
        print("Increased counter, new value is {}\n".format(counter))
        sock.sendto(str(counter).encode("utf-8"), addr)
        time.sleep(0.5)

def run(ip, wait=False):
    global end_thread
    global counter
    end_thread = False
    counter = 0
    sockController = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sockController.bind((ip, 6633))
    counter_init = 0
    while True:
        if wait:
            #Server not active, waiting for server to send migrate command
            data, _ = sockController.recvfrom(6633)
            counter_init = int(data.decode("utf-8"))
            print("Starting new instance of server, counter state is {}".format(counter_init))
            wait = False
            end_thread = False
        else:
            #Server is active, listening for client packets
            print("Initializing thread...\n")
            thread = threading.Thread(target=listen_host, args=((counter_init, )))
            thread.start()
            data, _ = sockController.recvfrom(6633)
            
            print("Received migrate signal from controller, closing thread...\n")
            end_thread = True
            thread.join()
            sockController.sendto(str(counter).encode("utf-8"), ("172.17.0.1", 6633))
            wait = True
            print("Service migrated, listening for controller now...\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simple counting server.")
    parser.add_argument(
        "ip",
        type=str,
        help="IP adress for the host on which the server is deployed.",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="True if server is waiting for controller command to migrate",
    )

    args = parser.parse_args()
    print("Starting up server with IP address {}\n".format(args.ip))
    run(args.ip, args.wait)