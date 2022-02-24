#! /usr/bin/env bash

echo "Clear environment"
#Clear enviroment
docker stop $(docker ps -aq)
docker rm $(docker ps -aq)
sudo mn -c

#Build images
echo "Build docker image for the client, monitor and servers routine."
docker build -t routine --file ./Dockerfile .
docker image prune

echo "All done!"