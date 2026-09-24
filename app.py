import os
import threading

from flask import Flask, render_template, jsonify, request

from wifi_scanner import get_channel_statistics
from wifi_environment import WiFiEnvironment
from sarsa import SARSAAgent


app = Flask(__name__)

# ---------------------------------------------------------
# SARSA SETUP
# ---------------------------------------------------------

env = WiFiEnvironment()
agent = SARSAAgent()

# SARSA memory across submitted scans
previous_state = None
previous_action = None

# Latest scan received from local Windows scanner
latest_result = None

# Thread safety
data_lock = threading.Lock()

# Optional API key
SCANNER_API_KEY = os.environ.get("SCANNER_API_KEY", "").strip()


# ---------------------------------------------------------
# PROCESS WIFI SCAN
# ---------------------------------------------------------

def process_scan(raw_networks):
    """
    Process ALL Wi-Fi networks received from local_scanner.py.

    Important:
    We do NOT remove duplicate SSIDs.
    Every detected Wi-Fi entry is kept.
    """

    global previous_state, previous_action

    # -----------------------------------------------------
    # KEEP EVERY DETECTED NETWORK
    # -----------------------------------------------------

    networks = []

    for network in raw_networks:
        if not isinstance(network, dict):
            continue

        item = dict(network)

        # Default values
        item["ssid"] = item.get("ssid") or "Hidden Network"
        item["signal"] = item.get("signal", 0)
        item["channel"] = item.get("channel", 0)

        networks.append(item)

    # -----------------------------------------------------
    # CHANNEL STATISTICS
    # -----------------------------------------------------

    statistics = get_channel_statistics(raw_networks)

    enriched = []
    candidates = []

    # -----------------------------------------------------
    # ANALYZE EVERY NETWORK
    # -----------------------------------------------------

    for index, network in enumerate(networks):

        ssid = network["ssid"]

        quality = env.network_quality(
            network,
            statistics
        )

        # Make candidate IDs unique internally.
        # This prevents two networks with the same SSID
        # from causing problems in SARSA.
        candidate_id = f"{ssid}__{index}"

        candidates.append(candidate_id)

        # Create a copy for the website
        item = dict(network)

        item["quality"] = quality

        # Channel load
        item["channel_load"] = round(
            env.calculate_channel_load(
                statistics,
                network.get("channel", 0)
            ) * 100,
            2
        )

        # Internal SARSA ID
        item["_sarsa_id"] = candidate_id

        enriched.append(item)

    # -----------------------------------------------------
    # EMPTY SCAN
    # -----------------------------------------------------

    if not enriched:
        return {
            "success": True,
            "networks": [],
            "raw_network_count": len(raw_networks),
            "network_count": 0,
            "channel_statistics": statistics,
            "channel_loads": env.get_channel_loads(statistics),
            "state": "No Networks",
            "recommended_network": None,
            "learning": {
                "alpha": agent.alpha,
                "gamma": agent.gamma,
                "epsilon": agent.epsilon,
                "memory_entries": len(agent.q_table),
            },
        }

    # -----------------------------------------------------
    # CALCULATE STATE
    # -----------------------------------------------------

    qualities = [
        n["quality"]
        for n in enriched
    ]

    state = env.overall_state(qualities)

    # -----------------------------------------------------
    # SARSA TRANSITION
    # -----------------------------------------------------

    if (
        previous_action is not None
        and previous_state is not None
    ):

        # If previous action is still available
        if previous_action in candidates:

            next_action = agent.choose_action(
                state,
                candidates,
                explore=True
            )

            previous_reward = 0

            for network in enriched:
                if network["_sarsa_id"] == previous_action:
                    previous_reward = network["quality"]
                    break

            agent.update(
                previous_state,
                previous_action,
                previous_reward,
                state,
                next_action
            )

        else:

            next_action = agent.choose_action(
                state,
                candidates,
                explore=True
            )

    else:

        next_action = agent.choose_action(
            state,
            candidates,
            explore=True
        )

    # -----------------------------------------------------
    # CALCULATE Q VALUES AND RECOMMENDATION SCORE
    # -----------------------------------------------------

    for item in enriched:

        q = agent.get_q(
            state,
            item["_sarsa_id"]
        )

        item["q_value"] = round(
            q,
            2
        )

        q_normalized = (
            max(
                0.0,
                min(
                    q / 100.0,
                    1.0
                )
            )
            * 100
        )

        item["recommendation_score"] = round(
            0.85 * item["quality"]
            +
            0.15 * q_normalized,
            2
        )

    # -----------------------------------------------------
    # SORT ALL NETWORKS
    # -----------------------------------------------------

    enriched.sort(
        key=lambda n: (
            n["recommendation_score"],
            n["quality"]
        ),
        reverse=True
    )

    # -----------------------------------------------------
    # BEST NETWORK
    # -----------------------------------------------------

    recommended = (
        enriched[0]
        if enriched
        else None
    )

    # -----------------------------------------------------
    # SARSA MEMORY
    # -----------------------------------------------------

    previous_state = state

    if recommended:

        previous_action = (
            recommended["_sarsa_id"]
        )

    else:

        previous_action = None

    # -----------------------------------------------------
    # REMOVE INTERNAL FIELD BEFORE SENDING TO WEBSITE
    # -----------------------------------------------------

    for item in enriched:

        item.pop(
            "_sarsa_id",
            None
        )

    # -----------------------------------------------------
    # SAVE SARSA
    # -----------------------------------------------------

    agent.save()

    # -----------------------------------------------------
    # RETURN RESULT
    # -----------------------------------------------------

    return {
        "success": True,

        # ALL networks
        "networks": enriched,

        # Number received from scanner
        "raw_network_count": len(raw_networks),

        # Number displayed
        "network_count": len(enriched),

        # Channel information
        "channel_statistics": statistics,

        "channel_loads": env.get_channel_loads(
            statistics
        ),

        # SARSA state
        "state": env.states[state],

        # Best network
        "recommended_network": recommended,

        # SARSA information
        "learning": {
            "alpha": agent.alpha,
            "gamma": agent.gamma,
            "epsilon": agent.epsilon,
            "memory_entries": len(agent.q_table),
        },
    }


# ---------------------------------------------------------
# API KEY CHECK
# ---------------------------------------------------------

def authorized_upload():

    if not SCANNER_API_KEY:
        return True

    supplied = request.headers.get(
        "X-Scanner-Key",
        ""
    )

    return supplied == SCANNER_API_KEY


# ---------------------------------------------------------
# HOME PAGE
# ---------------------------------------------------------

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# ---------------------------------------------------------
# WIFI SCAN API
# ---------------------------------------------------------

@app.route(
    "/api/scan",
    methods=["GET", "POST"]
)
def scan():

    global latest_result

    # =====================================================
    # RECEIVE NEW SCAN
    # =====================================================

    if request.method == "POST":

        if not authorized_upload():

            return jsonify({
                "success": False,
                "error": "Invalid scanner API key."
            }), 401

        payload = request.get_json(
            silent=True
        ) or {}

        raw_networks = payload.get(
            "networks"
        )

        # -------------------------------------------------
        # VALIDATE
        # -------------------------------------------------

        if not isinstance(
            raw_networks,
            list
        ):

            return jsonify({
                "success": False,
                "error": (
                    "JSON must contain "
                    "a 'networks' list."
                )
            }), 400

        # -------------------------------------------------
        # PROCESS ALL NETWORKS
        # -------------------------------------------------

        result = process_scan(
            raw_networks
        )

        # -------------------------------------------------
        # SAVE LATEST RESULT
        # -------------------------------------------------

        with data_lock:

            latest_result = result

        return jsonify(
            result
        )

    # =====================================================
    # GET LAST SCAN
    # =====================================================

    with data_lock:

        if latest_result is None:

            return jsonify({
                "success": False,
                "available": False,
                "error": (
                    "No local Wi-Fi scan "
                    "has been uploaded yet. "
                    "Run local_scanner.py "
                    "on the Windows computer first."
                )
            })

        return jsonify({
            **latest_result,
            "available": True
        })


# ---------------------------------------------------------
# SARSA Q-TABLE
# ---------------------------------------------------------

@app.route("/api/qtable")
def qtable():

    return jsonify({
        "q_table": agent.q_table
    })


# ---------------------------------------------------------
# RUN FLASK
# ---------------------------------------------------------

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
