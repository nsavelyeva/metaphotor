FROM python:3.8.3-alpine3.12
MAINTAINER Natallia Savelyeva

RUN apk --update add gcc libgcc linux-headers musl-dev zlib-dev jpeg-dev postgresql-dev

COPY deploy/variant-docker/web/requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --requirement /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

RUN addgroup -S nginx && adduser -S nginx -G nginx

RUN apk add ca-certificates ffmpeg libva-intel-driver \
    && rm -rf /var/cache/*

COPY deploy/variant-kubernetes/dockerize/uwsgi.ini /etc/uwsgi.ini
COPY --chown=nginx:nginx src /opt/metaphotor/

WORKDIR /opt/metaphotor/

CMD uwsgi --ini /etc/uwsgi.ini --static-map /static=/opt/metaphotor/app/static
