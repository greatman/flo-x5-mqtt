FROM python:3.12-alpine


RUN pip install requests ha_mqtt_discoverable pkce

WORKDIR /app

COPY main.py /app
COPY flo_client /app/flo_client

ENTRYPOINT ["python", "-u", "main.py"]
