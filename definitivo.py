import os
import shlex
import time

from subprocess import check_output

from comnetsemu.cli import CLI
from comnetsemu.net import Containernet, VNFManager
from comnetsemu.node import DockerHost
from mininet.link import TCLink
from mininet.log import info, setLogLevel

from mininet.topo import Topo
from mininet.node import OVSKernelSwitch, RemoteController
    
class NetworkSlicingTopo(Topo):
    def __init__(self):
        # Initialize topology
        Topo.__init__(self)

        # Create template host, switch, and link
        http_link_config = dict(bw=2)
        video_link_config = dict(bw=15)
        host_link_config = dict()
        
        h1 = self.addHost(
            "h1",
            cls=DockerHost,
            dimage="dev_test",
            ip="10.0.0.1/24",
            mac="00:00:00:00:00:01",
            docker_args={"hostname": "h1"}
        )
        h2 = self.addHost(
            "h2",
            cls=DockerHost,
            dimage="dev_test",
            ip="10.0.0.2/24",
            mac="00:00:00:00:00:02",
            docker_args={"hostname": "h2"}
        )
        h3 = self.addHost(
            "h3",
            cls=DockerHost,
            dimage="dev_test",
            ip="10.0.0.3/24",
            mac="00:00:00:00:00:03",
            docker_args={"hostname": "h3"}
        )
        h4 = self.addHost(
            "h4",
            cls=DockerHost,
            dimage="dev_test",
            ip="10.0.0.3/24",
            mac="00:00:00:00:00:03",
            docker_args={"hostname": "h4"}
        )
        h5 = self.addHost(
            "h5",
            cls=DockerHost,
            dimage="dev_test",
            ip="10.0.0.4/24",
            mac="00:00:00:00:00:04",
            docker_args={"hostname": "h5"}
        )
        h6 = self.addHost(
            "h6",
            cls=DockerHost,
            dimage="dev_test",
            ip="10.0.0.4/24",
            mac="00:00:00:00:00:04",
            docker_args={"hostname": "h6"}
        )
        
        switches = {}
        for i in range(4):
            sconfig = {"dpid": "%016x" % (i + 1)}
            switches["s" + str(i+1)] = self.addSwitch("s%d" % (i + 1), **sconfig)

        self.addLink(switches["s1"], switches["s2"], **video_link_config)
        self.addLink(switches["s2"], switches["s4"], **video_link_config)
        self.addLink(switches["s1"], switches["s3"], **http_link_config)
        self.addLink(switches["s3"], switches["s4"], **http_link_config)
        self.addLink(h1, switches["s1"], **host_link_config)
        self.addLink(h2, switches["s1"], **host_link_config)
        self.addLink(h3, switches["s4"], **host_link_config)
        self.addLink(h4, switches["s2"], **host_link_config)
        self.addLink(h5, switches["s2"], **host_link_config)
        self.addLink(h6, switches["s4"], **host_link_config)


topos = {"networkslicingtopo": (lambda: NetworkSlicingTopo())}


try:
    if __name__ == "__main__":
        
        setLogLevel("info")

        topo = NetworkSlicingTopo()
        net = Containernet(
            topo=topo,
            switch=OVSKernelSwitch,
            build=False,
            autoSetMacs=True,
            autoStaticArp=True,
            link=TCLink
        )

        mgr = VNFManager(net)

        info("*** Connecting to the controller\n")
        controller = RemoteController("c1", ip="127.0.0.1", port=6633)
        net.addController(controller)

        info("\n*** Starting network\n")
        net.build()
        net.start()

        info("*** Start listening on h3 as an UDP server\n")
        net.get('h3').cmd("iperf -s -u -p 9998 -b 10M &")
        net.get('h3').cmd("iperf -s -u -p 1023 -b 10M &")

        info("*** Start listening on h4 as an UDP server\n")
        net.get('h4').cmd("iperf -s -u -p 9998 -b 10M &")

        info("*** Start listening on h5 as an UDP server\n")
        net.get('h5').cmd("iperf -s -u -p 9998 -b 10M &")
        net.get('h5').cmd("iperf -s -u -p 1023 -b 10M &")

        info("*** Start listening on h6 as an UDP server\n")
        net.get('h6').cmd("iperf -s -u -p 1023 -b 10M &")
        
        info("*** Deploying docker containers...\n")

        logs = {}
        logs["h1"] = mgr.addContainer(
            "monitor", "h1", "routine", "python /home/monitor.py"
        )
        info("h1 ")
        logs["h2"] = mgr.addContainer(
            "client", "h2", "routine", "python /home/client.py"
        )
        info("h2 ")
        logs["h3"] = mgr.addContainer(
            "serverh3", "h3", "routine", "python /home/server.py 172.17.0.4"
        )
        info("h3 ")
        logs["h4"] = mgr.addContainer(
            "serverh4", "h4", "routine", "python /home/server.py 172.17.0.5 --wait"
        )
        info("h4\n")

        #info("\n*** Spero sia andato lmao\n")
        
        links_index = {}
        links_index["s1s2"] = 1
        links_index["s2s4"] = 2
        links_index["s1s3"] = 2
        links_index["s3s4"] = 2

        #Simple command menu to interact with the demo in real time
        inMenu = True
        while inMenu:
            choice = input("\n*** MENU:\n1) Open CLI\n2) Modify bandwidth\n3) Show host logs\n4) Stop network simulation\nACTION: ")
            if choice=="1":
                #1 = Mininet CLI
                CLI(net)
            elif choice=="2":
                #2 = Modify Bandwith
                inModifyBandwidth = True
                while inModifyBandwidth:
                    choice = input('\nInsert "node1 node2 new_bandwidth" to change bandwidth of a link or "X" to exit: ')
                    args = choice.split()

                    if args[0] == "X":
                        inModifyBandwidth = False
                    elif args[0] in ["s1","s2","s3"]:
                        try:
                            node1 = args[0]
                            node2 = args[1]
                            new_bw = int(args[2])

                            node = net.getNodeByName(node1) 

                            links = node.intfList()

                            links[links_index[node1+node2]].link.intf1.config(bw=new_bw)
                            links[links_index[node1+node2]].link.intf2.config(bw=new_bw)
                        except Exception as e:
                            print("Error! Invalid input")
                    else:
                        print("Error! Invalid input")
            elif choice == "3":
                #Server log
                inLogMenu = True
                while inLogMenu:
                    arg = input('\nInsert "h1/h2/h3/h4" to see the logs of the various hosts or "X" to exit: ')
                    if arg == "X":
                        inLogMenu = False
                    elif arg in ["h1","h2","h3","h4"]:
                        log = logs[arg].getLogs()
                        info("\n***Current log on host {}: \n{}".format(arg, log))
                        cont = input("\nContinue?[Y/n]: ")
                        while cont != "n":
                            time.sleep(5)
                            log = logs[arg].getLogs()
                            info("\n***Current log on host {}: \n{}".format(arg, log))
                            cont = input("\nContinue?[Y/n]: ")
            elif choice=="4":
                #Quit
                inMenu = False

        net.stop()
except Exception as e: 
    info("\n*** Osti errore popo!\n")
    print(e)
    net.stop()