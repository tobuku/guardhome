"""LAN device discovery via ARP scan.

Tries arp-scan (Linux/Pi), then falls back to parsing the system ARP cache.
Returns list of {mac, ip, hostname} dicts.
"""
import asyncio
import ipaddress
import logging
import re
import socket
import subprocess
from typing import List, Optional

log = logging.getLogger("guardhome.scanner")


async def scan_lan() -> List[dict]:
    """Run ARP scan and return list of discovered devices."""
    devices = []
    try:
        devices = await _arp_scan_tool()
    except Exception:
        pass

    if not devices:
        try:
            devices = await _arp_cache_scan()
        except Exception as exc:
            log.warning("ARP cache scan failed: %s", exc)

    # Attempt reverse DNS for hostnames
    for d in devices:
        if not d.get("hostname") and d.get("ip"):
            d["hostname"] = await _reverse_dns(d["ip"])

    return devices


async def _arp_scan_tool() -> List[dict]:
    """Use arp-scan if available."""
    proc = await asyncio.create_subprocess_exec(
        "arp-scan", "--localnet", "--quiet",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
    lines = stdout.decode(errors="replace").splitlines()
    devices = []
    # arp-scan output: "<IP>\t<MAC>\t<Vendor>"
    for line in lines:
        parts = line.split("\t")
        if len(parts) >= 2:
            ip = parts[0].strip()
            mac = parts[1].strip().upper()
            if _is_valid_ip(ip) and _is_valid_mac(mac):
                devices.append({"ip": ip, "mac": mac, "hostname": None})
    return devices


async def _arp_cache_scan() -> List[dict]:
    """Parse the OS ARP cache (works without root)."""
    proc = await asyncio.create_subprocess_exec(
        "arp", "-n",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
    lines = stdout.decode(errors="replace").splitlines()
    devices = []
    # Linux arp -n: "IP  HW type  Flags  HW address  Mask  Device"
    mac_pattern = re.compile(r"([0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}")
    ip_pattern  = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
    for line in lines:
        ip_match  = ip_pattern.search(line)
        mac_match = mac_pattern.search(line)
        if ip_match and mac_match:
            ip  = ip_match.group()
            mac = mac_match.group().upper().replace("-", ":")
            if _is_valid_ip(ip) and _is_valid_mac(mac):
                devices.append({"ip": ip, "mac": mac, "hostname": None})
    return devices


async def _reverse_dns(ip: str) -> Optional[str]:
    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, socket.gethostbyaddr, ip),
            timeout=2,
        )
        return result[0]
    except Exception:
        return None


def _is_valid_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private
    except ValueError:
        return False


def _is_valid_mac(mac: str) -> bool:
    return bool(re.match(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$", mac))
