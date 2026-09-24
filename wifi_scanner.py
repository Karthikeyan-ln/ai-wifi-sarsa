import subprocess
import re


def scan_wifi():
    """Scan nearby Wi-Fi networks using Windows netsh."""
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "networks", "mode=bssid"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=15,
        )

        output = result.stdout
        if not output:
            return []

        networks = []
        current_ssid = None
        current_authentication = None
        current_encryption = None
        current_bssid = None
        current_signal = None
        current_channel = None

        def save_current():
            if current_bssid is not None:
                networks.append({
                    "ssid": current_ssid or "Hidden Network",
                    "bssid": current_bssid,
                    "signal": current_signal if current_signal is not None else 0,
                    "channel": current_channel if current_channel is not None else 0,
                    "authentication": current_authentication,
                    "encryption": current_encryption,
                })

        for raw_line in output.splitlines():
            line = raw_line.strip()

            m = re.match(r"SSID\s+\d+\s*:\s*(.*)", line)
            if m:
                save_current()
                current_ssid = m.group(1).strip()
                current_authentication = None
                current_encryption = None
                current_bssid = None
                current_signal = None
                current_channel = None
                continue

            m = re.match(r"Authentication\s*:\s*(.*)", line)
            if m:
                current_authentication = m.group(1).strip()
                continue

            m = re.match(r"Encryption\s*:\s*(.*)", line)
            if m:
                current_encryption = m.group(1).strip()
                continue

            m = re.match(r"BSSID\s+\d+\s*:\s*(.*)", line)
            if m:
                save_current()
                current_bssid = m.group(1).strip()
                current_signal = None
                current_channel = None
                continue

            m = re.match(r"Signal\s*:\s*(\d+)%?", line)
            if m:
                current_signal = int(m.group(1))
                continue

            m = re.match(r"Channel\s*:\s*(\d+)", line)
            if m:
                current_channel = int(m.group(1))
                continue

        save_current()
        return networks

    except Exception as exc:
        print("Wi-Fi scanning error:", exc)
        return []


def get_channel_statistics(networks):
    """Build statistics for every channel reported by the scan."""
    buckets = {}

    for network in networks:
        channel = network.get("channel")
        signal = network.get("signal", 0)

        if channel in (None, 0):
            continue

        bucket = buckets.setdefault(channel, [])
        bucket.append(signal or 0)

    statistics = {}
    for channel, signals in sorted(buckets.items()):
        statistics[channel] = {
            "network_count": len(signals),
            "average_signal": round(sum(signals) / len(signals), 2),
        }

    return statistics
