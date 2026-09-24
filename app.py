import os
import threading
from flask import Flask, render_template, jsonify, request

from wifi_scanner import get_channel_statistics
from wifi_environment import WiFiEnvironment
from sarsa import SARSAAgent


app = Flask(__name__)
env = WiFiEnvironment()
agent = SARSAAgent()

# SARSA memory across submitted scans.
previous_state = None
previous_action = None

# Latest real scan received from a local Windows scanner.
latest_result = None
data_lock = threading.Lock()

# Optional shared secret. Set SCANNER_API_KEY on Render and in local_scanner.py
# for a protected upload endpoint. If empty, uploads are accepted without a key.
SCANNER_API_KEY = os.environ.get("SCANNER_API_KEY", "").strip()


def group_networks(networks):
    """Keep the strongest visible BSSID for each SSID."""
    grouped = {}

    for network in networks:
        ssid = network.get("ssid") or "Hidden Network"
        old = grouped.get(ssid)
        if old is None or network.get("signal", 0) > old.get("signal", 0):
            grouped[ssid] = network

    return list(grouped.values())


def process_scan(raw_networks):
    """Turn submitted real Wi-Fi measurements into a SARSA recommendation."""
    global previous_state, previous_action

    networks = group_networks(raw_networks)
    statistics = get_channel_statistics(raw_networks)

    enriched = []
    candidates = []

    for network in networks:
        ssid = network["ssid"]
        quality = env.network_quality(network, statistics)
        candidates.append(ssid)

        item = dict(network)
        item["quality"] = quality
        item["channel_load"] = round(
            env.calculate_channel_load(
                statistics, network.get("channel", 0)
            ) * 100,
            2,
        )
        enriched.append(item)

    qualities = [n["quality"] for n in enriched]
    state = env.overall_state(qualities)

    # SARSA transition: reward the previously selected network using
    # its newly measured quality, then bootstrap from the next action.
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

    # Current measured quality remains dominant.
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

    return {
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
    }


def authorized_upload():
    """Check the optional API key for local scanner uploads."""
    if not SCANNER_API_KEY:
        return True

    supplied = request.headers.get("X-Scanner-Key", "")
    return supplied == SCANNER_API_KEY


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/scan", methods=["GET", "POST"])
def scan():
    """
    POST: receive a real scan from local_scanner.py.
    GET: return the most recently received scan.
    """
    global latest_result

    if request.method == "POST":
        if not authorized_upload():
            return jsonify({
                "success": False,
                "error": "Invalid scanner API key."
            }), 401

        payload = request.get_json(silent=True) or {}
        raw_networks = payload.get("networks")

        if not isinstance(raw_networks, list):
            return jsonify({
                "success": False,
                "error": "JSON must contain a 'networks' list."
            }), 400

        result = process_scan(raw_networks)
        with data_lock:
            latest_result = result

        return jsonify(result)

    with data_lock:
        if latest_result is None:
            return jsonify({
                "success": False,
                "available": False,
                "error": (
                    "No local Wi-Fi scan has been uploaded yet. "
                    "Run local_scanner.py on the Windows computer first."
                ),
            })

        return jsonify({
            **latest_result,
            "available": True,
        })


@app.route("/api/qtable")
def qtable():
    return jsonify({"q_table": agent.q_table})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
