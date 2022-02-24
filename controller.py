from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib.packet import udp
from ryu.lib.packet import tcp
from ryu.lib.packet import icmp
from ryu.lib import hub
from mininet.log import info, setLogLevel
import socket
import time
import subprocess
from subprocess import check_output
import shlex
import argparse


class TrafficSlicing(app_manager.RyuApp):
    #OpenFlow version 1.3
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(TrafficSlicing, self).__init__(*args, **kwargs)
        setLogLevel("info")
        #Bind host MAC adresses to interface
        self.mac_to_port = {
            1: {"00:00:00:00:00:01": 3, "00:00:00:00:00:02": 4},
            4: {"00:00:00:00:00:03": 3, "00:00:00:00:00:04": 1},
            2: {"00:00:00:00:00:03": 2, "00:00:00:00:00:04": 4}
        }

        #9998 used for iperf testing, 9999 used for service packets
        self.slice_TCport = [9998, 9999]

        #Associate interface to slice
        self.slice_ports = {
            1: {1: 1, 2: 2}, 
            4: {1: 1, 2: 2},
            2: {1: 2, 2: 2}
        }
        self.end_swtiches = [1, 4]

        #Server starts on h3
        self.current_sever_ip = "172.17.0.4"
        #The optimal slice at the beginning is 1
        self.current_slice = 1
        #Start thread 
        self.monitor_thread = hub.spawn(self.send)
    
    def send(self):
        #Wait the startup of the performance sampler (h1)
        info("Controller starting up, initial timeout is 60s to ensure network is running properly\n")
        time.sleep(60)
        info(f"Performance check started, will ask for info every 10s (monitor will usually take an additional 10s to reply)\n")

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("172.17.0.1", 6633))
        
        switches = ['s1', 's2', 's3', 's4']

        while True:
            #Ask h1 to gather network performance
            data = b"Send me iperf info"
            sock.sendto(data, ("172.17.0.2", 6633))

            #Performance info
            data, _ = sock.recvfrom(6633)
            info("\nMSG: ", data.decode("utf-8"))

            #Check for action and serve accordingly
            x = (str(data.decode("utf-8"))).split()

            #Swap and migrate aren't functions even if they're called multiple times because python had issues :( ugly code
            if "SWAP" in x:
                info("Swapping slices to improve performance\n")

                #Set new dynamic bindings
                if self.current_slice == 1:
                    self.current_slice = 2
                    self.slice_ports[2][1] = 1
                    self.slice_ports[2][2] = 1
                else:
                    self.current_slice = 1
                    self.slice_ports[2][1] = 2
                    self.slice_ports[2][2] = 2

                #Clear old flow tables
                for switch in switches:
                    check_output(shlex.split('sudo ovs-ofctl del-flows {} udp'.format(switch)), universal_newlines=True)
                    check_output(shlex.split('sudo ovs-ofctl del-flows {} tcp'.format(switch)), universal_newlines=True)
                    check_output(shlex.split('sudo ovs-ofctl del-flows {} icmp'.format(switch)), universal_newlines=True)
            
            elif "MIGRATE" in x:
                info("Migrate server to improve performance\n")

                #Set new dynamic bindings
                if self.current_slice == 2:
                    self.current_slice = 1
                    self.slice_ports[2][1] = 2
                    self.slice_ports[2][2] = 2

                #Send migrate message
                sock.sendto(b'MIGRATE', (self.current_sever_ip, 6633))    
                
                #Receive service state
                data, _  = sock.recvfrom(6633)
                info("Server counter is currently {}\nSending counter to new server\n".format(data.decode("utf-8")))

                #Modify mac_to_port of server
                self.mac_to_port[4]["00:00:00:00:00:03"] = 1
                self.mac_to_port[2]["00:00:00:00:00:03"] = 3
                self.mac_to_port[4]["00:00:00:00:00:04"] = 4
                self.mac_to_port[2]["00:00:00:00:00:04"] = 2
                self.current_sever_ip = "172.17.0.5"
        
                #Send data to new server
                sock.sendto(data, (self.current_sever_ip, 6633))

                #Clear old flow tables
                for switch in switches:
                    check_output(shlex.split('sudo ovs-ofctl del-flows {} dl_dst=00:00:00:00:00:03'.format(switch)), universal_newlines=True)
                    check_output(shlex.split('sudo ovs-ofctl del-flows {} dl_dst=00:00:00:00:00:04'.format(switch)), universal_newlines=True)
               
            elif "MIGRATESWAP" in x:
                info("Swapping slices and migrating service to improve performance\n")

                #Change slice
                #Set new dynamic bindings
                self.current_slice = 2
                self.slice_ports[2][1] = 1
                self.slice_ports[2][2] = 1
                    
                #Migrate service
                #Send migrate message
                sock.sendto(b'MIGRATE', (self.current_sever_ip, 6633))    
                
                #Receive service state
                data, _  = sock.recvfrom(6633)
                info("Server counter is currently {}\nSending counter to new server\n".format(data.decode("utf-8")))
                
                #Modify mac_to_port of server
                self.mac_to_port[4]["00:00:00:00:00:03"] = 3
                self.mac_to_port[2]["00:00:00:00:00:03"] = 2
                self.mac_to_port[4]["00:00:00:00:00:04"] = 1
                self.mac_to_port[2]["00:00:00:00:00:04"] = 4
                self.current_sever_ip = "172.17.0.4"
            
                #Send data to new server
                sock.sendto(data, (self.current_sever_ip, 6633))
                
                #Clear old flow tables
                for switch in switches:
                    check_output(shlex.split('sudo ovs-ofctl del-flows {} udp'.format(switch)), universal_newlines=True)
                    check_output(shlex.split('sudo ovs-ofctl del-flows {} tcp'.format(switch)), universal_newlines=True)
                    check_output(shlex.split('sudo ovs-ofctl del-flows {} icmp'.format(switch)), universal_newlines=True)
                    check_output(shlex.split('sudo ovs-ofctl del-flows {} dl_dst=00:00:00:00:00:03'.format(switch)), universal_newlines=True)
                    check_output(shlex.split('sudo ovs-ofctl del-flows {} dl_dst=00:00:00:00:00:04'.format(switch)), universal_newlines=True)
                
            time.sleep(10)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        #Install the table-miss flow entry.
        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)
        ]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        #Construct flow_mod message and send it.
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(
            datapath=datapath, priority=priority, match=match, instructions=inst
        )
        datapath.send_msg(mod)

    def _send_package(self, msg, datapath, in_port, actions):
        data = None
        ofproto = datapath.ofproto
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = datapath.ofproto_parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        datapath.send_msg(out)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        #Get packet info
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            # ignore lldp packet
            return
        dst = eth.dst
        src = eth.src

        dpid = datapath.id

        if dpid in self.mac_to_port:
            if dst in self.mac_to_port[dpid]:
                #Create new flow based on known flow table
                out_port = self.mac_to_port[dpid][dst]
                actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
                match = datapath.ofproto_parser.OFPMatch(eth_dst=dst)
                self.add_flow(datapath, 1, match, actions)
                self._send_package(msg, datapath, in_port, actions)
            elif (pkt.get_protocol(udp.udp) and pkt.get_protocol(udp.udp).dst_port in self.slice_TCport):
                #Create new flow automatically and send to high performance slice
                slice_number = self.current_slice
                out_port = self.slice_ports[dpid][slice_number]
                match = datapath.ofproto_parser.OFPMatch(
                    in_port=in_port,
                    eth_dst=dst,
                    eth_type=ether_types.ETH_TYPE_IP,
                    ip_proto=0x11,  # udp
                    udp_dst=pkt.get_protocol(udp.udp).dst_port,
                )

                actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
                self.add_flow(datapath, 2, match, actions)
                self._send_package(msg, datapath, in_port, actions)
            elif (pkt.get_protocol(udp.udp) and pkt.get_protocol(udp.udp).dst_port not in self.slice_TCport):
                #Create new flow automatically and send to low performance slice
                slice_number = 2
                if self.current_slice == 2:
                    slice_number = 1
                out_port = self.slice_ports[dpid][slice_number]
                match = datapath.ofproto_parser.OFPMatch(
                    in_port=in_port,
                    eth_dst=dst,
                    eth_src=src,
                    eth_type=ether_types.ETH_TYPE_IP,
                    ip_proto=0x11,  # udp
                    udp_dst=pkt.get_protocol(udp.udp).dst_port,
                )
                actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
                self.add_flow(datapath, 1, match, actions)
                self._send_package(msg, datapath, in_port, actions)
            elif pkt.get_protocol(tcp.tcp):
                #Create new flow automatically and send to low performance slice
                slice_number = 2
                if self.current_slice == 2:
                    slice_number = 1
                out_port = self.slice_ports[dpid][slice_number]
                match = datapath.ofproto_parser.OFPMatch(
                    in_port=in_port,
                    eth_dst=dst,
                    eth_src=src,
                    eth_type=ether_types.ETH_TYPE_IP,
                    ip_proto=0x06,  # tcp
                )
                actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
                self.add_flow(datapath, 1, match, actions)
                self._send_package(msg, datapath, in_port, actions)
            elif pkt.get_protocol(icmp.icmp):
                #Create new flow automatically and send to low performance slice
                slice_number = 2
                if self.current_slice == 2:
                    slice_number = 1
                out_port = self.slice_ports[dpid][slice_number]
                match = datapath.ofproto_parser.OFPMatch(
                    in_port=in_port,
                    eth_dst=dst,
                    eth_src=src,
                    eth_type=ether_types.ETH_TYPE_IP,
                    ip_proto=0x01,  # icmp
                )
                actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
                self.add_flow(datapath, 1, match, actions)
                self._send_package(msg, datapath, in_port, actions)
        elif dpid not in self.end_swtiches:
            #Unknown switch, flood
            out_port = ofproto.OFPP_FLOOD
            actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
            match = datapath.ofproto_parser.OFPMatch(in_port=in_port)
            self.add_flow(datapath, 1, match, actions)
            self._send_package(msg, datapath, in_port, actions)