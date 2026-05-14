"""Support for sensors."""

from . import exceptions as e
from .device import Device
import json

class eths(Device):
    """Controls a LinknLink eths."""

    TYPE = "ETHS"
    
    def _send(self, command: int, data: bytes = b"") -> bytes:
        """Send a packet to the device."""
        cmdstu = self.build_cmdstu(command)
        resp = self.send_packet(0x6A, cmdstu)
        e.check_error(resp[0x22:0x24])
        payload = self.decrypt(resp[0x38:])
        res = self.analysis_data(payload)
        return res[2]
    
    def check_sensors(self) -> dict:
        """Return the state of the sensors."""
        resp = self._send(0x0b01)
        try:
            json_string = resp.decode('utf-8')
            json_object = json.loads(json_string)
        except Exception:
            return {}
        # return json_object
        return {
            "envtemp": float(json_object["envtemp"]) / 100.0,
            "envhumid": float(json_object["envhumid"]) / 100.0,
        }

    def check_temperature(self) -> float:
        """Return the temperature."""
        return float(self.check_sensors()["envtemp"]) / 100.0

    def check_humidity(self) -> float:
        """Return the humidity."""
        return float(self.check_sensors()["envhumid"]) / 100.0

class motion(eths):
    """Controls a LinknLink motion."""

    TYPE = "EMOTION"

    def check_sensors(self) -> dict:
        """Return the state of the sensors."""
        resp = self._send(0x0b01)
        try:
            json_string = resp.decode('utf-8')
            json_object = json.loads(json_string)
        except Exception:
            return {}
        return json_object

    def check_pir(self) -> int:
        """Return the pirDetected."""
        return self.check_sensors()["pir_detected"]