import asyncio
import logging
from crabclaw.clawlink.transport import RedisTransport
from crabclaw.clawlink.envelope import Envelope

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestLocalVillage")

# Assuming a local Redis is running on default port
REDIS_URL = "redis://localhost:6379"

async def main():
    # 1. Initialize two Sapiens (Alice and Bob)
    alice_did = "did:claw:agent:alice"
    bob_did = "did:claw:agent:bob"
    
    logger.info(f"Initializing {alice_did} and {bob_did}...")
    
    alice_transport = RedisTransport(REDIS_URL, alice_did)
    bob_transport = RedisTransport(REDIS_URL, bob_did)
    
    await alice_transport.connect()
    await bob_transport.connect()
    
    # 2. Define how they handle incoming messages
    async def alice_handler(envelope: Envelope):
        logger.info(f"[ALICE] Received Envelope: Intent={envelope.intent}, Payload={envelope.payload}")
        if envelope.intent == "SYN_ACK":
            logger.info("[ALICE] Bob accepted my handshake! Sending PROPOSE...")
            # Send PROPOSE
            proposal = Envelope(
                from_did=alice_did,
                to_did=bob_did,
                intent="PROPOSE",
                session_id=envelope.session_id,
                payload={"task": "Write a Python script", "reward": 10}
            )
            await alice_transport.send(proposal)
        elif envelope.intent == "ACCEPT":
            logger.info("[ALICE] Bob accepted the task! Awaiting result...")
        elif envelope.intent == "REPORT":
            logger.info(f"[ALICE] Received result from Bob: {envelope.payload.get('result')}")
            # Send final ACK and Pay
            ack = Envelope(
                from_did=alice_did,
                to_did=bob_did,
                intent="ACK",
                session_id=envelope.session_id,
                payload={"status": "received"}
            )
            await alice_transport.send(ack)

    async def bob_handler(envelope: Envelope):
        logger.info(f"[BOB] Received Envelope: Intent={envelope.intent}, Payload={envelope.payload}")
        if envelope.intent == "SYN":
            logger.info("[BOB] Alice wants to connect. Sending SYN_ACK...")
            # Send SYN_ACK
            syn_ack = Envelope(
                from_did=bob_did,
                to_did=alice_did,
                intent="SYN_ACK",
                session_id="session-12345", # Generate a session ID
                payload={"capabilities": ["python", "research"]}
            )
            await bob_transport.send(syn_ack)
        elif envelope.intent == "PROPOSE":
            logger.info(f"[BOB] Alice proposed a task: {envelope.payload.get('task')}. Accepting...")
            accept = Envelope(
                from_did=bob_did,
                to_did=alice_did,
                intent="ACCEPT",
                session_id=envelope.session_id,
                payload={"status": "starting"}
            )
            await bob_transport.send(accept)
            
            # Simulate work
            await asyncio.sleep(1)
            logger.info("[BOB] Finished work. Sending REPORT...")
            report = Envelope(
                from_did=bob_did,
                to_did=alice_did,
                intent="REPORT",
                session_id=envelope.session_id,
                payload={"result": "print('Hello World')"}
            )
            await bob_transport.send(report)
        elif envelope.intent == "ACK":
            logger.info("[BOB] Alice acknowledged receipt. Session complete.")

    # 3. Start listening
    await alice_transport.start_listening(alice_handler)
    await bob_transport.start_listening(bob_handler)
    
    # 4. Trigger the interaction: Alice sends SYN to Bob
    logger.info("--- STARTING INTERACTION ---")
    syn = Envelope(
        from_did=alice_did,
        to_did=bob_did,
        intent="SYN",
        payload={"intent": "need_help"}
    )
    await alice_transport.send(syn)
    
    # 5. Wait for interaction to complete
    await asyncio.sleep(3)
    
    # 6. Cleanup
    logger.info("--- CLEANING UP ---")
    await alice_transport.disconnect()
    await bob_transport.disconnect()

if __name__ == "__main__":
    asyncio.run(main())