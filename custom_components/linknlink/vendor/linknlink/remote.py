"""Support for universal remotes."""
import struct
import socket
import time
import threading
from typing import Tuple

from linknlink.const import DEFAULT_TIMEOUT

from . import exceptions as e
from .device import Device
from .device import Device
from.const import PID_DOORSENSOR, PID_HUMITURE, PID_REMOTE
import json
import typing as t

class ehub(Device):
    """Controls a LinknLink ehub."""

    TYPE = "EHUB"
    
    # sensor function
    def _send(self, command: int, data: bytes = b"") -> bytes:
        """Send a packet to the device."""
        if 20000 <= self.devtype <= 29999:
            packet = struct.pack("<HI", len(data) + 4, command) + data
        else:
            packet = struct.pack("<I", command) + data
        resp = self.send_packet(0x6A, packet)
        e.check_error(resp[0x22:0x24])
        payload = self.decrypt(resp[0x38:])
        if 20000 <= self.devtype <= 29999:
            p_len = struct.unpack("<H", payload[:0x2])[0]
            return payload[0x6 : p_len + 2]
        return payload[0x4:]
    
    def check_sensors(self) -> dict:
        """Return the state of the sensors."""
        resp = self._send(0x24)
        return {
            "envtemp": resp[0x0] + resp[0x1] / 100.0,
            "envhumid": resp[0x2] + resp[0x3] / 100.0,
            "pir_detected": resp[0x6],
        }

    def check_temperature(self) -> float:
        """Return the temperature."""
        return self.check_sensors()["temperature"]

    def check_humidity(self) -> float:
        """Return the humidity."""
        return self.check_sensors()["humidity"]
    
    def check_pir(self) -> str:
        """Return the pirDetected."""
        return self.check_sensors()["pir_detected"]

    # remote function
    def sweep_frequency(self) -> None:
        """Sweep frequency."""
        self._send(0x19)

    def check_frequency(self) -> bool:
        """Return True if the frequency was identified successfully."""
        resp = self._send(0x1A)
        return resp[0] == 1

    def find_rf_packet(self) -> None:
        """Enter radiofrequency learning mode."""
        self._send(0x1B)

    def cancel_sweep_frequency(self) -> None:
        """Cancel sweep frequency."""
        self._send(0x1E)

    def update(self) -> None:
        """Update device name and lock status."""
        resp = self._send(0x1)
        self.name = resp[0x48:].split(b"\x00")[0].decode()
        self.is_locked = bool(resp[0x87])

    def send_data(self, data: bytes) -> None:
        """Send a code to the device."""
        self._send(0x2, data)

    def enter_learning(self) -> None:
        """Enter infrared learning mode."""
        self._send(0x3)

    def check_data(self) -> bytes:
        """Return the last captured code."""
        return self._send(0x4)

class eremote(Device):
    """Controls a LinknLink eremote."""

    TYPE = "EREMOTE"
    UdpFlag = False
    Port = 61212
    
    def _send(self, command: int, data: bytes = b"") -> bytes:
        """Send a packet to the device."""
        if 20000 <= self.devtype <= 29999:
            packet = struct.pack("<HI", len(data) + 4, command) + data
        else:
            packet = struct.pack("<I", command) + data
        resp = self.send_packet(0x6A, packet)
        e.check_error(resp[0x22:0x24])
        payload = self.decrypt(resp[0x38:])
        if 20000 <= self.devtype <= 29999:
            p_len = struct.unpack("<H", payload[:0x2])[0]
            return payload[0x6 : p_len + 2]
        return payload[0x4:]
    
    def _sendV2(self, command: int, data: bytes = b"") -> bytes:
        """Send a packet to the device."""
        cmdstu = self.build_cmdstuV2(command, data)
        resp = self.send_packet(0x6A, cmdstu)
        e.check_error(resp[0x22:0x24])
        payload = self.decrypt(resp[0x38:])
        res = self.analysis_data(payload)
        return res[2]
    
    def startUdpServer(self):
        # 创建一个 UDP socket
        udp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # 绑定服务器地址和端口
        server_address = ('', self.Port)  # 绑定到所有网络接口
        try:
            udp_server_socket.bind(server_address)
        except OSError as e:
            if e.errno == socket.errno.EADDRINUSE:
                # print(f"端口{self.Port}已被占用")
                self.Port += 1
                return self.startUdpServer()
            else:
                raise e

        # print(f"UDP 服务器已在{self.Port}启动，等待客户端连接...")

        # 接收数据并发送响应
        while True:
            # 接收数据
            data, client_address = udp_server_socket.recvfrom(1024)
            if self.cb:
                try:
                    data_dict = json.loads(data.decode('utf-8'))
                    for key, value in data_dict.items():
                        if key.startswith("rmkey") and value != 0:
                            # print(f"键: {key}, 值: {value}")
                            self.cb(key)
                except Exception as e:
                    print(e)

            # 发送响应
            response = "ok"
            udp_server_socket.sendto(response.encode('utf-8'), client_address)

    def sendTimeout(self) -> bytes:
        """Send a packet to the device."""
        while True:
            data = (("""{"port":%s, "timeout":60}""") % (self.Port)).encode('utf-8')
            packet = struct.pack("<I", 20000) + data
            # packet = struct.pack("<HI", len(data) + 4, 20000) + data
            try: 
                resp = self.send_packet(0x6A, packet)
            except Exception as e:
                print(e)
            time.sleep(60)
    
    def getalldev(self) -> dict:
        """Return the all devices."""
        resp = self._sendV2(0x0b0e, """{"count":16,"index":0,}""".encode('utf-8')) # max 16dev
        try:
            json_string = resp.decode('utf-8')
            json_object = json.loads(json_string)
        except Exception:
            return {}
        # 使用字典推导式创建pid到did的映射
        pid_to_did_map = {}
        for item in json_object['list']:
            pid = item['pid']
            did = item['did']
            if pid in pid_to_did_map:
                pid_to_did_map[pid].append(did)
            else:
                pid_to_did_map[pid] = [did]
        return pid_to_did_map
    
    def check_sensors(self) -> dict:
        """Return the state of the sensors."""
        if not self.UdpFlag:
            self.UdpFlag = True
            # 启动一个线程来运行 UDP 服务器
            thread = threading.Thread(target=self.startUdpServer)
            thread.start()
            # 周期向客户端发送超时时间
            thread2 = threading.Thread(target=self.sendTimeout)
            thread2.start()
        big_dict = {}
        pid_to_did_map = self.getalldev()
        # print(pid_to_did_map)
        for pid in PID_HUMITURE, PID_DOORSENSOR, PID_REMOTE:
            if pid in pid_to_did_map:
                for did in pid_to_did_map[pid]:
                    resp = self._sendV2(0x0b01, ("""{"did":"%s"}"""%(did)).encode('utf-8'))
                    try:
                        json_string = resp.decode('utf-8')
                        json_object = json.loads(json_string)
                    except Exception:
                        return {}
                    # print(json_object)
                    big_dict.update(json_object)
        if "envtemp" in big_dict:
            big_dict["envtemp"] = round(float(big_dict["envtemp"])/100, 2)
        if "envhumid" in big_dict:
            big_dict["envhumid"] = round(float(big_dict["envhumid"])/100, 2)
        return big_dict

    def check_temperature(self) -> float:
        """Return the temperature."""
        return round(float(self.check_sensors()["envtemp"])/100, 2)

    def check_humidity(self) -> float:
        """Return the humidity."""
        return round(float(self.check_sensors()["envhumid"])/100, 2)
    
    def check_doorsensor(self) -> str:
        """Return the pirDetected."""
        return self.check_sensors()["doorsensor_status"]

    # remote function
    def sweep_frequency(self) -> None:
        """Sweep frequency."""
        self._send(0x19)

    def check_frequency(self) -> bool:
        """Return True if the frequency was identified successfully."""
        resp = self._send(0x1A)
        return resp[0] == 1

    def find_rf_packet(self) -> None:
        """Enter radiofrequency learning mode."""
        self._send(0x1B)

    def cancel_sweep_frequency(self) -> None:
        """Cancel sweep frequency."""
        self._send(0x1E)

    def update(self) -> None:
        """Update device name and lock status."""
        resp = self._send(0x1)
        self.name = resp[0x48:].split(b"\x00")[0].decode()
        self.is_locked = bool(resp[0x87])

    def send_data(self, data: bytes) -> None:
        """Send a code to the device."""
        self._send(0x2, data)

    def enter_learning(self) -> None:
        """Enter infrared learning mode."""
        self._send(0x3)

    def check_data(self) -> bytes:
        """Return the last captured code."""
        return self._send(0x4)