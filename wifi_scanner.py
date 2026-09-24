import subprocess
import re


def scan_wifi():
    """Scan ALL nearby Wi-Fi BSSIDs using Windows netsh."""

    try:
        result = subprocess.run(
            [
                "netsh",
                "wlan",
                "show",
                "networks",
                "mode=bssid",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=15,
        )

        output = result.stdout

        if not output:
            print("No Wi-Fi scan output received.")
            return []

        networks = []

        current_ssid = None
        current_authentication = None
        current_encryption = None

        current_bssid = None
        current_signal = None
        current_channel = None

        # --------------------------------------------------
        # Save current BSSID
        # --------------------------------------------------

        def save_current():

            if current_bssid is None:
                return

            networks.append({
                "ssid": current_ssid or "Hidden Network",
                "bssid": current_bssid,
                "signal": (
                    current_signal
                    if current_signal is not None
                    else 0
                ),
                "channel": (
                    current_channel
                    if current_channel is not None
                    else 0
                ),
                "authentication": current_authentication,
                "encryption": current_encryption,
            })

        # --------------------------------------------------
        # Parse netsh output
        # --------------------------------------------------

        for raw_line in output.splitlines():

            line = raw_line.strip()

            if not line:
                continue

            # ==============================================
            # SSID
            # ==============================================

            match = re.match(
                r"^SSID\s+\d+\s*:\s*(.*)$",
                line,
                re.IGNORECASE,
            )

            if match:

                # Save previous BSSID
                save_current()

                current_ssid = match.group(1).strip()

                if not current_ssid:
                    current_ssid = "Hidden Network"

                current_authentication = None
                current_encryption = None

                current_bssid = None
                current_signal = None
                current_channel = None

                continue

            # ==============================================
            # AUTHENTICATION
            # ==============================================

            match = re.match(
                r"^Authentication\s*:\s*(.*)$",
                line,
                re.IGNORECASE,
            )

            if match:

                current_authentication = (
                    match.group(1).strip()
                )

                continue

            # ==============================================
            # ENCRYPTION
            # ==============================================

            match = re.match(
                r"^Encryption\s*:\s*(.*)$",
                line,
                re.IGNORECASE,
            )

            if match:

                current_encryption = (
                    match.group(1).strip()
                )

                continue

            # ==============================================
            # BSSID
            # ==============================================

            match = re.match(
                r"^BSSID\s+\d+\s*:\s*(.+)$",
                line,
                re.IGNORECASE,
            )

            if match:

                # Save previous BSSID first
                save_current()

                current_bssid = (
                    match.group(1).strip()
                )

                current_signal = None
                current_channel = None

                continue

            # ==============================================
            # SIGNAL
            # ==============================================

            match = re.match(
                r"^Signal\s*:\s*(\d+)\s*%?",
                line,
                re.IGNORECASE,
            )

            if match:

                current_signal = int(
                    match.group(1)
                )

                continue

            # ==============================================
            # CHANNEL
            # ==============================================

            match = re.match(
                r"^Channel\s*:\s*(\d+)",
                line,
                re.IGNORECASE,
            )

            if match:

                current_channel = int(
                    match.group(1)
                )

                continue

        # --------------------------------------------------
        # Save final BSSID
        # --------------------------------------------------

        save_current()

        return networks

    except subprocess.TimeoutExpired:

        print("Wi-Fi scanning timed out.")
        return []

    except FileNotFoundError:

        print("ERROR: Windows netsh command not found.")
        return []

    except Exception as exc:

        print("Wi-Fi scanning error:", exc)
        return []


# ==========================================================
# CHANNEL STATISTICS
# ==========================================================

def get_channel_statistics(networks):
    """
    Build statistics for every detected Wi-Fi channel.

    Every BSSID counts as a separate network.
    """

    buckets = {}

    for network in networks:

        channel = network.get("channel")
        signal = network.get("signal", 0)

        if channel in (None, 0):
            continue

        try:
            channel = int(channel)
        except (TypeError, ValueError):
            continue

        try:
            signal = float(signal)
        except (TypeError, ValueError):
            signal = 0

        bucket = buckets.setdefault(
            channel,
            []
        )

        bucket.append(signal)

    statistics = {}

    for channel, signals in sorted(
        buckets.items()
    ):

        statistics[channel] = {
            "network_count": len(signals),

            "average_signal": round(
                sum(signals) / len(signals),
                2
            ),
        }

    return statistics


# ==========================================================
# DIRECT TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 60)
    print("WI-FI SCANNER TEST")
    print("=" * 60)

    networks = scan_wifi()

    print(
        f"\nFound {len(networks)} BSSID entries.\n"
    )

    for index, network in enumerate(
        networks,
        start=1
    ):

        print(
            f"{index}. "
            f"SSID: {network['ssid']} | "
            f"BSSID: {network['bssid']} | "
            f"Signal: {network['signal']}% | "
            f"Channel: {network['channel']} | "
            f"Authentication: {network['authentication']} | "
            f"Encryption: {network['encryption']}"
        )

    print("\nChannel statistics:")

    statistics = get_channel_statistics(
        networks
    )

    for channel, data in statistics.items():

        print(
            f"Channel {channel}: "
            f"{data['network_count']} network(s), "
            f"average signal "
            f"{data['average_signal']}%"
        )
