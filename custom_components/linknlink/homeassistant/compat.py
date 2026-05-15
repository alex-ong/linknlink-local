"""Home Assistant compatibility helpers."""

try:
    from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
except ImportError:
    from homeassistant.components.dhcp import DhcpServiceInfo

__all__ = ["DhcpServiceInfo"]
