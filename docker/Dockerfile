FROM python:3.8-slim

ENV TZ="Europe/Amsterdam"

COPY requirements.txt /

RUN apt-get update && apt-get install -y build-essential libffi-dev tzdata \
    && python3 -m pip install --upgrade pip \
    && pip3 install --no-cache-dir -U -I -r requirements.txt \
        && rm -rf /var/lib/apt/lists/*

VOLUME /config

WORKDIR /app
COPY galaxyscore.py .

CMD [ "python", "-u", "./galaxyscore.py", "-d", "/config" ]
