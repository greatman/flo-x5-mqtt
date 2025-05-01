"""flo X5 sync daemon."""

import os
import time
import logging

from ha_mqtt_discoverable import Settings

from flo_client.client import FloX5Client
from flo_client.device import FloX5Device
from flo_client.consts import *
from flo_client.station import Station

logger = logging.getLogger(__name__)


def configure_logging(log_level: str | None) -> None:
    level = logging.INFO
    if log_level:
        level = logging.getLevelName(log_level)

    format = "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s"

    logging.basicConfig(level=level, format=format)


if __name__ == "__main__":
    # Get username and password from command line
    username = os.environ.get("FLO_USERNAME")
    password = os.environ.get("FLO_PASSWORD")
    station_name = os.environ.get("FLO_STATION_NAME")
    log_level = os.environ.get("FLO_LOG_LEVEL")
    hass_mqtt_host = os.environ.get("HASS_MQTT_HOST")
    hass_mqtt_port = os.environ.get("HASS_MQTT_PORT")
    hass_mqtt_username = os.environ.get("HASS_MQTT_USERNAME")
    hass_mqtt_password = os.environ.get("HASS_MQTT_PASSWORD")

    configure_logging(log_level)

    # Check if data folder exists
    if not os.path.exists(DATA_FOLDER):
        raise Exception(
            "Data folder not found: '"
            + DATA_FOLDER
            + "'. Please create it and re-run the application."
        )

    # Validate the environment variables, the MQTT username and password are optional.
    if not username:
        raise Exception("FLO_USERNAME environment variable not set.")
    if not password:
        raise Exception("FLO_PASSWORD environment variable not set.")
    if not station_name:
        raise Exception("FLO_STATION_NAME environment variable not set.")
    if not hass_mqtt_host:
        raise Exception("HASS_MQTT_HOST environment variable not set.")
    if not hass_mqtt_port:
        raise Exception("HASS_MQTT_PORT environment variable not set.")

    logger.info("Starting flo to MQTT...")
    try:
        # Create the client
        client = FloX5Client(username, password)
        # Configure the required parameters for the MQTT broker
        mqtt_settings = Settings.MQTT(
            host=hass_mqtt_host,
            port=int(hass_mqtt_port),
            username=hass_mqtt_username,
            password=hass_mqtt_password,
        )
        station_json = client.get_station_by_name(name=station_name)
        if station_json:
            station = Station(station_uid=station_json["chargingStationUid"], client=client, mqtt_settings=mqtt_settings)
            while True:
                try:
                    station.refresh()
                except Exception as e:
                    logger.error("Error updating sensors: ", e)
                time.sleep(REFRESH_DELAY_SECS)
        else:
            raise Exception(f"Station {station_name} not found")
    except Exception as e:
        logger.error("Error: ", e)
