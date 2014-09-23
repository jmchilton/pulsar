# Base Image for Pulsar + Mesos
#
# VERSION       0.1.0

# Build Docker image and then run tests with current pulsar clone! Tests
# include exercising rabbitmq, run as real user, DRMAA, etc....
# sudo docker build -t pulsar/testing .  
# sudo docker run -v `pwd`/../..:/pulsar/ -t pulsar/testing 

FROM ubuntu:14.04

MAINTAINER John Chilton, jmchilton@gmail.com

RUN echo "deb http://repos.mesosphere.io/ubuntu/ trusty main" > /etc/apt/sources.list.d/mesosphere.list
RUN apt-key adv --keyserver keyserver.ubuntu.com --recv E56151BF

RUN DEBIAN_FRONTEND=noninteractive apt-get -qq update

RUN DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y build-essential
RUN DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y python-dev
RUN DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y python-virtualenv
RUN DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y sudo
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y rabbitmq-server
RUN DEBIAN_FRONTEND=noninteractive apt-get -y install mesos 
RUN DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y libcurl4-openssl-dev

RUN mkdir /usr/share/pulsar; chmod 755 /usr/share/pulsar
RUN virtualenv /usr/share/pulsar/venv

RUN . /usr/share/pulsar/venv/bin/activate; pip install webob psutil PasteDeploy six paste PasteScript
RUN . /usr/share/pulsar/venv/bin/activate; pip install pycurl kombu pyyaml

ENV PULSAR_LOCAL_ENV /usr/share/pulsar/container_env.sh
ENV PULSAR_VIRTUALENV /usr/share/pulsar/venv

ADD container_env.sh /usr/share/pulsar/container_env.sh

