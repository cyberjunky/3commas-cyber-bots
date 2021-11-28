
Choose the Dockerfile to use and copy it to 3commas-cyber-bots directory
If you use a RaspberryPi
```
$ cp Dockerfile.pi ../Dockerfile
```
Else use the generic version
```
$ cp Dockerfile ..
```

Edit the file 
```
cd ..
vi Dockerfile

Replace <SCRIPT_NAME>.py with the tool you want to run


So for galaxyscore it looks like this:
```
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
```

Create docker image using 'Dockerfile' and give it the name 'galaxyscore'
```
$ docker build -t galaxyscore .
```

Create docker volume with name 'config-galaxyscore'
```
$ docker volume create config-galaxyscore
```

List docker volume(s)
```
$ docker volume ls
DRIVER    VOLUME NAME
local     config-galaxyscore
```

Run docker image and mount persistant volume for /config
```
$ docker run --mount source=config-galaxyscore,target=/config galaxyscore
```

To run in daemon mode add -d

```
$ docker run -d --mount source=config-galaxyscore,target=/config galaxyscore
```


You can also run it using docker-compose

Edit example docker-compose.yml and run it:

```
$ docker-compose up -d
```

If you need to recreate the container with same name, you need to delete the old one

```
$ docker rm galaxyscore
```

