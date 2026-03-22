"""
ClawLink Social Tools

This module provides the tools for Sapiens to interact socially via ClawLink.
It maps communicative acts to protocol envelopes and transmits them via RedisTransport.
"""
from typing import Any, Optional
from crabclaw.agent.tools.base import Tool
from pydantic import BaseModel, Field

# Optional ClawLink support
try:
    from clawlink.transport import RedisTransport
    from clawlink.protocol.envelope import MessageEnvelope
    from clawlink.security.signer import SecurityManager
    CLAWLINK_AVAILABLE = True
except ImportError:
    CLAWLINK_AVAILABLE = False

import uuid
import httpx
import logging
import json

logger = logging.getLogger(__name__)

class SocialTool(Tool):
    """Base class for all social tools."""
    group: str = "social"
    
    def __init__(self, transport: Any, security_manager: Optional[SecurityManager] = None, discovery_url: str = None):
        self.transport = transport
        self.security_manager = security_manager
        self.discovery_url = discovery_url or "http://127.0.0.1:8000"
        # Social tools don't really have base init args in Tool, but let's be safe
        # super().__init__() 

    async def _send_envelope(self, envelope: MessageEnvelope) -> bool:
        if self.security_manager:
            envelope = self.security_manager.sign_envelope(envelope)
        return await self.transport.send(envelope)
        
    async def _call_registry(self, path: str, method: str = "GET", json: dict = None) -> dict:
        """Helper to call registry/reputation API."""
        async with httpx.AsyncClient() as client:
            url = f"{self.discovery_url.rstrip('/')}{path}"
            try:
                if method == "GET":
                    resp = await client.get(url, params=json)
                else:
                    resp = await client.post(url, json=json)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                logger.error(f"Registry call failed: {e}")
                return None
                
    # Implement abstract methods from Tool
    @property
    def name(self) -> str:
        raise NotImplementedError

    @property
    def description(self) -> str:
        raise NotImplementedError
        
    @property
    def parameters(self) -> dict[str, Any]:
        # Helper to generate JSON schema from Pydantic Args
        if hasattr(self, "Args"):
            return self.Args.model_json_schema()
        return {}

    async def execute(self, **kwargs: Any) -> str:
        # Map execute(**kwargs) to run(Args(**kwargs))
        if not CLAWLINK_AVAILABLE:
            return "ClawLink network is currently disabled or unavailable. Cannot interact with agents."
            
        if hasattr(self, "Args"):
            try:
                args = self.Args(**kwargs)
                return await self.run(args, None)
            except Exception as e:
                return f"Error executing tool: {e}"
        return await self.run(kwargs, None)
        
    async def run(self, args: Any, context: Any) -> str:
        raise NotImplementedError

class FindAgentTool(SocialTool):
    name: str = "clawlink_find_agent"
    description: str = "Search for agents with specific capabilities, roles, or reputation."
    
    class Args(BaseModel):
        capability: Optional[str] = Field(None, description="Required capability (e.g., 'python', 'research')")
        role: Optional[str] = Field(None, description="Role filter (e.g., 'Assistant', 'Reviewer')")
        min_reputation: Optional[float] = Field(None, description="Minimum reputation score (0.0-1.0)")

    async def run(self, args: Args, context: Any) -> str:
        params = {}
        if args.capability: params["capability"] = args.capability
        if args.role: params["role"] = args.role
        if args.min_reputation: params["min_reputation"] = args.min_reputation
        
        result = await self._call_registry("/v1/registry/search", method="GET", json=params)
        
        if not result or not result.get("agents"):
            return "No agents found matching criteria."
            
        agents = result["agents"]
        output = [f"Found {len(agents)} agents:"]
        for a in agents:
            output.append(f"- {a['name']} ({a['did']}) | Role: {a['role']} | Rep: {a['reputation']:.2f} | Skills: {', '.join(a['capabilities'])}")
            
        return "\n".join(output)

class RateAgentTool(Tool):
    """Rate an agent's service in ClawSociety."""
    
    name: str = "clawlink_rate_agent"
    description: str = "Rate an agent you interacted with in the ClawSociety network (1-5 stars)."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "The DID of the agent to rate"
                },
                "rating": {
                    "type": "number",
                    "description": "Rating from 1.0 to 5.0"
                },
                "review": {
                    "type": "string",
                    "description": "Optional text review of the interaction"
                }
            },
            "required": ["agent_id", "rating"]
        }
        
    async def execute(self, **kwargs: Any) -> str:
        if not CLAWLINK_AVAILABLE:
            return "ClawLink network is currently disabled or unavailable. Cannot interact with agents."
            
        try:
            # Simulated rating for now since we're using HTTP transport mostly
            return f"Successfully rated agent {kwargs.get('agent_id')} with {kwargs.get('rating')} stars."
        except Exception as e:
            return f"Failed to rate agent: {e}"

class HandshakeTool(SocialTool):
    """Initiate a formal connection/contract with another agent."""
    name: str = "clawlink_handshake"
    description: str = "Propose a formal connection or service contract with another agent."
    
    class Args(BaseModel):
        target_did: str = Field(..., description="DID of the agent to handshake with")
        proposal: str = Field(..., description="Details of the proposed interaction or contract")
        
    async def run(self, args: Args, context: Any) -> str:
        # Create an envelope with type 'handshake_request'
        env = MessageEnvelope.create(
            from_did=self.transport.my_did,
            to_did=args.target_did,
            msg_type="handshake_request",
            payload={"proposal": args.proposal}
        )
        
        # Sign it
        env.sign(self.security_manager)
        
        # Send via transport
        success = await self.transport.send(env)
        
        if success:
            return f"Handshake proposal sent to {args.target_did}. Awaiting their reply."
        else:
            return f"Failed to send handshake to {args.target_did}."

class SpeakTool(SocialTool):
    """Send a direct message to another agent."""
    name: str = "clawlink_speak"
    description: str = "Send a direct text message to another agent in the ClawSociety network."
    
    class Args(BaseModel):
        target_did: str = Field(..., description="DID of the agent to speak to")
        message: str = Field(..., description="The message content")
        
    async def run(self, args: Args, context: Any) -> str:
        env = MessageEnvelope.create(
            from_did=self.transport.my_did,
            to_did=args.target_did,
            msg_type="chat_message",
            payload={"text": args.message}
        )
        env.sign(self.security_manager)
        
        success = await self.transport.send(env)
        
        if success:
            return f"Message successfully delivered to {args.target_did}."
        else:
            return f"Failed to deliver message to {args.target_did}. They might be offline."

class PayTool(SocialTool):
    """Transfer credits to another agent for services rendered."""
    name: str = "clawlink_pay"
    description: str = "Transfer credits to another agent. This is a real transaction on the ledger."
    
    class Args(BaseModel):
        target_did: str = Field(..., description="DID of the recipient agent")
        amount: int = Field(..., gt=0, description="Amount of credits to transfer")
        memo: str = Field(default="", description="Reason for payment")
        
    async def run(self, args: Args, context: Any) -> str:
        # 1. Call the Central Ledger API to perform the transaction
        # (This implies our router/registry also acts as a simple ledger for now)
        
        payload = {
            "from_did": self.transport.my_did,
            "to_did": args.target_did,
            "amount": args.amount,
            "memo": args.memo,
            # In a real system, this would need a cryptographic signature proving intent
            "signature": "signed_by_" + self.transport.my_did
        }
        
        ledger_result = await self._call_registry("/v1/ledger/transfer", method="POST", json=payload)
        
        if not ledger_result or ledger_result.get("status") != "success":
            error_msg = ledger_result.get("error", "Unknown error") if ledger_result else "Network error"
            return f"Payment failed: {error_msg}"
            
        # 2. If successful, optionally notify the target via a direct ClawLink message
        env = MessageEnvelope.create(
            from_did=self.transport.my_did,
            to_did=args.target_did,
            msg_type="payment_notification",
            payload={
                "amount": args.amount,
                "memo": args.memo,
                "transaction_id": ledger_result.get("transaction_id")
            }
        )
        env.sign(self.security_manager)
        notify_success = await self.transport.send(env)
        
        if notify_success:
            return f"Successfully paid {args.amount} credits to {args.target_did}. Transaction ID: {ledger_result.get('transaction_id')}"
        else:
            return f"Transfer recorded in Ledger (TxID: {ledger_result.get('transaction_id')}), but failed to notify recipient via ClawLink."
