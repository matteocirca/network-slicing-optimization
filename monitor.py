#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""
About: Simple monitor checking for network performance.
"""

import os
import socket
import time
import subprocess
from subprocess import check_output
import shlex

if __name__ == "__main__":
    serviceInH3 = True
    bottomSlice = False

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("172.17.0.2", 6633))

    bandwidth = {}
    msg = ""
    
    while True:
        data, addr = sock.recvfrom(6633)

        #If iperf returns an error (server not reachable) logic does not handle the error (probably because check output can't read something printed to stderr)
        #Shouldn't be able to happen in this demo anyways

        try:
            #Iperf slice 1
            data = check_output(shlex.split('iperf -c 10.0.0.3 -u -p 9998 -b 10M -t 5 -i 1 -C'), universal_newlines=True)
            x = (str(data)).split()
            x.reverse()
            index = x.index("Mbits/sec")
            bandwidth["slice1"] = float(x[index+1])
            print("BW slice 1: ", bandwidth["slice1"])

            if serviceInH3:

                #Iperf slice 2
                data = check_output(shlex.split('iperf -c 10.0.0.3 -u -p 1023 -b 10M -t 5 -i 1 -C'), universal_newlines=True)
                x = (str(data)).split()
                x.reverse()
                index = x.index("Mbits/sec")
                bandwidth["slice2"] = float(x[index+1])
                print("BW slice 2: ", bandwidth["slice2"])

                #Check slices
                if bandwidth["slice2"] > bandwidth["slice1"]:
                    #Check sentry host to decide if it's better to migrate service or swap slices
                    data = check_output(shlex.split('iperf -c 10.0.0.4 -u -p 9998 -b 10M -t 5 -i 1 -C'), universal_newlines=True)
                    x = (str(data)).split()
                    x.reverse()
                    index = x.index("Mbits/sec")
                    bandwidth["sentinella"] = float(x[index+1])
                    print("BW sentinella: ", bandwidth["sentinella"])
                    
                    if bandwidth["sentinella"] >= bandwidth["slice2"]:
                        serviceInH3 = False
                        #Bottleneck is s2-s4
                        msg = "MIGRATE - BW sentinella = " + str(bandwidth["sentinella"])
                    else:
                        bottomSlice = not bottomSlice
                        #Bottleneck is s1-s2
                        msg = "SWAP - BW slice2 = " + str(bandwidth["slice2"])
                else:
                    if bottomSlice:
                        #Check sentry host to decide if it's better to migrate service or swap slices
                        data = check_output(shlex.split('iperf -c 10.0.0.4 -u -p 1023 -b 10M -t 5 -i 1 -C'), universal_newlines=True)
                        x = (str(data)).split()
                        x.reverse()
                        index = x.index("Mbits/sec")
                        bandwidth["sentinella"] = float(x[index+1])
                        print("BW sentinella: ", bandwidth["sentinella"])
                        if bandwidth["sentinella"] >= bandwidth["slice1"]:
                            serviceInH3 = False
                            bottomSlice = False
                            #Bottleneck is s2-s4
                            msg = "MIGRATE - BW sentinella = " + str(bandwidth["sentinella"])
                        else:
                            #Performance is optimal with current setup
                            msg = "OK - BW slice1 = " + str(bandwidth["slice1"])
                    else:
                        #Performance is optimal with current setup
                        msg = "OK - BW slice1 = " + str(bandwidth["slice1"])
            else:
                #Service in h4
                #Iperf slice 2
                data = check_output(shlex.split('iperf -c 10.0.0.4 -u -p 1023 -b 10M -t 5 -i 1 -C'), universal_newlines=True)
                x = (str(data)).split()
                x.reverse()
                index = x.index("Mbits/sec")
                bandwidth["slice2"] = float(x[index+1])
                print("BW slice 2: ", bandwidth["slice2"])

                #Check slices
                if bandwidth["slice2"] > bandwidth["slice1"]:
                    serviceInH3 = True
                    bottomSlice = True
                    #Bottleneck is s1-s2
                    msg = "MIGRATESWAP - BW slice2= " + str(bandwidth["slice2"])
                else:
                    #Performance is optimal with current setup
                    msg = "OK - BW slice1 = " + str(bandwidth["slice1"])

        except subprocess.CalledProcessError as error:
            print(error)

        #data = b"Oh yes, send you a pic!"
        msg = bytes(msg, 'utf8')
        sock.sendto(msg, ("172.17.0.1", 6633))