"""
Local Windows Wi-Fi scanner bridge.

This program runs on the Windows PC that has the real Wi-Fi adapter.
It uses netsh through wifi_scanner.py, then sends the scan results to
the public Flask server on Render.

Examples:

    python local_scanner.py --server https://ai-wifi-sarsa.onrender.com --once

Continuous mode:

    python local_scanner.py --server https://ai-wifi-sarsa.onrender.com --interval 10

If you set SCANNER_API_KEY on Render, also pass:

    python local_scanner.py --server https://ai-wifi-sarsa.onrender.com --api-key YOUR_KEY
"""

import argparse
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from wifi_scanner import scan_wifi


def upload_scan(server, networks, api_key=""):
    url = server.rstrip("/") + "/api/scan"
    payload = json.dumps({"networks": networks}).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "AI-WiFi-SARSA-Local-Scanner/1.0",
    }
    if api_key:
        headers["X-Scanner-Key"] = api_key

    req = Request(url, data=payload, headers=headers, method="POST")

    with urlopen(req, timeout=30) as response:
        body = response.read().decode("utf-8")
        return response.status, json.loads(body)


def main():
    parser = argparse.ArgumentParser(
        description="Send real Windows Wi-Fi scans to the public SARSA website."
    )
    parser.add_argument(
        "--server",
        required=True,
        help="Public Render URL, e.g. https://ai-wifi-sarsa.onrender.com",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=0,
        help="Seconds between scans. 0 means scan once.",
    )
    parser.add_argument(
        "--api-key",
        default="",
        help="Optional SCANNER_API_KEY configured on Render.",
    )
    args = parser.parse_args()

    interval = max(0, args.interval)

    while True:
        print("\nScanning nearby Wi-Fi networks...")
        networks = scan_wifi()
        print(f"Found {len(networks)} BSSID entries.")

        try:
            status, result = upload_scan(args.server, networks, args.api_key)
            print(f"Uploaded to {args.server} (HTTP {status}).")

            if result.get("success"):
                rec = result.get("recommended_network")
                if rec:
                    print(
                        f"Recommendation: {rec['ssid']} | "
                        f"Quality: {rec['quality']}% | "
                        f"Channel: {rec['channel']}"
                    )
                else:
                    print("No Wi-Fi networks were found.")
            else:
                print("Server response:", result)
        except HTTPError as exc:
            print(f"Upload failed: HTTP {exc.code}")
            try:
                print(exc.read().decode("utf-8", errors="replace"))
            except Exception:
                pass
        except URLError as exc:
            print("Could not reach the public server:", exc.reason)
        except Exception as exc:
            print("Scanner bridge error:", exc)

        if interval <= 0:
            break

        print(f"Waiting {interval} seconds before the next scan. Press Ctrl+C to stop.")
        time.sleep(interval)


if __name__ == "__main__":
    main()
