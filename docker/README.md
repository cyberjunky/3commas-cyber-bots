
## Running in docker

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
$ cd ..
$ vi Dockerfile
```

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

## docker-compose

You can also run it using docker-compose

Edit example docker-compose.yml and run it:

```
$ docker-compose up -d
```

If you need to recreate the container with same name, you need to delete the old one

```
$ docker rm galaxyscore
```

## Home assistant Portainer

## Requirements
- Pycharm
-  Docker desktop
-  Home Assistant with Portainer addon installed
-  Git

## Pycharm settings

Make shure **Activate virtualenv** is enabled in File --> Settings --> Tools --> Terminal

## Pycharm steps
-  File --> New Project 
-  Name project and select **New environment using Virtualenv** click **Create**
-  On the bottom left select Terminal
```
$ sudo apt install git
$ git clone https://github.com/cyberjunky/3commas-cyber-bots.git
$ cd 3commas-cyber-bots
$ pip3 install -r requirements.txt
$ python compound.py
```
Once compound.py is executed it wil create a compound.ini edit this file and start the script again to see if it works

## Create dockerfile

Create a file without an extention in the directory above the **3commas-cyber-bots** folder

- Your project folder
- - 3commas-cyber-bots
- - venv
- - Dockerfile

Open the Dockerfile and add this

```
FROM python:3.9  
  
WORKDIR /commabot  
  
COPY /3commas-cyber-bots/requirements.txt .  
  
RUN pip install -r requirements.txt  
  
COPY /3commas-cyber-bots/ .  
  
CMD ["python", "./compound.py"]
```
Save everything


## Creating the docker container

In the terminal make shure you are in the folder above **3commas-cyber-bots**

```
docker build -t 3commabot .

docker save 3commabot > 3commabot.tar
```
Now you should see a file **3commabot.tar**

## Adding Container to portainer

 - Go to Images --> import
 - Select file --> select your **3commabot.tar** --> upload
 - Go to Containers --> select **Add container** --> image enter **3commabot:latest** and give your container a name
 - **Deploy the container**

