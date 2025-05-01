"""Client for the flo X5 API."""

import logging
import json
import requests

from datetime import datetime, timedelta
from flo_client.auth import Auth
from flo_client.consts import *


class FloX5Client:
    def __init__(self, username: str, password: str) -> None:
        self.next_refresh = datetime.now()
        self._auth = Auth(username, password)

        self._refresh()

    def _refresh(self) -> None:
        # Refresh every minutes at most
        if datetime.now() < self.next_refresh:
            return

        self._stations = self._get_stations()

        self.next_refresh = datetime.now() + timedelta(seconds=REFRESH_DELAY_SECS)

    def _get_stations(self) -> dict:
        resp = requests.get(STATIONS_URL, headers=self._get_headers())
        if resp.status_code != 200:
            raise Exception("Error getting stations.", resp.status_code, resp.text)

        return resp.json()


    def _get_headers(self) -> dict:
        return {
            "Accept": "*/*",
            "Authorization": "Bearer " + self._auth.get_access_token(),
        }

    def get_station(self, station_uid: str):
        self._refresh()
        resp = requests.get(f"{BASE_URL}/v3.1/homestation/{station_uid}", headers=self._get_headers())


        if resp.status_code != 200:
            raise Exception("Error getting sessions.", resp.status_code, resp.text)
        return resp.json()

    def get_session_by_station_id(self, station_uid: str):
        resp = requests.get(f"{BASE_URL}/v3.1/homestation/chargingstation/{station_uid}/session", headers=self._get_headers())
        if resp.status_code != 200:
            raise Exception("Error getting sessions.", resp.status_code, resp.text)

        return resp.json()

    def get_station_by_name(self, name: str) -> dict | None:
        self._refresh()
        for station in self._stations['ocpiHomeStations']:
            if station["stationPreferences"]["nickname"] == name:
                return station

        return None

    def is_station_online(self, station: dict | None) -> bool:
        if station is None:
            return False

        return (
            station["evse"]["status"] == STATE_AVAILABLE
            or station["evse"]["status"] == STATE_INUSE
        )

    def is_vehicle_connected(self, station: dict | None) -> bool:
        if station is None:
            return False

        return (
            station[STATUS_KEY][PILOT_STATE_KEY] == PILOT_STATE_CONNECTED
            or station[STATUS_KEY][PILOT_STATE_KEY] == PILOT_STATE_CHARGING
        )

    def is_vehicle_charging(self, station: dict | None) -> bool:
        if station is None:
            return False

        return station[STATUS_KEY][PILOT_STATE_KEY] == PILOT_STATE_CHARGING

