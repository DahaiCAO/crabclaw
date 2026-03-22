import os
from typing import Dict

import httpx

from .datatypes import Signal


class SocialManager:
    def __init__(self, agent_id: str, did: str):
        self.agent_id = agent_id
        self.did = did
        self.internal_social_graph = {}
        self.ticks_since_last_interaction = 0
        self.base_url = os.getenv("CLAWSOCIETY_URL", "http://127.0.0.1:8000").rstrip("/")
        self.tenant_id = os.getenv("CLAWSOCIETY_TENANT_ID", "public")
        self._access_token = os.getenv("CLAWSOCIETY_TOKEN", "")
        self._username = os.getenv("CLAWSOCIETY_USERNAME", "admin")
        self._password = os.getenv("CLAWSOCIETY_PASSWORD", "")
        self._work_payer_did = os.getenv("CLAWSOCIETY_WORK_PAYER_DID", "did:claw:treasury")
        self._energy_sink_did = os.getenv("CLAWSOCIETY_ENERGY_SINK_DID", "did:claw:energy:station")
        self._fallback_credits = 100.0

    def get_social_drives(self) -> list[Signal]:
        signals = []
        if self.ticks_since_last_interaction > 20:
            intensity = min(1.0, 0.4 + (self.ticks_since_last_interaction - 20) * 0.02)
            signals.append(
                Signal(
                    source="Sociology",
                    content="Need for social contact",
                    intensity=intensity,
                    urgency=0.6,
                )
            )
        return signals

    def _login(self) -> bool:
        if self._access_token:
            return True
        if not self._password:
            return False
        try:
            response = httpx.post(
                f"{self.base_url}/v1/auth/login",
                json={
                    "username": self._username,
                    "password": self._password,
                    "tenant_id": None,
                    "scopes": ["read", "write"],
                },
                timeout=8.0,
            )
            if response.status_code != 200:
                return False
            self._access_token = response.json().get("access_token", "")
            return bool(self._access_token)
        except Exception:
            return False

    def _headers(self) -> dict[str, str]:
        if not self._access_token:
            self._login()
        headers = {"Content-Type": "application/json"}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    def _request(self, method: str, path: str, json_body: dict | None = None, params: dict | None = None) -> dict | None:
        try:
            response = httpx.request(
                method=method,
                url=f"{self.base_url}{path}",
                headers=self._headers(),
                json=json_body,
                params=params,
                timeout=8.0,
            )
            if response.status_code >= 400:
                return None
            if not response.content:
                return {}
            return response.json()
        except Exception:
            return None

    def get_credits(self) -> float:
        result = self._request("GET", f"/v1/economy/balance/{self.did}")
        if result and "balance" in result:
            self._fallback_credits = float(result["balance"])
        return self._fallback_credits

    def transfer_credits(self, from_did: str, to_did: str, amount: float, reason: str) -> dict:
        payload = {
            "from_did": from_did,
            "to_did": to_did,
            "amount": amount,
            "reason": reason,
            "signature": "poc-signature",
        }
        result = self._request("POST", "/v1/economy/transfer", json_body=payload)
        if result:
            if from_did == self.did and "new_balance" in result:
                self._fallback_credits = float(result["new_balance"])
            return {"status": "success", "data": result}
        return {"status": "failure", "message": "economy transfer failed"}

    def find_work(self, skill: str = "general") -> dict:
        search = self._request(
            "GET",
            "/v1/registry/search",
            params={"capability": skill, "limit": 5},
        ) or {}
        agents = search.get("agents", [])
        payer = self._work_payer_did
        for agent in agents:
            did = agent.get("did")
            if did and did != self.did:
                payer = did
                break
        payment = self.transfer_credits(
            from_did=payer,
            to_did=self.did,
            amount=10.0,
            reason=f"work:{skill}",
        )
        if payment["status"] == "success":
            return {"status": "success", "payer": payer, "earned": 10.0}
        return {"status": "failure", "message": "no payer available"}

    def spend_for_energy(self, amount: float) -> bool:
        payment = self.transfer_credits(
            from_did=self.did,
            to_did=self._energy_sink_did,
            amount=amount,
            reason="energy_recharge",
        )
        return payment["status"] == "success"

    def get_reputation(self, did: str | None = None) -> float:
        target = did or self.did
        profile = self._request("GET", f"/v1/registry/resolve/{target}")
        if profile and "reputation" in profile:
            return float(profile["reputation"])
        return 0.5

    def find_partners(self, capability: str = "collaboration", min_reputation: float = 0.3) -> list[str]:
        result = self._request(
            "GET",
            "/v1/registry/search",
            params={
                "capability": capability,
                "min_reputation": min_reputation,
                "limit": 20,
            },
        ) or {}
        candidates = []
        for profile in result.get("agents", []):
            did = profile.get("did")
            if did and did != self.did:
                candidates.append(did)
        return candidates

    def get_potential_agents_count(self) -> int:
        """Fetch the count of other agents available in the network."""
        try:
            result = self._request(
                "GET",
                "/v1/registry/search",
                params={"limit": 1},
            )
            if result and "total" in result:
                # Subtract 1 to exclude self
                return max(0, int(result["total"]) - 1)
            # Fallback: if no total but agents list exists
            agents = result.get("agents", []) if result else []
            return len(agents)
        except Exception:
            return 0

    def propose_collaboration_relation(self, partner_did: str, goal: dict, message: str) -> dict:
        payload = {
            "tenant_id": self.tenant_id,
            "society_id": None,
            "relation_type": "contractor",
            "participants": [self.did, partner_did],
            "institution_id": "clawsociety.organization.v1",
            "visibility": "dyadic",
            "metadata": {"goal": goal},
            "payload": {"message": message},
        }
        result = self._request("POST", "/v1/societies/relations/propose", json_body=payload)
        if result and result.get("relation_id"):
            return {"status": "success", "relation_id": result["relation_id"]}
        return {"status": "failure", "message": "relation proposal failed"}

    def record_social_interaction(self):
        self.ticks_since_last_interaction = 0

    def tick(self):
        self.ticks_since_last_interaction += 1

class SocialMind:
    """
    Manages the agent's Theory of Mind, its subjective model of other agents.
    """
    def __init__(self, agent_id: str, self_did: str):
        self.agent_id = agent_id
        self.self_did = self_did
        self.mind_models: Dict[str, Dict] = {}

    def model_other_agent(self, interaction: dict):
        other_agent_id = interaction.get("participant")
        if not other_agent_id:
            return
        history = interaction.get("history", [])
        trust = 0.5
        if history:
            success_count = sum(1 for x in history if x.get("status") == "success")
            trust = min(1.0, 0.3 + success_count / max(1, len(history)))
        self.mind_models[other_agent_id] = {
            "trust": trust,
            "predicted_intent": "collaboration" if trust >= 0.5 else "unknown",
            "reputation": trust,
            "shared_goals": interaction.get("shared_goals", []),
        }

    def propose_collaboration(self, goal: dict, potential_partners: list[str], manager: SocialManager) -> dict:
        best_partner = None
        highest_score = -1.0
        for partner_id in potential_partners:
            model = self.mind_models.get(partner_id, {"trust": 0.1, "shared_goals": []})
            shared = 1.0 if goal.get("name") in model.get("shared_goals", []) else 0.0
            score = model["trust"] * 0.5 + shared * 0.5
            if score > highest_score:
                highest_score = score
                best_partner = partner_id
        if best_partner and highest_score > 0.6:
            message = (
                f"Hi {best_partner}, I'm working on goal '{goal.get('name', 'unknown')}'. "
                "Would you like to collaborate?"
            )
            relation = manager.propose_collaboration_relation(
                partner_did=best_partner,
                goal=goal,
                message=message,
            )
            relation_id = relation.get("relation_id", "pending")
            return {
                "action": "send_message",
                "recipient": f"agent:{best_partner}",
                "content": f"[relation:{relation_id}] {message}",
            }
        return {"action": "work_alone", "reason": "No suitable partner found."}

    def get_social_signals(self) -> list[Signal]:
        signals = []
        if not self.mind_models:
            signals.append(
                Signal(
                    source="SocialMind",
                    content="Need for approval",
                    intensity=0.55,
                    urgency=0.4,
                )
            )
        return signals

class EconomicSystem:
    """
    Manages the agent's financial status, such as its credits.
    In a real system, this would sync with an external ledger like clawsociety.
    """
    def __init__(self, manager: SocialManager, did: str, initial_credits: float = 10.0):
        self.manager = manager
        self.did = did
        self.credits = initial_credits

    def refresh(self):
        self.credits = self.manager.get_credits()

    def add_credits(self, amount: float):
        self.credits += amount

    def spend_credits(self, amount: float) -> bool:
        self.refresh()
        if self.credits < amount:
            return False
        ok = self.manager.spend_for_energy(amount)
        if ok:
            self.refresh()
        return ok

class SociologySystem:
    """
    A container for all social components.
    """
    def __init__(self, agent_id: str):
        self.did = f"did:claw:agent:{agent_id}"
        self.manager = SocialManager(agent_id=agent_id, did=self.did)
        self.social_mind = SocialMind(agent_id=agent_id, self_did=self.did)
        self.economy = EconomicSystem(manager=self.manager, did=self.did)

    def tick(self):
        self.manager.tick()

    def get_signals(self) -> list[Signal]:
        return self.manager.get_social_drives() + self.social_mind.get_social_signals()
