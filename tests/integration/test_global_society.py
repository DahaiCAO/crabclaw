import asyncio
import logging
import httpx
from clawlink.transport import HTTPTransport
from clawlink.protocol.envelope import MessageEnvelope
from clawlink.security.signer import SecurityManager
from crabclaw.agent.tools.social import FindAgentTool, RateAgentTool, PayTool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestGlobalSociety")

SOCIETY_URL = "http://127.0.0.1:8005"

async def main():
    # 1. Initialize two Sapiens (Alice and Bob)
    alice_keypair = SecurityManager.generate_keypair()
    bob_keypair = SecurityManager.generate_keypair()
    
    alice_did = alice_keypair.did
    bob_did = bob_keypair.did
    
    alice_security = SecurityManager(alice_keypair)
    bob_security = SecurityManager(bob_keypair)
    
    logger.info(f"Initializing ALICE ({alice_did[:30]}...) and BOB ({bob_did[:30]}...)...")
    
    # Simple registry to resolve DIDs to local HTTP endpoints
    # Note: PayTool needs this for HTTPTransport
    local_registry = {
        alice_did: "http://127.0.0.1:8001",
        bob_did: "http://127.0.0.1:8002"
    }
    
    # 2. Start HTTP Transports
    # Note: We need a discovery_url to register ourselves
    alice_transport = HTTPTransport(alice_did, host="127.0.0.1", port=8001, registry=local_registry, discovery_url=SOCIETY_URL)
    bob_transport = HTTPTransport(bob_did, host="127.0.0.1", port=8002, registry=local_registry, discovery_url=SOCIETY_URL)
    
    # Mock message handlers
    async def noop_handler(envelope: MessageEnvelope):
        logger.info(f"Received envelope: {envelope.intent} {envelope.content}")

    await alice_transport.start_listening(noop_handler)
    await bob_transport.start_listening(noop_handler)
    
    # Wait for server to be up and registration to happen
    await asyncio.sleep(2)
    
    # 3. Enhance Alice's profile (Marketplace Registration)
    async with httpx.AsyncClient() as client:
        # Register Alice with capabilities
        profile = {
            "did": alice_did,
            "endpoint": "http://127.0.0.1:8001",
            "name": "Alice the Coder",
            "role": "Senior Developer",
            "capabilities": ["python", "rust", "debugging"],
            "pricing": {"code_review": 50.0}
        }
        resp = await client.post(f"{SOCIETY_URL}/v1/registry/register", json=profile)
        logger.info(f"Alice registered: {resp.status_code} {resp.json()}")

    # 4. Bob Searches for a Python Expert (Marketplace Search)
    find_tool = FindAgentTool(bob_transport, bob_security, discovery_url=SOCIETY_URL)
    search_result = await find_tool.run(FindAgentTool.Args(capability="python"), None)
    logger.info(f"Bob search result:\n{search_result}")
    
    if "Alice" not in search_result:
        logger.error("Alice not found in search!")
        return

    # 5. Bob Pays Alice for a Code Review (Economy & Ledger)
    pay_tool = PayTool(bob_transport, bob_security, discovery_url=SOCIETY_URL)
    payment_result = await pay_tool.run(PayTool.Args(target_did=alice_did, amount=50.0, reason="code_review"), None)
    logger.info(f"Bob payment result: {payment_result}")
    
    # Verify balance
    async with httpx.AsyncClient() as client:
        # Note: The DID in the URL must be URL-encoded if it contains special chars like '/' or '+'
        # FastAPI handles path parameters, but standard clients might need explicit encoding
        # However, usually just passing the string works if the client handles it.
        # Let's try to debug why Alice was not found.
        # Issue: The DID contains '/' (e.g. "did:claw:agent:.../...") which might be interpreted as path separator.
        import urllib.parse
        alice_did_encoded = urllib.parse.quote(alice_did, safe='')
        bob_did_encoded = urllib.parse.quote(bob_did, safe='')
        
        bal = await client.get(f"{SOCIETY_URL}/v1/economy/balance/{alice_did_encoded}")
        logger.info(f"Alice balance: {bal.json()}")
        bal = await client.get(f"{SOCIETY_URL}/v1/economy/balance/{bob_did_encoded}")
        logger.info(f"Bob balance: {bal.json()}")

    # 6. Bob Rates Alice (Reputation)
    rate_tool = RateAgentTool(bob_transport, bob_security, discovery_url=SOCIETY_URL)
    rate_result = await rate_tool.run(RateAgentTool.Args(target_did=alice_did, score=0.95, comment="Excellent code review!"), None)
    logger.info(f"Bob rating result: {rate_result}")
    
    # Verify new reputation
    async with httpx.AsyncClient() as client:
        import urllib.parse
        alice_did_encoded = urllib.parse.quote(alice_did, safe='')
        profile = await client.get(f"{SOCIETY_URL}/v1/registry/resolve/{alice_did_encoded}")
        logger.info(f"Alice new profile: {profile.json()}")

    # Cleanup
    await alice_transport.disconnect()
    await bob_transport.disconnect()
    logger.info("Test complete.")

if __name__ == "__main__":
    asyncio.run(main())
