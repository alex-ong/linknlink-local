#!/usr/bin/env python3
"""The python-linknlink library."""
import socket
import typing as t
import logging
_LOGGER = logging.getLogger("custom_components.linknlink")

from . import exceptions as e
from .const import DEFAULT_BCAST_ADDR, DEFAULT_PORT, DEFAULT_TIMEOUT
from .device import Device, scan, ping
from .remote import ehub, ehome_rf_ha, eremote
from .sensor import motion, eths

SUPPORTED_TYPES = {
    motion: {
        0xAC7B: ("eMotion", "LinknLink"),
    },
    eths: {
        0xAC7C: ("eTHS", "LinknLink"),
    },
    ehub: {
        0x520B: ("eHub", "LinknLink"),
    },
    ehome_rf_ha: {
        0xAC85: ("eHome HA", "LinknLink")
    },
    eremote: {
        0xAC99: ("eRemote", "LinknLink"),
    },
}


def gendevice(
    dev_type: int,
    host: t.Tuple[str, int],
    mac: t.Union[bytes, str],
    name: str = "",
    is_locked: bool = False,
) -> Device:
    """Generate a device."""
    _LOGGER.error("generating devices")
    _LOGGER.error(len(SUPPORTED_TYPES))
    for dev_cls, products in SUPPORTED_TYPES.items():
        try:
            _LOGGER.error("dev_type=%s", dev_type)
            model, manufacturer = products[dev_type]
            _LOGGER.error(model)
            _LOGGER.error(manufacturer)
        except KeyError:
            continue
        return dev_cls(
            host,
            mac,
            dev_type,
            name=name,
            model=model,
            manufacturer=manufacturer,
            is_locked=is_locked,
        )
    return Device(host, mac, dev_type, name=name, is_locked=is_locked)


def hello(
    host: str,
    port: int = DEFAULT_PORT,
    timeout: int = DEFAULT_TIMEOUT,
) -> Device:
    """Direct device discovery.

    Useful if the device is locked.
    """
    try:
        return next(
            xdiscover(timeout=timeout, discover_ip_address=host, discover_ip_port=port)
        )
    except StopIteration as err:
        raise e.NetworkTimeoutError(
            -4000,
            "Network timeout",
            f"No response received within {timeout}s",
        ) from err


def discover(
    timeout: int = DEFAULT_TIMEOUT,
    local_ip_address: str = None,
    discover_ip_address: str = DEFAULT_BCAST_ADDR,
    discover_ip_port: int = DEFAULT_PORT,
) -> t.List[Device]:
    """Discover devices connected to the local network."""
    responses = scan(timeout, local_ip_address, discover_ip_address, discover_ip_port)
    return [gendevice(*resp) for resp in responses]


def xdiscover(
    timeout: int = DEFAULT_TIMEOUT,
    local_ip_address: str = None,
    discover_ip_address: str = DEFAULT_BCAST_ADDR,
    discover_ip_port: int = DEFAULT_PORT,
) -> t.Generator[Device, None, None]:
    """Discover devices connected to the local network.

    This function returns a generator that yields devices instantly.
    """
    responses = scan(timeout, local_ip_address, discover_ip_address, discover_ip_port)
    for resp in responses:
        _LOGGER.error(resp)
        yield gendevice(*resp)


# Setup a new LinknLink device via AP Mode. Review the README to see how to enter AP Mode.
# Only tested with LinknLink RM3 Mini (Blackbean)
def setup(ssid: str, password: str, security_mode: int) -> None:
    """Set up a new LinknLink device via AP mode."""
    # Security mode options are (0 - none, 1 = WEP, 2 = WPA1, 3 = WPA2, 4 = WPA1/2)
    payload = bytearray(0x88)
    payload[0x26] = 0x14  # This seems to always be set to 14
    # Add the SSID to the payload
    ssid_start = 68
    ssid_length = 0
    for letter in ssid:
        payload[(ssid_start + ssid_length)] = ord(letter)
        ssid_length += 1
    # Add the WiFi password to the payload
    pass_start = 100
    pass_length = 0
    for letter in password:
        payload[(pass_start + pass_length)] = ord(letter)
        pass_length += 1

    payload[0x84] = ssid_length  # Character length of SSID
    payload[0x85] = pass_length  # Character length of password
    payload[0x86] = security_mode  # Type of encryption

    checksum = sum(payload, 0xBEAF) & 0xFFFF
    payload[0x20] = checksum & 0xFF  # Checksum 1 position
    payload[0x21] = checksum >> 8  # Checksum 2 position

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Internet  # UDP
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(payload, (DEFAULT_BCAST_ADDR, DEFAULT_PORT))
    sock.close()
