import json
from pathlib import Path
import numpy as np


class SARSAAgent:
    """
    SARSA for dynamic Wi-Fi choices.

    State:
        0 = Low overall quality
        1 = Medium overall quality
        2 = High overall quality

    Action:
        A currently visible Wi-Fi network, identified by SSID.
    """

    def __init__(
        self,
        learning_rate=0.20,
        discount_factor=0.80,
        epsilon=0.10,
        storage_file="q_table.json",
    ):
        self.alpha = learning_rate
        self.gamma = discount_factor
        self.epsilon = epsilon
        self.storage_file = Path(storage_file)
        self.q_table = self._load()

    def _load(self):
        if not self.storage_file.exists():
            return {}
        try:
            return json.loads(self.storage_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save(self):
        self.storage_file.write_text(
            json.dumps(self.q_table, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def state_from_quality(quality):
        if quality < 40:
            return 0
        if quality < 70:
            return 1
        return 2

    @staticmethod
    def _key(state, network_key):
        return f"{state}|{network_key}"

    def get_q(self, state, network_key):
        return float(self.q_table.get(self._key(state, network_key), 0.0))

    def choose_action(self, state, candidates, explore=True):
        if not candidates:
            return None

        if explore and np.random.random() < self.epsilon:
            return candidates[np.random.randint(len(candidates))]

        values = [self.get_q(state, c) for c in candidates]
        max_value = max(values)
        best = [c for c, value in zip(candidates, values) if value == max_value]
        return best[np.random.randint(len(best))]

    def update(self, state, action, reward, next_state, next_action):
        if action is None:
            return

        current_q = self.get_q(state, action)
        next_q = 0.0 if next_action is None else self.get_q(next_state, next_action)

        target = reward + self.gamma * next_q
        new_q = current_q + self.alpha * (target - current_q)
        self.q_table[self._key(state, action)] = round(float(new_q), 4)

    def current_q_values(self, state, candidates):
        return {c: round(self.get_q(state, c), 2) for c in candidates}
