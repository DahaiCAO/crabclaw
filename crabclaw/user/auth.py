"""User authentication."""

import bcrypt
from datetime import datetime, timedelta
import secrets
from typing import Optional, Dict, Any


class UserAuth:
    """User authentication utilities."""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify a password."""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

    @staticmethod
    def generate_session_token() -> str:
        """Generate a session token."""
        return secrets.token_hex(32)

    @staticmethod
    def create_session(user_id: str, username: str) -> Dict[str, Any]:
        """Create a session."""
        return {
            "session_id": UserAuth.generate_session_token(),
            "user_id": user_id,
            "username": username,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=7)).isoformat()
        }

    @staticmethod
    def is_session_valid(session: Dict[str, Any]) -> bool:
        """Check if a session is valid."""
        try:
            expires_at = datetime.fromisoformat(session.get("expires_at", ""))
            return datetime.now() < expires_at
        except:
            return False
