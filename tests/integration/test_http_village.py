import asyncio
import logging
from crabclaw.clawlink.transport import HTTPTransport
from crabclaw.clawlink.envelope import Envelope
from crabclaw.clawlink.security.signer import SecurityManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestHTTPVillage")

async def main():
    # 1. Initialize two Sapiens (Alice and Bob) with real keypairs for signing
    alice_keypair = SecurityManager.generate_keypair()
    bob_keypair = SecurityManager.generate_keypair()
    
    alice_did = alice_keypair.did
    bob_did = bob_keypair.did
    
    alice_security = SecurityManager(alice_keypair)
    bob_security = SecurityManager(bob_keypair)
    
    logger.info(f"Initializing ALICE ({alice_did[:30]}...) and BOB ({bob_did[:30]}...)...")
    
    # Simple registry to resolve DIDs to local HTTP endpoints
    registry = {
        alice_did: "http://127.0.0.1:8001",
        bob_did: "http://127.0.0.1:8002"
    }
    
    alice_transport = HTTPTransport(alice_did, host="127.0.0.1", port=8001, registry=registry)
    bob_transport = HTTPTransport(bob_did, host="127.0.0.1", port=8002, registry=registry)
    
    # 2. Define how they handle incoming messages
    async def alice_handler(envelope: Envelope):
        if not SecurityManager.verify_envelope(envelope):
            logger.error("[ALICE] Invalid signature received!")
            return
            
        logger.info(f"[ALICE] Verified Envelope: Intent={envelope.intent}, Payload={envelope.payload}")
        if envelope.intent == "SYN_ACK":
            logger.info("[ALICE] Bob accepted my handshake! Sending PROPOSE...")
            proposal = Envelope(
                from_did=alice_did,
                to_did=bob_did,
                intent="PROPOSE",
                session_id=envelope.session_id,
                payload={"task": "Write a HTTP script", "reward": 20}
            )
            proposal = alice_security.sign_envelope(proposal)
            await alice_transport.send(proposal)
        elif envelope.intent == "REPORT":
            logger.info(f"[ALICE] Received result from Bob: {envelope.payload.get('result')}")

    async def bob_handler(envelope: Envelope):
        if not SecurityManager.verify_envelope(envelope):
            logger.error("[BOB] Invalid signature received!")
            return
            
        logger.info(f"[BOB] Verified Envelope: Intent={envelope.intent}, Payload={envelope.payload}")
        if envelope.intent == "SYN":
            logger.info("[BOB] Alice wants to connect. Sending SYN_ACK...")
            syn_ack = Envelope(
                from_did=bob_did,
                to_did=alice_did,
                intent="SYN_ACK",
                session_id="session-http-123",
                payload={"capabilities": ["http", "fastapi"]}
            )
            syn_ack = bob_security.sign_envelope(syn_ack)
            await bob_transport.send(syn_ack)
        elif envelope.intent == "PROPOSE":
            logger.info(f"[BOB] Alice proposed a task: {envelope.payload.get('task')}. Sending REPORT...")
            await asyncio.sleep(0.5)
            report = Envelope(
                from_did=bob_did,
                to_did=alice_did,
                intent="REPORT",
                session_id=envelope.session_id,
                payload={"result": "import requests\nprint('Done')"}
            )
            report = bob_security.sign_envelope(report)
            await bob_transport.send(report)

    # 3. Start listening (FastAPI servers)
    await alice_transport.start_listening(alice_handler)
    await bob_transport.start_listening(bob_handler)
    
    # Give uvicorn servers a moment to start
    await asyncio.sleep(1)
    
    # 4. Trigger the interaction: Alice sends SYN to Bob
    logger.info("--- STARTING HTTP INTERACTION ---")
    syn = Envelope(
        from_did=alice_did,
        to_did=bob_did,
        intent="SYN",
        payload={"intent": "test_http_connection"}
    )
    syn = alice_security.sign_envelope(syn)
    await alice_transport.send(syn)
    
    # Keep alive to let messages pass
    await asyncio.sleep(3)
    
    # 5. Cleanup
    await alice_transport.disconnect()
    await bob_transport.disconnect()
    logger.info("Test complete.")

if __name__ == "__main__":
    asyncio.run(main())
