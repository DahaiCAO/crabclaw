"""
Component: WorldModel (Modeling System)

The agent's internal simulation of the external world. It is responsible
for prediction and causal reasoning. This is the core of the "Prediction Loop".
"""
from ..datatypes import Action


class WorldModel:
    """Predicts the outcomes of actions and understands cause-and-effect."""
    def __init__(self):
        self.causal_model: dict[str, str] = {}
        self.prediction_table = {
            "send_message": {"expected_reward": 1.0, "risk_level": 0.05, "samples": 1},
            "respond_to_message": {"expected_reward": 1.0, "risk_level": 0.05, "samples": 1},
            "recharge_self": {"expected_reward": 0.8, "risk_level": 0.4, "samples": 1},
            "work_for_credits": {"expected_reward": 0.6, "risk_level": 0.2, "samples": 1},
            "social_interaction": {"expected_reward": 0.7, "risk_level": 0.2, "samples": 1},
            "explore_environment": {"expected_reward": 0.75, "risk_level": 0.35, "samples": 1},
            "safe_mode": {"expected_reward": 0.3, "risk_level": 0.05, "samples": 1},
        }

    def predict_outcome(self, action: Action) -> dict:
        baseline = self.prediction_table.get(
            action.name,
            {"expected_reward": 0.4, "risk_level": 0.6, "samples": 1},
        )
        return {
            "outcome": "success" if baseline["expected_reward"] >= baseline["risk_level"] else "failure",
            "expected_reward": baseline["expected_reward"],
            "risk_level": baseline["risk_level"],
            "credit_change": -0.5 if action.name == "recharge_self" else 0.5 if action.name == "work_for_credits" else 0.0,
            "confidence": min(0.95, 0.5 + baseline["samples"] * 0.1),
        }

    def update_from_feedback(self, action: Action, actual_outcome: dict):
        current = self.prediction_table.get(
            action.name,
            {"expected_reward": 0.5, "risk_level": 0.5, "samples": 0},
        )
        samples = current["samples"] + 1
        actual_reward = 1.0 if actual_outcome.get("status") == "success" else 0.0
        actual_risk = 0.0 if actual_outcome.get("status") == "success" else 1.0
        current["expected_reward"] = (
            current["expected_reward"] * (samples - 1) + actual_reward
        ) / samples
        current["risk_level"] = (
            current["risk_level"] * (samples - 1) + actual_risk
        ) / samples
        current["samples"] = samples
        self.prediction_table[action.name] = current
        self.causal_model[f"{action.name}:{actual_outcome.get('status', 'unknown')}"] = (
            f"reward={current['expected_reward']:.2f},risk={current['risk_level']:.2f}"
        )

    def update_from_reality(self, action: Action, actual_outcome: dict):
        prediction = self.predict_outcome(action)
        predicted_reward = prediction.get("expected_reward", 0.5)
        actual_reward = 1.0 if actual_outcome.get("status") == "success" else 0.0
        prediction_error = abs(predicted_reward - actual_reward)
        self.update_from_feedback(action, actual_outcome)
        if prediction_error > 0.5:
            self.causal_model[f"learned:{action.name}"] = (
                f"high_prediction_error={prediction_error:.2f}"
            )
