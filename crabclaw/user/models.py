"""User profile models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional


@dataclass
class ContactInfo:
    """Contact information."""
    type: str  # email, feishu, etc.
    value: str
    is_primary: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UserProfile:
    """User profile."""
    user_id: str
    username: str
    display_name: str
    password_hash: str
    contacts: List[ContactInfo] = field(default_factory=list)
    preferences: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    is_active: bool = True
    is_admin: bool = False

    def add_contact(self, contact: ContactInfo) -> None:
        """Add a contact."""
        if contact.is_primary:
            # Set all other contacts to non-primary
            for c in self.contacts:
                c.is_primary = False
        self.contacts.append(contact)
        self.updated_at = datetime.now()

    def update_preferences(self, preferences: Dict[str, Any]) -> None:
        """Update user preferences."""
        self.preferences.update(preferences)
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "display_name": self.display_name,
            "password_hash": self.password_hash,
            "contacts": [
                {
                    "type": c.type,
                    "value": c.value,
                    "is_primary": c.is_primary,
                    "metadata": c.metadata
                }
                for c in self.contacts
            ],
            "preferences": self.preferences,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "is_active": self.is_active,
            "is_admin": self.is_admin
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        """Create from dictionary."""
        contacts = [
            ContactInfo(
                type=c["type"],
                value=c["value"],
                is_primary=c.get("is_primary", False),
                metadata=c.get("metadata", {})
            )
            for c in data.get("contacts", [])
        ]
        
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            display_name=data["display_name"],
            password_hash=data["password_hash"],
            contacts=contacts,
            preferences=data.get("preferences", {}),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now().isoformat())),
            last_login=datetime.fromisoformat(data["last_login"]) if data.get("last_login") else None,
            is_active=data.get("is_active", True),
            is_admin=data.get("is_admin", False)
        )
