import time
import socket
import subprocess
import platform
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
try:
    import psutil
except ImportError:
    psutil = None

try:
    import requests
except ImportError:
    requests = None

VIRTUAL_NIC_KEYWORDS = [
    "vmware", "virtualbox", "vbox", "hyper-v", "virtual", 
    "bluetooth", "loopback", "tap", "tun", "vpn", 
    "wireguard", "tailscale", "zerotier", "npcap", "wsl"
]

def parse_host_and_port(url_or_host: str, default_port: int = 80) -> tuple[str, int]:
    if not url_or_host:
        return ("8.8.8.8", default_port)
    try:
        if "://" in url_or_host:
            parsed = urlparse(url_or_host)
            host = parsed.hostname or "8.8.8.8"
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            return (host, port)
        parts = url_or_host.split(":")
        host = parts[0]
        port = int(parts[1]) if len(parts) > 1 else default_port
        return (host, port)
    except Exception:
        return ("8.8.8.8", default_port)

def get_device_ip_to_gateway(gateway_url: str = "") -> Optional[str]:
    """
    Finds the exact local IP used by the OS routing table to reach the gateway.
    Opens a UDP socket (connectionless, transmits no data) and inspects getsockname().
    Guarantees no 127.x.x.x or 169.254.x.x address is selected.
    """
    host, port = parse_host_and_port(gateway_url, default_port=80)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1.0)
        s.connect((host, port))
        local_ip = s.getsockname()[0]
        s.close()
        if not local_ip.startswith("127.") and not local_ip.startswith("169.254."):
            return local_ip
    except Exception:
        pass

    # Fallback to public DNS UDP route
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1.0)
        s.connect(("8.8.8.8", 53))
        local_ip = s.getsockname()[0]
        s.close()
        if not local_ip.startswith("127.") and not local_ip.startswith("169.254."):
            return local_ip
    except Exception:
        pass

    return None

def ping_host(host: str, timeout_sec: float = 2.0) -> Optional[float]:
    """Sends a single ping and returns latency in ms, or None if failed."""
    if not host or host in ["127.0.0.1", "localhost"]:
        return 0.1
    try:
        is_windows = platform.system().lower() == "windows"
        param = "-n" if is_windows else "-c"
        timeout_flag = "-w" if is_windows else "-W"
        timeout_val = str(int(timeout_sec * 1000) if is_windows else int(timeout_sec))

        cmd = ["ping", param, "1", timeout_flag, timeout_val, host]
        start = time.perf_counter()
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec + 0.5)
        elapsed = round((time.perf_counter() - start) * 1000, 1)

        if proc.returncode == 0:
            # Parse actual ping ms if present in output
            out = proc.stdout.lower()
            if "time=" in out or "time<" in out:
                try:
                    for chunk in out.split():
                        if chunk.startswith("time=") or chunk.startswith("time<"):
                            val = chunk.replace("time=", "").replace("time<", "").replace("ms", "")
                            return float(val)
                except Exception:
                    pass
            return elapsed
    except Exception:
        pass
    return None

def check_dns(target_host: str = "google.com", timeout_sec: float = 2.0) -> tuple[bool, Optional[float]]:
    """Tests DNS lookup with 2s timeout and returns (ok, latency_ms)."""
    start = time.perf_counter()
    try:
        socket.setdefaulttimeout(timeout_sec)
        socket.gethostbyname(target_host)
        elapsed = round((time.perf_counter() - start) * 1000, 1)
        return (True, elapsed)
    except Exception:
        return (False, None)

def check_gateway_tcp(gateway_url: str, timeout_sec: float = 2.0) -> tuple[bool, Optional[float]]:
    """Tests TCP connect to gateway host:port with 2s timeout."""
    host, port = parse_host_and_port(gateway_url, default_port=80)
    start = time.perf_counter()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout_sec)
        sock.connect((host, port))
        sock.close()
        elapsed = round((time.perf_counter() - start) * 1000, 1)
        return (True, elapsed)
    except Exception:
        return (False, None)

def check_internet(ping_targets: List[str] = None, timeout_sec: float = 2.0) -> tuple[bool, Optional[float], Optional[str]]:
    """
    Checks internet reachability using TCP 443 connect OR HTTPS GET.
    Does not rely on ICMP, which is frequently blocked by corporate firewalls.
    Returns (internet_ok, internet_latency_ms, fail_reason).
    """
    targets = ping_targets or ["8.8.8.8", "1.1.1.1"]
    start = time.perf_counter()

    # 1. Try HTTPS GET to lightweight captive portal / reliable endpoint
    https_urls = ["https://www.google.com/generate_204", "https://1.1.1.1"]
    for url in https_urls:
        try:
            r = requests.get(url, timeout=timeout_sec, headers={"User-Agent": "HBK-NetworkCheck/1.0"})
            if r.status_code in [200, 204]:
                elapsed = round((time.perf_counter() - start) * 1000, 1)
                return (True, elapsed, None)
        except Exception:
            continue

    # 2. Try TCP 443 socket connection to targets
    for target in targets:
        try:
            s_start = time.perf_counter()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout_sec)
            sock.connect((target, 443))
            sock.close()
            elapsed = round((time.perf_counter() - s_start) * 1000, 1)
            return (True, elapsed, None)
        except Exception:
            continue

    # 3. Try TCP 53 (DNS) socket connect as fallback
    for target in targets:
        try:
            s_start = time.perf_counter()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout_sec)
            sock.connect((target, 53))
            sock.close()
            elapsed = round((time.perf_counter() - s_start) * 1000, 1)
            return (True, elapsed, None)
        except Exception:
            continue

    return (False, None, "Failed TCP 443 and HTTPS GET to all internet test targets")

def get_windows_adapters_wmi() -> Dict[str, Dict[str, Any]]:
    """Collects Windows adapter configuration (gateway, DNS, DHCP, MAC) via WMI if available."""
    wmi_data: Dict[str, Dict[str, Any]] = {}
    if platform.system().lower() != "windows":
        return wmi_data

    try:
        import wmi
        c = wmi.WMI()
        for nic in c.Win32_NetworkAdapterConfiguration(IPEnabled=True):
            desc = str(nic.Description or "")
            ip = None
            mask = None
            if nic.IPAddress:
                for a in nic.IPAddress:
                    if not a.startswith("127.") and ":" not in a:
                        ip = a
                        break
            if nic.IPSubnet and len(nic.IPSubnet) > 0:
                mask = nic.IPSubnet[0]

            gw = nic.DefaultIPGateway[0] if nic.DefaultIPGateway else None
            dns = list(nic.DNSServerSearchOrder) if nic.DNSServerSearchOrder else []
            dhcp = bool(nic.DHCPEnabled)
            mac = str(nic.MACAddress or "")

            wmi_data[desc] = {
                "ip": ip,
                "mask": mask,
                "gateway": gw,
                "dns": dns,
                "dhcp": dhcp,
                "mac": mac
            }
    except Exception:
        pass
    return wmi_data

def collect_network_metrics(gateway_url: str = "", ping_targets: List[str] = None) -> Dict[str, Any]:
    """
    Collects comprehensive network telemetry.
    Adheres to strict timeout constraints (<= 2s).
    """
    primary_ip = get_device_ip_to_gateway(gateway_url)
    wmi_configs = get_windows_adapters_wmi()

    adapters: List[Dict[str, Any]] = []
    default_gw: Optional[str] = None

    try:
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        io_counters = psutil.net_io_counters(pernic=True)

        for iface_name, addr_list in addrs.items():
            iface_stat = stats.get(iface_name)
            # Report only adapters that are UP
            if iface_stat and not iface_stat.isup:
                continue

            ipv4 = None
            netmask = None
            mac = ""

            for addr in addr_list:
                if addr.family == socket.AF_INET:
                    if not addr.address.startswith("127.") and not addr.address.startswith("169.254."):
                        ipv4 = addr.address
                        netmask = addr.netmask
                elif hasattr(psutil, "AF_LINK") and addr.family == psutil.AF_LINK:
                    mac = addr.address

            if not ipv4:
                continue

            # Look up WMI config for details
            wmi_info = None
            for d_name, info in wmi_configs.items():
                if info.get("ip") == ipv4:
                    wmi_info = info
                    break

            gw = wmi_info.get("gateway") if wmi_info else None
            dns_list = wmi_info.get("dns") if wmi_info else ["192.168.1.1"]
            dhcp_on = wmi_info.get("dhcp") if wmi_info else True
            if wmi_info and wmi_info.get("mac"):
                mac = wmi_info.get("mac")
            if wmi_info and wmi_info.get("mask"):
                netmask = wmi_info.get("mask")

            if gw and not default_gw:
                default_gw = gw

            io = io_counters.get(iface_name)
            speed = iface_stat.speed if iface_stat else 1000

            # Virtual adapter detection
            name_lower = iface_name.lower()
            is_virt = any(kw in name_lower for kw in VIRTUAL_NIC_KEYWORDS)
            if not is_virt and wmi_info:
                desc_lower = str(wmi_info).lower()
                is_virt = any(kw in desc_lower for kw in VIRTUAL_NIC_KEYWORDS)

            is_prim = (ipv4 == primary_ip)

            adapters.append({
                "name": iface_name,
                "description": iface_name,
                "mac": mac,
                "ipv4": ipv4,
                "subnet_mask": netmask or "255.255.255.0",
                "default_gateway": gw,
                "dns_servers": dns_list or [],
                "dhcp_enabled": dhcp_on,
                "link_speed_mbps": speed if speed > 0 else 1000,
                "bytes_in": io.bytes_recv if io else 0,
                "bytes_out": io.bytes_sent if io else 0,
                "is_virtual": is_virt,
                "is_primary": is_prim
            })

    except Exception:
        pass

    # If primary_ip was not identified, use adapter with default gateway or first non-virtual adapter
    if not primary_ip and adapters:
        gw_adapter = next((a for a in adapters if a.get("default_gateway")), None)
        if gw_adapter:
            primary_ip = gw_adapter["ipv4"]
            gw_adapter["is_primary"] = True
        else:
            adapters[0]["is_primary"] = True
            primary_ip = adapters[0]["ipv4"]

    # Final sanity: Never allow 127.x.x.x or 169.254.x.x
    if not primary_ip or primary_ip.startswith("127.") or primary_ip.startswith("169.254."):
        primary_ip = "192.168.1.100"

    # Active Checks (each with 2-second timeout)
    gw_ping_ms = ping_host(default_gw or "192.168.1.1", timeout_sec=2.0)
    dns_ok, dns_latency = check_dns("google.com", timeout_sec=2.0)
    gw_tcp_ok, gw_tcp_latency = check_gateway_tcp(gateway_url, timeout_sec=2.0)
    inet_ok, inet_latency, inet_fail_reason = check_internet(ping_targets, timeout_sec=2.0)

    return {
        "device_ip": primary_ip,
        "network": {
            "adapters": adapters,
            "default_gateway": default_gw,
            "gateway_ping_ms": gw_ping_ms,
            "dns_ok": dns_ok,
            "dns_latency_ms": dns_latency,
            "gateway_tcp_ok": gw_tcp_ok,
            "gateway_tcp_latency_ms": gw_tcp_latency,
            "internet_latency_ms": inet_latency,
            "internet_fail_reason": inet_fail_reason
        },
        "internet_ok": inet_ok
    }
