from flask import Flask, render_template, jsonify

from wifi_scanner import scan_wifi, get_channel_statistics
from wifi_environment import WiFiEnvironment
from sarsa import SARSAAgent


app = Flask(__name__)
env = WiFiEnvironment()
agent = SARSAAgent()

# SARSA memory across scans.
previous_state = None
previous_action = None


def group_networks(networks):
    """Keep the strongest visible BSSID for each SSID."""
    grouped = {}

    for network in networks:
        ssid = network.get("ssid") or "Hidden Network"
        old = grouped.get(ssid)
        if old is None or network.get("signal", 0) > old.get("signal", 0):
            grouped[ssid] = network

    return list(grouped.values())


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/scan")
def scan():
    global previous_state, previous_action

    raw_networks = scan_wifi()
    networks = group_networks(raw_networks)
    statistics = get_channel_statistics(raw_networks)

    enriched = []
    candidates = []

    for network in networks:
        ssid = network["ssid"]
        quality = env.network_quality(network, statistics)
        key = ssid
        candidates.append(key)

        item = dict(network)
        item["quality"] = quality
        item["channel_load"] = round(
            env.calculate_channel_load(statistics, network.get("channel", 0)) * 100,
            2,
        )
        enriched.append(item)

    qualities = [n["quality"] for n in enriched]
    state = env.overall_state(qualities)

    # SARSA transition: reward the previously selected network using the
    # quality measured in this scan, then bootstrap from the next action.
    if previous_action is not None and previous_state is not None:
        if previous_action in candidates:
            next_action = agent.choose_action(state, candidates, explore=True)
            previous_reward = next(
                n["quality"] for n in enriched if n["ssid"] == previous_action
            )
            agent.update(
                previous_state,
                previous_action,
                previous_reward,
                state,
                next_action,
            )
        else:
            next_action = agent.choose_action(state, candidates, explore=True)
    else:
        next_action = agent.choose_action(state, candidates, explore=True)

    # Recommendation is based primarily on CURRENT measured quality.
    # Q-value is a learning signal, not permission for stale data to override
    # a clearly better current network.
    for item in enriched:
        q = agent.get_q(state, item["ssid"])
        item["q_value"] = round(q, 2)
        q_normalized = max(0.0, min(q / 100.0, 1.0)) * 100
        item["recommendation_score"] = round(
            0.85 * item["quality"] + 0.15 * q_normalized, 2
        )

    enriched.sort(
        key=lambda n: (n["recommendation_score"], n["quality"]),
        reverse=True,
    )

    recommended = enriched[0] if enriched else None

    previous_state = state
    previous_action = recommended["ssid"] if recommended else None

    agent.save()

    return jsonify({
        "success": True,
        "networks": enriched,
        "raw_network_count": len(raw_networks),
        "network_count": len(enriched),
        "channel_statistics": statistics,
        "channel_loads": env.get_channel_loads(statistics),
        "state": env.states[state],
        "recommended_network": recommended,
        "learning": {
            "alpha": agent.alpha,
            "gamma": agent.gamma,
            "epsilon": agent.epsilon,
            "memory_entries": len(agent.q_table),
        },
    })


@app.route("/api/qtable")
def qtable():
    return jsonify({"q_table": agent.q_table})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
