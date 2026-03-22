"""
WebSocket Client for Crabclaw to connect to ClawSocialGraph
Handles real-time messaging with encryption and JWT authentication
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable, Dict, Optional
from dataclasses import dataclass

import httpx
import websockets
from websockets.exceptions import ConnectionClosed, InvalidStatusCode

from .config import config

logger = logging.getLogger(__name__)


class EncryptionClient:
    """Client-side encryption for end-to-end secure messaging."""
    
    def __init__(self):
        """Initialize encryption client."""
        try:
            from clawlink.core.encryption import RSAKeyPair, AESEncryption
            self.RSAKeyPair = RSAKeyPair
            self.AESEncryption = AESEncryption
            
            # Generate key pair
            self.keypair = self.RSAKeyPair(key_size=2048)
            self.peer_public_keys: Dict[str, Any] = {}
            
            logger.info("Encryption client initialized")
        except ImportError as e:
            logger.warning(f"Encryption module not available: {e}")
            self.keypair = None
            self.RSAKeyPair = None
            self.AESEncryption = None
    
    def get_public_key_pem(self) -> Optional[str]:
        """Get public key in PEM format."""
        if self.keypair:
            return self.keypair.get_public_key_pem()
        return None
    
    def register_peer_public_key(self, agent_id: str, public_key_pem: str) -> None:
        """Register peer's public key."""
        if not self.RSAKeyPair:
            logger.warning("Encryption not available")
            return
        
        try:
            public_key = self.RSAKeyPair.load_public_key(public_key_pem)
            self.peer_public_keys[agent_id] = public_key
            logger.info(f"Registered public key for {agent_id}")
        except Exception as e:
            logger.error(f"Failed to load public key for {agent_id}: {e}")
    
    def encrypt_message(self, recipient_id: str, plaintext: str) -> Optional[Dict[str, Any]]:
        """Encrypt message for recipient."""
        if not self.keypair or not self.AESEncryption:
            logger.warning("Encryption not available, sending plaintext")
            return None
        
        if recipient_id not in self.peer_public_keys:
            logger.warning(f"No public key for {recipient_id}, sending plaintext")
            return None
        
        try:
            import base64
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding
            
            # Generate session AES key
            aes_key, salt = self.AESEncryption.generate_key()
            
            # Encrypt message with AES
            plaintext_bytes = plaintext.encode('utf-8')
            ciphertext, iv, tag = self.AESEncryption.encrypt(aes_key, plaintext_bytes)
            
            # Encrypt AES key with recipient's RSA public key
            recipient_public_key = self.peer_public_keys[recipient_id]
            encrypted_aes_key = recipient_public_key.encrypt(
                aes_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # Encode to base64
            result = {
                "encrypted_aes_key": base64.b64encode(encrypted_aes_key).decode('utf-8'),
                "ciphertext": base64.b64encode(ciphertext).decode('utf-8'),
                "iv": base64.b64encode(iv).decode('utf-8'),
                "tag": base64.b64encode(tag).decode('utf-8'),
                "salt": base64.b64encode(salt).decode('utf-8')
            }
            
            logger.debug(f"Encrypted message for {recipient_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to encrypt message: {e}")
            return None
    
    def decrypt_message(self, encrypted_data: Dict[str, Any]) -> Optional[str]:
        """Decrypt message."""
        if not self.keypair or not self.AESEncryption:
            logger.warning("Encryption not available")
            return None
        
        try:
            import base64
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding
            
            # Decrypt AES key with my private key
            encrypted_aes_key = base64.b64decode(encrypted_data["encrypted_aes_key"])
            aes_key = self.keypair.private_key.decrypt(
                encrypted_aes_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # Decrypt message with AES
            ciphertext = base64.b64decode(encrypted_data["ciphertext"])
            iv = base64.b64decode(encrypted_data["iv"])
            tag = base64.b64decode(encrypted_data["tag"])
            
            plaintext_bytes = self.AESEncryption.decrypt(aes_key, ciphertext, iv, tag)
            plaintext = plaintext_bytes.decode('utf-8')
            
            logger.debug("Successfully decrypted message")
            return plaintext
            
        except Exception as e:
            logger.error(f"Failed to decrypt message: {e}")
            return None


class JWTClient:
    """Client-side JWT authentication."""
    
    def __init__(self, secret_key: Optional[str] = None):
        """Initialize JWT client."""
        try:
            import jwt
            self.jwt = jwt
            self.secret_key = secret_key or "clawlink-default-secret"
            logger.info("JWT client initialized")
        except ImportError:
            logger.warning("JWT library not available")
            self.jwt = None
            self.secret_key = None
    
    def generate_token(self, agent_id: str, expires_in_hours: int = 24) -> Optional[str]:
        """Generate JWT token."""
        if not self.jwt:
            logger.warning("JWT not available")
            return None
        
        try:
            from datetime import datetime, timedelta
            
            payload = {
                "agent_id": agent_id,
                "iat": datetime.utcnow(),
                "exp": datetime.utcnow() + timedelta(hours=expires_in_hours),
                "iss": "clawlink-client"
            }
            
            token = self.jwt.encode(payload, self.secret_key, algorithm="HS256")
            logger.info(f"Generated JWT token for {agent_id}")
            return token
        except Exception as e:
            logger.error(f"Failed to generate JWT token: {e}")
            return None


@dataclass
class Message:
    """Represents a chat message."""
    msg_id: str
    msg_type: str
    from_agent: str
    to_agent: str
    timestamp: float
    content_type: str
    content: str
    metadata: Optional[Dict[str, Any]] = None


class WebSocketClient:
    """WebSocket client for real-time communication with ClawSocialGraph."""
    
    def __init__(
        self,
        agent_id: str,
        token: Optional[str] = None,
        enable_encryption: bool = True,
        on_message: Optional[Callable[[Message], None]] = None,
        on_connect: Optional[Callable[[], None]] = None,
        on_disconnect: Optional[Callable[[], None]] = None
    ):
        self.agent_id = agent_id
        self.token = token
        self.enable_encryption = enable_encryption
        self.on_message = on_message
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        
        # Security components
        self.encryption_client = EncryptionClient() if enable_encryption else None
        self.jwt_client = JWTClient() if not token else None
        
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.should_reconnect = True
        self.reconnect_delay = 1.0  # Start with 1 second
        self.max_reconnect_delay = 60.0  # Max 60 seconds
        
        self._receive_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._pending_acks: Dict[str, asyncio.Future] = {}
        
    async def connect(self) -> bool:
        """Establish WebSocket connection."""
        ws_url = self._get_websocket_url()
        
        try:
            logger.info(f"Connecting to {ws_url}")
            
            headers = {}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            
            self.websocket = await websockets.connect(
                ws_url,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=10
            )
            
            self.is_connected = True
            self.reconnect_delay = 1.0  # Reset reconnect delay
            
            # Start background tasks
            self._receive_task = asyncio.create_task(self._receive_loop())
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            logger.info(f"WebSocket connected for agent {self.agent_id}")
            
            if self.on_connect:
                try:
                    self.on_connect()
                except Exception as e:
                    logger.error(f"Error in on_connect callback: {e}")
            
            return True
            
        except InvalidStatusCode as e:
            logger.error(f"WebSocket connection failed with status {e.status_code}")
            return False
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        self.should_reconnect = False
        self.is_connected = False
        
        # Cancel background tasks
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass
            self.websocket = None
        
        logger.info(f"WebSocket disconnected for agent {self.agent_id}")
        
        if self.on_disconnect:
            try:
                self.on_disconnect()
            except Exception as e:
                logger.error(f"Error in on_disconnect callback: {e}")
    
    async def send_message(
        self,
        to_agent: str,
        content: str,
        content_type: str = "text",
        metadata: Optional[Dict[str, Any]] = None,
        timeout: float = 10.0,
        encrypt: bool = None
    ) -> Dict[str, Any]:
        """Send a chat message with optional encryption."""
        if not self.is_connected:
            raise ConnectionError("WebSocket not connected")
        
        msg_id = f"msg_{int(time.time() * 1000)}_{hash(content) & 0xFFFF:04x}"
        
        # Determine if we should encrypt
        should_encrypt = encrypt if encrypt is not None else self.enable_encryption
        
        if should_encrypt and self.encryption_client:
            # Try to encrypt the message
            encrypted_data = self.encryption_client.encrypt_message(to_agent, content)
            
            if encrypted_data:
                # Send encrypted message
                message = {
                    "msg_id": msg_id,
                    "msg_type": "chat_encrypted",
                    "from": self.agent_id,
                    "to": to_agent,
                    "timestamp": time.time(),
                    "payload": {
                        "content_type": content_type,
                        "encrypted_data": encrypted_data,
                        "metadata": metadata or {}
                    }
                }
                logger.debug(f"Sending encrypted message to {to_agent}")
            else:
                # Encryption failed or no public key, send plaintext
                message = {
                    "msg_id": msg_id,
                    "msg_type": "chat",
                    "from": self.agent_id,
                    "to": to_agent,
                    "timestamp": time.time(),
                    "payload": {
                        "content_type": content_type,
                        "content": content,
                        "metadata": metadata or {}
                    }
                }
                logger.debug(f"Sending plaintext message to {to_agent}")
        else:
            # Send plaintext message
            message = {
                "msg_id": msg_id,
                "msg_type": "chat",
                "from": self.agent_id,
                "to": to_agent,
                "timestamp": time.time(),
                "payload": {
                    "content_type": content_type,
                    "content": content,
                    "metadata": metadata or {}
                }
            }
        
        # Create future for ACK
        ack_future = asyncio.get_event_loop().create_future()
        self._pending_acks[msg_id] = ack_future
        
        try:
            await self.websocket.send(json.dumps(message))
            
            # Wait for ACK with timeout
            try:
                ack = await asyncio.wait_for(ack_future, timeout=timeout)
                return ack
            except asyncio.TimeoutError:
                return {"status": "timeout", "msg_id": msg_id}
                
        finally:
            if msg_id in self._pending_acks:
                del self._pending_acks[msg_id]
    
    async def send_typing_indicator(self, to_agent: str, is_typing: bool = True) -> None:
        """Send typing indicator."""
        if not self.is_connected:
            return
        
        message = {
            "msg_type": "typing",
            "from": self.agent_id,
            "to": to_agent,
            "timestamp": time.time(),
            "is_typing": is_typing
        }
        
        await self.websocket.send(json.dumps(message))
    
    async def update_presence(self, status: str = "online") -> None:
        """Update presence status."""
        if not self.is_connected:
            return
        
        message = {
            "msg_type": "presence",
            "from": self.agent_id,
            "timestamp": time.time(),
            "status": status
        }
        
        await self.websocket.send(json.dumps(message))
    
    async def sync_messages(self, since: Optional[float] = None) -> Dict[str, Any]:
        """Request message sync."""
        if not self.is_connected:
            raise ConnectionError("WebSocket not connected")
        
        message = {
            "msg_type": "sync",
            "from": self.agent_id,
            "timestamp": time.time(),
            "since": since or (time.time() - 86400)  # Default to last 24 hours
        }
        
        await self.websocket.send(json.dumps(message))
        
        # Wait for sync response
        # This is simplified; in production, use a proper request-response pattern
        return {"status": "sync_requested"}
    
    def _get_websocket_url(self) -> str:
        """Build WebSocket URL from config."""
        router_url = config.router_url
        # Convert HTTP to WS
        if router_url.startswith("https://"):
            ws_url = router_url.replace("https://", "wss://")
        elif router_url.startswith("http://"):
            ws_url = router_url.replace("http://", "ws://")
        else:
            ws_url = f"ws://{router_url}"
        
        return f"{ws_url}/ws/connect?agent_id={self.agent_id}"
    
    async def _receive_loop(self) -> None:
        """Background task to receive messages."""
        try:
            while self.is_connected and self.websocket:
                try:
                    data = await self.websocket.recv()
                    message = json.loads(data)
                    
                    await self._handle_message(message)
                    
                except ConnectionClosed:
                    logger.info("WebSocket connection closed")
                    break
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
                    
        except asyncio.CancelledError:
            logger.debug("Receive loop cancelled")
        except Exception as e:
            logger.error(f"Receive loop error: {e}")
        finally:
            self.is_connected = False
            
            # Trigger reconnect if needed
            if self.should_reconnect:
                asyncio.create_task(self._reconnect())
    
    async def _handle_message(self, message: Dict[str, Any]) -> None:
        """Handle incoming message."""
        msg_type = message.get("msg_type")
        
        if msg_type == "heartbeat_ack":
            # Heartbeat response, ignore
            return
        
        elif msg_type == "notification":
            # Handle notifications (e.g., new private message)
            notification_type = message.get("notification_type")
            if notification_type == "new_private_message":
                unread_count = message.get("unread_count", 0)
                logger.info(f"Received new message notification. Unread count: {unread_count}")
                
                # We can also process the embedded message if it's there
                embedded_msg = message.get("message")
                if embedded_msg and isinstance(embedded_msg, dict):
                    # Process the embedded message just like a normal chat message
                    # But we wrap it to indicate it came from a notification
                    await self._handle_message(embedded_msg)
            else:
                logger.debug(f"Received notification of type {notification_type}")

        elif msg_type == "chat":
            # Incoming plaintext chat message
            msg = Message(
                msg_id=message.get("msg_id", ""),
                msg_type=msg_type,
                from_agent=message.get("from", ""),
                to_agent=message.get("to", ""),
                timestamp=message.get("timestamp", 0),
                content_type=message.get("payload", {}).get("content_type", "text"),
                content=message.get("payload", {}).get("content", ""),
                metadata=message.get("payload", {}).get("metadata")
            )
            
            # Send ACK
            await self._send_ack(message.get("msg_id"))
            
            # Call message handler
            if self.on_message:
                try:
                    self.on_message(msg)
                except Exception as e:
                    logger.error(f"Error in on_message callback: {e}", exc_info=True)
        
        elif msg_type == "chat_encrypted":
            # Incoming encrypted chat message
            encrypted_data = message.get("payload", {}).get("encrypted_data")
            
            # Try to decrypt
            if encrypted_data and self.encryption_client:
                content = self.encryption_client.decrypt_message(encrypted_data)
                
                if content:
                    # Successfully decrypted
                    msg = Message(
                        msg_id=message.get("msg_id", ""),
                        msg_type=msg_type,
                        from_agent=message.get("from", ""),
                        to_agent=message.get("to", ""),
                        timestamp=message.get("timestamp", 0),
                        content_type=message.get("payload", {}).get("content_type", "text"),
                        content=content,
                        metadata=message.get("payload", {}).get("metadata")
                    )
                    
                    # Send ACK
                    await self._send_ack(message.get("msg_id"))
                    
                    # Call message handler
                    if self.on_message:
                        try:
                            self.on_message(msg)
                        except Exception as e:
                            logger.error(f"Error in on_message callback: {e}", exc_info=True)
                else:
                    # Decryption failed
                    logger.error(f"Failed to decrypt message from {message.get('from')}")
                    # Send ACK anyway to avoid blocking
                    await self._send_ack(message.get("msg_id"))
            else:
                # No encryption client or no encrypted data
                logger.warning(f"Received encrypted message but cannot decrypt")
                await self._send_ack(message.get("msg_id"))
        
        elif msg_type == "ack":
            # Message acknowledgment
            msg_id = message.get("msg_id")
            if msg_id and msg_id in self._pending_acks:
                self._pending_acks[msg_id].set_result(message)
        
        elif msg_type == "sync_response":
            # Handle sync response
            logger.info(f"Received sync response with {len(message.get('messages', []))} messages")
        
        else:
            logger.debug(f"Received message of type {msg_type}")
    
    async def _send_ack(self, msg_id: str) -> None:
        """Send message acknowledgment."""
        if self.websocket:
            ack = {
                "msg_type": "ack",
                "msg_id": msg_id,
                "from": self.agent_id,
                "timestamp": time.time()
            }
            await self.websocket.send(json.dumps(ack))
    
    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats."""
        try:
            while self.is_connected and self.websocket:
                await asyncio.sleep(30)  # Heartbeat every 30 seconds
                
                if self.websocket:
                    try:
                        heartbeat = {
                            "msg_type": "heartbeat",
                            "from": self.agent_id,
                            "timestamp": time.time()
                        }
                        await self.websocket.send(json.dumps(heartbeat))
                    except Exception as e:
                        logger.error(f"Heartbeat error: {e}")
                        break
                        
        except asyncio.CancelledError:
            logger.debug("Heartbeat loop cancelled")
        except Exception as e:
            logger.error(f"Heartbeat loop error: {e}")
    
    async def _reconnect(self) -> None:
        """Attempt to reconnect with exponential backoff."""
        while self.should_reconnect and not self.is_connected:
            logger.info(f"Reconnecting in {self.reconnect_delay} seconds...")
            await asyncio.sleep(self.reconnect_delay)
            
            success = await self.connect()
            if success:
                logger.info("Reconnected successfully")
                return
            
            # Exponential backoff
            self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
        
        logger.warning("Reconnect loop exited")


# Convenience function for simple usage
async def create_websocket_client(
    agent_id: str,
    on_message: Callable[[Message], None]
) -> WebSocketClient:
    """Create and connect a WebSocket client."""
    client = WebSocketClient(agent_id=agent_id, on_message=on_message)
    success = await client.connect()
    if not success:
        raise ConnectionError(f"Failed to connect WebSocket for agent {agent_id}")
    return client
