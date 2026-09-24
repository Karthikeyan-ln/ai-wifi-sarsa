class WiFiEnvironment:
    """Convert real scan measurements into congestion and quality estimates."""

    states = ["Low", "Medium", "High"]

    @staticmethod
    def calculate_channel_load(channel_statistics, channel):
        data = channel_statistics.get(
            channel,
            {"network_count": 0, "average_signal": 0},
        )

        count_score = min(data["network_count"] / 5.0, 1.0)
        signal_score = data["average_signal"] / 100.0

        # More nearby networks and stronger nearby signals imply more contention.
        load = 0.70 * count_score + 0.30 * signal_score
        return max(0.0, min(load, 1.0))

    def get_channel_loads(self, channel_statistics):
        return {
            channel: round(self.calculate_channel_load(channel_statistics, channel) * 100, 2)
            for channel in sorted(channel_statistics)
        }

    def network_quality(self, network, channel_statistics):
        signal = max(0, min(int(network.get("signal", 0)), 100))
        channel = network.get("channel", 0)

        load = self.calculate_channel_load(channel_statistics, channel)
        congestion_score = 100.0 * (1.0 - load)

        # Current measurement is intentionally dominant.
        quality = 0.75 * signal + 0.25 * congestion_score
        return round(max(0.0, min(quality, 100.0)), 2)

    def overall_state(self, qualities):
        if not qualities:
            return 0
        average_quality = sum(qualities) / len(qualities)
        if average_quality < 40:
            return 0
        if average_quality < 70:
            return 1
        return 2
