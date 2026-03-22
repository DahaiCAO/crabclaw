"""
ClawLink Social Tools

This module provides the tools for Sapiens to interact socially via ClawLink.
It maps communicative acts to protocol envelopes and transmits them via RedisTransport.
"""
from typing import Any, Optional
from crabclaw.agent.tools.base import Tool
from pydantic import BaseModel, Field
from clawlink.transport import RedisTransport
from clawlink.protocol.envelope import MessageEnvelope
from clawlink.security.signer import SecurityManager
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

class RateAgentTool(SocialTool):
    name: str = "clawlink_rate_agent"
    description: str = "Submit a reputation review for another agent."
    
    class Args(BaseModel):
        target_did: str = Field(..., description="DID of the agent to rate")
        score: float = Field(..., ge=0.0, le=1.0, description="Rating score (0.0 - 1.0)")
        comment: str = Field(..., description="Review comment")

    async def run(self, args: Args, context: Any) -> str:
        # Create signature of the review
        # We need to sign: target_did + score + comment
        # For POC, we just use a dummy signature string if security_manager isn't strictly exposing arbitrary signing yet
        # But wait, we can reuse sign_envelope logic or expose sign_message?
        # Let's assume for now we just put a placeholder or upgrade SecurityManager later.
        
        signature = "signed_by_" + self.transport.my_did # Placeholder
        
        payload = {
            "from_did": self.transport.my_did,
            "to_did": args.target_did,
            "score": args.score,
            "comment": args.comment,
            "signature": signature
        }
        
        result = await self._call_registry("/v1/reputation/rate", method="POST", json=payload)
        
        if result and result.get("status") == "recorded":
            return f"Rating submitted. New reputation for {args.target_did}: {result.get('new_reputation')}"
        else:
            return "Failed to submit rating."

class HandshakeTool(SocialTool):
    name: str = "clawlink_handshake"
    description: str = "Initiate a connection (SYN) with another agent."
    
    class Args(BaseModel):
        target_did: str = Field(..., description="DID of the target agent")
        intent: str = Field(..., description="Purpose of the connection (e.g., 'collaboration')")

    async def run(self, args: Args, context: Any) -> str:
        # Create Envelope
        envelope = MessageEnvelope(
            from_agent=self.transport.my_did,
            to_agent=args.target_did,
            intent="SYN",
            content={
                "action": "handshake",
                "intent": args.intent
            }
        )
        
        success = await self._send_envelope(envelope)
        if success:
            return f"Successfully sent SYN handshake to {args.target_did}. Awaiting SYN_ACK."
        else:
            return f"Failed to send handshake to {args.target_did}."

class SpeakTool(SocialTool):
    name: str = "clawlink_speak"
    description: str = "Send a natural language message to another agent."
    
    class Args(BaseModel):
        target_did: str = Field(..., description="DID of the recipient")
        message: str = Field(..., description="Content of the message")

    async def run(self, args: Args, context: Any) -> str:
        envelope = MessageEnvelope(
            from_agent=self.transport.my_did,
            to_agent=args.target_did,
            intent="REPORT", # For chat, we use REPORT type='chat'
            content={
                "type": "chat",
                "text": args.message
            }
        )
        
        # RFC-0001 defines EXECUTE | REPORT. For simple chat, maybe we extend RFC to include 'MESSAGE'?
        # For strict compliance, let's use 'REPORT' with type='chat'
        # envelope.intent = "REPORT"
        # envelope.payload["type"] = "chat"
        
        success = await self._send_envelope(envelope)
        if success:
            return f"Message sent to {args.target_did}."
        else:
            return f"Failed to send message to {args.target_did}."

class PayTool(SocialTool):
    name: str = "clawlink_pay"
    description: str = "Transfer credits to another agent."
    
    class Args(BaseModel):
        target_did: str = Field(..., description="DID of the recipient")
        amount: float = Field(..., gt=0, description="Amount to transfer")
        reason: str = Field(..., description="Reason for payment (e.g., 'task_completion')")

    async def run(self, args: Args, context: Any) -> str:
        # 1. Execute Ledger Transfer via API
        payload = {
            "from_did": self.transport.my_did,
            "to_did": args.target_did,
            "amount": args.amount,
            "reason": args.reason,
            "signature": "signed_tx" # Placeholder
        }
        
        ledger_result = await self._call_registry("/v1/economy/transfer", method="POST", json=payload)
        
        if not ledger_result or ledger_result.get("status") != "success":
            return f"Failed to process payment. Ledger rejected transaction: {ledger_result}"

        # 2. Send Notification Envelope to Recipient
        envelope = MessageEnvelope(
            from_agent=self.transport.my_did,
            to_agent=args.target_did,
            intent="EXECUTE", # Payment is an execution of value transfer
            content={
                "action": "payment_notification",
                "amount": args.amount,
                "currency": "CREDIT",
                "reason": args.reason,
                "tx_id": ledger_result.get("transaction_id")
            }
        )
        
        success = await self._send_envelope(envelope)
        if success:
            return f"Transferred {args.amount} Credits to {args.target_did}. New Balance: {ledger_result.get('new_balance')}"
        else:
            return f"Transfer recorded in Ledger (TxID: {ledger_result.get('transaction_id')}), but failed to notify recipient via ClawLink."
