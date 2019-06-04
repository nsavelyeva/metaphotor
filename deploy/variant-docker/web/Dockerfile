FROM python:3.7-alpine3.8
MAINTAINER Natallia Savelyeva

RUN apk --update add gcc libgcc linux-headers musl-dev zlib-dev jpeg-dev postgresql-dev

COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --requirement /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

RUN apk add ca-certificates ffmpeg libva-intel-driver \
    && rm -rf /var/cache/*

WORKDIR /opt/metaphotor/
COPY uwsgi.ini /etc/uwsgi.ini
