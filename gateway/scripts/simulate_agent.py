#!/usr/bin/env python3
"""
Simulate POS Agent for HBK IT Monitoring Gateway.
Registers a simulated POS terminal and transmits synthetic heartbeats and metrics.
Supports inducing failure states (disk high, service stopped, printer offline, going silent).
"""
import sys
import time
import argparse
from datetime import datetime, timezone
import httpx

def utc_iso():
    return datetime.now(timezone.utc).isoformat()

def main():
    parser = argparse.ArgumentParser(description="HBK IT POS Agent Simulator")
    parser.add_argument("--url", default="http://localhost:8000", help="Gateway URL")
    parser.add_argument("--key", required=True, help="Store Enrollment Key (from seed.py or admin API)")
    parser.add_argument("--device-id", default="POS-SIM-01", help="Device ID to simulate")
    parser.add_argument("--mode", default="normal", 
                        choices=["normal", "disk-high", "service-down", "printer-error", "internet-down", "cpu-high", "silent"],
                        help="Telemetry mode to test specific alert triggers")
    parser.add_argument("--count", type=int, default=1, help="Number of telemetry cycles to transmit (0 = infinite)")
    parser.add_argument("--interval", type=int, default=10, help="Interval between cycles in seconds")

    args = parser.parse_args()

    client = httpx.Client(base_url=args.url.rstrip("/"), timeout=10.0)

    print("=" * 60)
    print(f" HBK POS Terminal Simulator: {args.device_id}")
    print(f" Target Gateway:            {args.url}")
    print(f" Mode:                      {args.mode}")
    print("=" * 60)

    # 1. Register Device
    print(f"[*] Registering device '{args.device_id}' with enrollment key...")
    reg_payload = {
        "enrollment_key": args.key,
        "device_id": args.device_id,
        "computer_name": f"{args.device_id}-CASHIER",
        "device_type": "POS",
        "ip_address": "192.168.1.199",
        "os_version": "Windows 11 Enterprise LTSC",
        "agent_version": "1.0.0-sim"
    }

    try:
        res = client.post("/api/v1/agent/register", json=reg_payload)
        if res.status_code != 200:
            print(f"[!] Registration failed ({res.status_code}): {res.text}")
            sys.exit(1)
        data = res.json()
        device_token = data["device_token"]
        print(f"[✓] Registration successful! Assigned Store: {data['store_code']}")
        print(f"[✓] Received device token: {device_token[:10]}...{device_token[-6:]}")
    except Exception as e:
        print(f"[!] Network error connecting to gateway: {e}")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {device_token}"}

    # If mode is silent, exit or pause to let gateway offline detector trigger
    if args.mode == "silent":
        print("[*] Mode is 'silent'. Transmitted registration. Going silent now...")
        print("[*] Gateway offline detection worker will mark this device OFFLINE in ~90s.")
        return

    # 2. Transmit Telemetry Cycles
    cycle = 0
    while True:
        cycle += 1
        print(f"\n--- Cycle {cycle} [{utc_iso()}] ---")

        # 2a. Send Heartbeat
        try:
            hb_res = client.post(
                "/api/v1/agent/heartbeat",
                headers=headers,
                json={"agent_version": "1.0.0-sim", "ip_address": "192.168.1.199"}
            )
            print(f"[✓] Heartbeat sent: HTTP {hb_res.status_code}")
        except Exception as e:
            print(f"[!] Heartbeat failed: {e}")

        # 2b. Build Metrics Payload based on mode
        disk_pct = 95.0 if args.mode == "disk-high" else 62.0
        service_state = "Stopped" if args.mode == "service-down" else "Running"
        printer_status = "Error" if args.mode == "printer-error" else "Idle"
        internet_status = False if args.mode == "internet-down" else True
        cpu_usage = 96.5 if args.mode == "cpu-high" else 24.5

        metric_payload = {
            "ts": utc_iso(),
            "cpu_pct": cpu_usage,
            "ram_pct": 58.2,
            "ram_used_mb": 4720.0,
            "disks": [
                {
                    "mount": "C:",
                    "total_gb": 238.0,
                    "used_gb": round(238.0 * (disk_pct / 100.0), 1),
                    "free_gb": round(238.0 * ((100.0 - disk_pct) / 100.0), 1),
                    "pct": disk_pct
                }
            ],
            "network": {
                "adapters": [
                    {
                        "name": "Ethernet",
                        "ip": "192.168.1.199",
                        "gateway": "192.168.1.1",
                        "dns": ["192.168.1.1"],
                        "bytes_in": 512000,
                        "bytes_out": 128000
                    }
                ],
                "gateway_ping_ms": 1.8,
                "dns_ok": True
            },
            "internet_ok": internet_status,
            "printers": [
                {
                    "name": "Epson TM-T88VI",
                    "status": printer_status,
                    "queue": 0,
                    "port": "USB001"
                }
            ],
            "services": [
                {
                    "name": "Print Spooler",
                    "state": service_state
                },
                {
                    "name": "HBK POS Retail Core",
                    "state": "Running"
                }
            ]
        }

        # 2c. Send Metrics
        try:
            m_res = client.post("/api/v1/agent/metrics", headers=headers, json=metric_payload)
            if m_res.status_code == 200:
                print(f"[✓] Metrics ingested: HTTP 200 (CPU={cpu_usage}%, Disk={disk_pct}%, Spooler={service_state}, Printer={printer_status})")
            else:
                print(f"[!] Metrics failed ({m_res.status_code}): {m_res.text}")
        except Exception as e:
            print(f"[!] Metrics post error: {e}")

        if args.count > 0 and cycle >= args.count:
            print("\n[✓] Completed requested cycles. Exiting.")
            break

        time.sleep(args.interval)

if __name__ == "__main__":
    main()
