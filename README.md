# AI-Based Best Wi-Fi Network Recommendation

A Flask website that scans nearby Windows Wi-Fi networks and uses a SARSA reinforcement-learning agent to learn from measured network quality.

## What changed

- The system recommends a **Wi-Fi network**, not a Wi-Fi channel.
- Every scan uses real Windows `netsh wlan show networks mode=bssid` data.
- All channels reported by Windows are included.
- Current measured quality is the dominant part of the recommendation.
- SARSA Q-values provide a smaller learning component.
- Old Q-values cannot override a clearly better current measurement.
- Learning is automatically performed during scans; there is no separate "Learn From Real Wi-Fi" button.
- Q-values are saved in `q_table.json`.

## Important

"Estimated Quality" is calculated from Wi-Fi signal and estimated local congestion. It is **not** an internet-speed test.

## Run

```powershell
cd C:\Users\HP\Downloads\adaptive_wifi_sarsa
pip install -r requirements.txt
python app.py
```

Open:

http://127.0.0.1:5000

For another device on the same network, use the PC's LAN address, for example:

http://YOUR-PC-IP:5000
