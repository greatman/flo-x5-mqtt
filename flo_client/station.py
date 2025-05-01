import logging
import os
import uuid
from datetime import datetime, timedelta

from ha_mqtt_discoverable import DeviceInfo, Settings
from ha_mqtt_discoverable.sensors import BinarySensorInfo, BinarySensor, SensorInfo, Sensor

from flo_client.client import FloX5Client
from flo_client.consts import REFRESH_DELAY_SECS, DATA_FOLDER


class Station:
    def __init__(self, station_uid: str, client: FloX5Client, mqtt_settings: Settings.MQTT):
        self.station_uid: str = station_uid
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.client: FloX5Client = client
        self.last_update: None
        self.nickname: str = ""
        self.status: str
        self.online: bool = False
        self.next_refresh: datetime = datetime.now()
        self._capabilities: dict
        self.firmware_version: str
        self.modelType: str
        self.model: str
        self.maxAmperage: int
        self._is_vehicle_connected: bool = False
        self._mqtt_settings: Settings.MQTT = mqtt_settings
        self._initialize_device()

    def refresh(self) -> None:
        # Refresh every minutes at most
        if datetime.now() < self.next_refresh:
            return

        homestation_data = self.client.get_station(self.station_uid)

        self.online = homestation_data["connectionStatus"] == "Online"
        self.firmwareVersion = homestation_data["firmwareVersion"]
        self.last_update = homestation_data["evse"]["lastUpdated"]
        self.is_vehicle_connected = homestation_data["evse"]["status"] == "Charging" or homestation_data["evse"]["status"] == "PluggedIn"
        self.next_refresh = datetime.now() + timedelta(seconds=REFRESH_DELAY_SECS)


        if self.online:
            self.online_sensor.on()
        else:
            self.online_sensor.off()


        if self.is_vehicle_connected:
            self.vehicle_connected_sensor.on()
            homestation_sessions = self.client.get_session_by_station_id(self.station_uid)

            if len(homestation_sessions) > 0:
                session = homestation_sessions[0]
                self.session_duration.set_state(session["duration"])
                self.session_start_time.set_state(session["startDateTime"])
                if session["status"] == "NotCharging" or session["status"] == "Completed":
                    self.vehicle_charging_sensor.off()
                    self.amperage_charging_sensor.set_state(0)
                    self.amperage_offered_sensor.set_state(0)
                    self.voltage_sensor.set_state(0)
                    self.energy_transferred_sensor.set_state(0)
                elif session["status"] == "Charging":
                    self.vehicle_charging_sensor.on()
                    if session["uid"] != self._get_last_session_id():
                        # This is a new session. Let's reset the data
                        self.energy_transferred_sensor.set_state(0)
                        self._save_last_session_id(session["uid"])
                    self.amperage_offered_sensor.set_state(float(session["currentOffered"]))
                    self.amperage_charging_sensor.set_state(float(session["current"]))
                    self.voltage_sensor.set_state(float(session["voltage"]))
                    self.energy_transferred_sensor.set_state(float(session["kwh"]))
        else:
            self.vehicle_connected_sensor.off()
            self.vehicle_charging_sensor.off()
            self.amperage_charging_sensor.set_state(0)
            self.amperage_offered_sensor.set_state(0)
            self.voltage_sensor.set_state(0)




    def _initialize_device(self):
        homestation_data = self.client.get_station(self.station_uid)
        self._capabilities = homestation_data["evse"]["capabilities"]
        self.modelType = homestation_data["modelType"]
        self.model = homestation_data["model"]
        self.maxAmperage = homestation_data["evse"]["connectors"][0]["maxAmperage"]
        self.nickname = homestation_data["stationPreferences"]["nickname"]
        # Define the device. At least one of `identifiers` or `connections` must be supplied
        self.device_info = DeviceInfo(
            name=f"Flo {self.modelType}: {self.nickname}",
            model=self.model,
            manufacturer="AddEnergie",
            identifiers=self.station_uid,
        )
        self._initialize_sensors()
        self.amperage_supported_by_charger.set_state(float(self.maxAmperage))
        self.refresh()





    def _initialize_sensors(self):
        # Online sensor
        online_sensor_info = BinarySensorInfo(
            name="Station Online",
            device_class="connectivity",
            unique_id="status",
            device=self.device_info,
        )
        online_sensor_settings = Settings(
            mqtt=self._mqtt_settings, entity=online_sensor_info
        )

        self.online_sensor = BinarySensor(online_sensor_settings)

        # Vehicle connected sensor
        vehicle_connected_sensor_info = BinarySensorInfo(
            name="Vehicle Connected",
            device_class="connectivity",
            unique_id="vehicle_connected",
            device=self.device_info,
        )
        vehicle_connected_sensor_settings = Settings(
            mqtt=self._mqtt_settings, entity=vehicle_connected_sensor_info
        )

        self.vehicle_connected_sensor = BinarySensor(vehicle_connected_sensor_settings)

        # Charging sensor
        vehicle_charging_sensor_info = BinarySensorInfo(
            name="Vehicle Charging",
            device_class="battery_charging",
            unique_id="vehicle_charging",
            device=self.device_info,
        )
        vehicle_charging_sensor_settings = Settings(
            mqtt=self._mqtt_settings, entity=vehicle_charging_sensor_info
        )

        self.vehicle_charging_sensor = BinarySensor(vehicle_charging_sensor_settings)

        # Amperage sensor
        amperage_charging_sensor_info = SensorInfo(
            name="Amperage",
            unit_of_measurement="A",
            state_class="measurement",
            device_class="current",
            unique_id="amperage_charging",
            device=self.device_info,
        )

        amperage_charging_sensor_settings = Settings(
            mqtt=self._mqtt_settings, entity=amperage_charging_sensor_info
        )

        self.amperage_charging_sensor = Sensor(amperage_charging_sensor_settings)

        # Amperage sensor
        amperage_supported_by_charger_info = SensorInfo(
            name="Amperage supported by charger",
            unit_of_measurement="A",
            state_class="measurement",
            device_class="current",
            unique_id="amperage_supported_by_charger",
            device=self.device_info,
        )

        amperage_supported_by_charger_settings = Settings(
            mqtt=self._mqtt_settings, entity=amperage_supported_by_charger_info
        )

        self.amperage_supported_by_charger = Sensor(amperage_supported_by_charger_settings)

        # Amperage offered sensor
        amperage_offered_sensor_info = SensorInfo(
            name="Amperage Offered",
            unit_of_measurement="A",
            state_class="measurement",
            device_class="current",
            unique_id="amperage_offered",
            device=self.device_info,
        )

        amperage_offered_sensor_settings = Settings(
            mqtt=self._mqtt_settings, entity=amperage_offered_sensor_info
        )

        self.amperage_offered_sensor = Sensor(amperage_offered_sensor_settings)

        # Voltage sensor
        voltage_sensor_info = SensorInfo(
            name="Voltage",
            unit_of_measurement="V",
            state_class="measurement",
            device_class="voltage",
            unique_id="voltage",
            device=self.device_info,
        )

        voltage_sensor_settings = Settings(
            mqtt=self._mqtt_settings, entity=voltage_sensor_info
        )

        self.voltage_sensor = Sensor(voltage_sensor_settings)

        # Energy transferred sensor
        energy_transferred_sensor_info = SensorInfo(
            name="Energy Transferred",
            unit_of_measurement="kWh",
            state_class="total_increasing",
            device_class="energy",
            unique_id="session_energy_transferred",
            device=self.device_info,
        )

        energy_transferred_sensor_settings = Settings(
            mqtt=self._mqtt_settings, entity=energy_transferred_sensor_info
        )

        self.energy_transferred_sensor = Sensor(energy_transferred_sensor_settings)


        # Session Duration sensor
        session_duration_sensor_info = SensorInfo(
            name="Session duration",
            unit_of_measurement="s",
            state_class="total_increasing",
            device_class="duration",
            unique_id="session_duration",
            device=self.device_info
        )

        session_duration_sensor_settings = Settings(
            mqtt=self._mqtt_settings, entity=session_duration_sensor_info
        )

        self.session_duration = Sensor(session_duration_sensor_settings)

        # Session Start Time sensor
        session_start_time_info = SensorInfo(
            name="Session Start Time",
            device_class="date",
            unique_id="session_duration",
            device=self.device_info
        )

        session_start_time_sensor_settings = Settings(
            mqtt=self._mqtt_settings, entity=session_start_time_info
        )

        self.session_start_time = Sensor(session_start_time_sensor_settings)

    def _save_last_session_id(self, session_id: str) -> None:
        with open(f"{DATA_FOLDER}/last-session", "w") as f:
            f.write(session_id)

    def _get_last_session_id(self) -> str | None:
        if os.path.exists(f"{DATA_FOLDER}/last-session"):
            with open(f"{DATA_FOLDER}/last-session", "r") as f:
                return f.read()

        return None


