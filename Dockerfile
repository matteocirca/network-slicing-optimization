FROM python:3

RUN apt-get update
RUN apt-get install iperf -y

COPY ./client.py /home/client.py
COPY ./server.py /home/server.py
COPY ./monitor.py /home/monitor.py