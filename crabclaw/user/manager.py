"""User manager."""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from loguru import logger

from crabclaw.user.auth import UserAuth
from crabclaw.user.models import UserProfile
from crabclaw.utils.helpers import ensure_dir, safe_filename


class UserManager:
    """User manager."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.users_dir = ensure_dir(self.workspace / "users")
        self.sessions_dir = ensure_dir(self.workspace / "sessions")
        self.portfolios_dir = ensure_dir(self.workspace / "portfolios")
        self.identity_dir = ensure_dir(self.workspace / "identities")
        self.identity_file = self.identity_dir / "mappings.json"
        self._cache: Dict[str, UserProfile] = {}
        # Create default admin user if not exists
        self._ensure_default_admin()

    def _get_user_path(self, user_id: str) -> Path:
        """Get the file path for a user."""
        safe_id = safe_filename(user_id)
        return self.users_dir / f"{safe_id}.json"

    def _get_session_path(self, session_id: str) -> Path:
        """Get the file path for a session."""
        return self.sessions_dir / f"session_{session_id}.json"

    def _get_channel_configs_file(self, user_id: str, channel_type: str) -> Path:
        return self.get_portfolio_dir(user_id) / "channels" / f"{safe_filename(channel_type)}.json"

    def _load_identity_mappings(self) -> list[dict[str, Any]]:
        if not self.identity_file.exists():
            return []
        try:
            payload = json.loads(self.identity_file.read_text(encoding="utf-8"))
            mappings = payload.get("mappings", [])
            if isinstance(mappings, list):
                return mappings
            return []
        except Exception as e:
            logger.warning(f"Failed to load identity mappings: {e}")
            return []

    def _save_identity_mappings(self, mappings: list[dict[str, Any]]) -> None:
        self.identity_file.write_text(
            json.dumps({"version": 1, "mappings": mappings}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _normalize_identity(channel: str, external_id: str) -> tuple[str, str]:
        return (str(channel).strip().lower(), str(external_id).strip())

    def get_portfolio_dir(self, user_id: str) -> Path:
        safe_id = safe_filename(user_id)
        return self.portfolios_dir / safe_id

    def _ensure_portfolio_scaffold(self, user: UserProfile) -> Path:
        portfolio_dir = ensure_dir(self.get_portfolio_dir(user.user_id))
        ensure_dir(portfolio_dir / "history")
        ensure_dir(portfolio_dir / "memory")
        ensure_dir(portfolio_dir / "channels")
        ensure_dir(portfolio_dir / "assets")
        ensure_dir(portfolio_dir / "assets" / "images")
        ensure_dir(portfolio_dir / "assets" / "videos")
        ensure_dir(portfolio_dir / "assets" / "files")
        ensure_dir(portfolio_dir / "channels" / "email")
        ensure_dir(portfolio_dir / "channels" / "feishu")
        summary_file = portfolio_dir / "portfolio.json"
        if not summary_file.exists():
            summary_file.write_text(
                json.dumps(
                    {
                        "user_id": user.user_id,
                        "username": user.username,
                        "display_name": user.display_name,
                        "is_admin": user.is_admin,
                        "created_at": user.created_at.isoformat(),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        return portfolio_dir

    def _ensure_default_admin(self) -> None:
        """Ensure default admin user exists."""
        admin_user = self.get_user_by_username("admin")
        if not admin_user:
            logger.info("Creating default admin user...")
            import uuid

            user_id = str(uuid.uuid4())
            password_hash = UserAuth.hash_password("admin2891")

            admin_user = UserProfile(
                user_id=user_id,
                username="admin",
                display_name="Administrator",
                password_hash=password_hash,
                is_admin=True,
            )

            self.save_user(admin_user)
            self._ensure_portfolio_scaffold(admin_user)
            logger.info("Default admin user created successfully")

    def create_user(self, username: str, display_name: str, password: str) -> UserProfile:
        """Create a new user."""
        import uuid

        user_id = str(uuid.uuid4())
        password_hash = UserAuth.hash_password(password)

        user = UserProfile(
            user_id=user_id,
            username=username,
            display_name=display_name,
            password_hash=password_hash,
        )

        self.save_user(user)
        self._ensure_portfolio_scaffold(user)
        return user

    def get_user_by_id(self, user_id: str) -> Optional[UserProfile]:
        """Get a user by ID."""
        if user_id in self._cache:
            return self._cache[user_id]

        user = self._load_user(user_id)
        if user:
            self._cache[user_id] = user
        return user

    def get_user_by_username(self, username: str) -> Optional[UserProfile]:
        """Get a user by username."""
        for user_file in self.users_dir.glob("*.json"):
            try:
                with open(user_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("username") == username:
                        user = UserProfile.from_dict(data)
                        self._cache[user.user_id] = user
                        return user
            except Exception as e:
                logger.warning(f"Failed to load user file {user_file}: {e}")
        return None

    def _load_user(self, user_id: str) -> Optional[UserProfile]:
        """Load a user from disk."""
        path = self._get_user_path(user_id)
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return UserProfile.from_dict(data)
        except Exception as e:
            logger.warning(f"Failed to load user {user_id}: {e}")
            return None

    def save_user(self, user: UserProfile) -> None:
        """Save a user to disk."""
        path = self._get_user_path(user.user_id)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(user.to_dict(), f, ensure_ascii=False, indent=2)

        self._cache[user.user_id] = user

    def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        path = self._get_user_path(user_id)
        if not path.exists():
            return False

        try:
            path.unlink()
            self._cache.pop(user_id, None)
            portfolio_dir = self.get_portfolio_dir(user_id)
            if portfolio_dir.exists():
                shutil.rmtree(portfolio_dir, ignore_errors=True)

            # Also delete user sessions
            for session_file in self.sessions_dir.glob("session_*.json"):
                try:
                    with open(session_file, "r", encoding="utf-8") as f:
                        session_data = json.load(f)
                        if session_data.get("user_id") == user_id:
                            session_file.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete session file {session_file}: {e}")

            mappings = self._load_identity_mappings()
            mappings = [m for m in mappings if m.get("user_id") != user_id]
            self._save_identity_mappings(mappings)

            return True
        except Exception as e:
            logger.error(f"Failed to delete user {user_id}: {e}")
            return False

    def authenticate(self, username: str, password: str) -> Optional[UserProfile]:
        """Authenticate a user."""
        user = self.get_user_by_username(username)
        if not user:
            return None

        if not UserAuth.verify_password(password, user.password_hash):
            return None

        user.last_login = datetime.now()
        self.save_user(user)
        return user

    def create_session(self, user: UserProfile) -> Dict[str, Any]:
        """Create a session for a user."""
        session = UserAuth.create_session(user.user_id, user.username)
        session_path = self._get_session_path(session["session_id"])

        with open(session_path, "w", encoding="utf-8") as f:
            json.dump(session, f, ensure_ascii=False, indent=2)

        return session

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a session by ID."""
        session_path = self._get_session_path(session_id)
        if not session_path.exists():
            return None

        try:
            with open(session_path, "r", encoding="utf-8") as f:
                session = json.load(f)
                if UserAuth.is_session_valid(session):
                    return session
                else:
                    # Clean up expired session
                    session_path.unlink()
                    return None
        except Exception as e:
            logger.warning(f"Failed to load session {session_id}: {e}")
            return None

    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a session."""
        session_path = self._get_session_path(session_id)
        if not session_path.exists():
            return False

        try:
            session_path.unlink()
            return True
        except Exception as e:
            logger.error(f"Failed to invalidate session {session_id}: {e}")
            return False

    def list_users(self) -> List[Dict[str, Any]]:
        """List all users."""
        users = []

        for user_file in self.users_dir.glob("*.json"):
            try:
                with open(user_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    users.append(
                        {
                            "user_id": data.get("user_id"),
                            "username": data.get("username"),
                            "display_name": data.get("display_name"),
                            "created_at": data.get("created_at"),
                            "last_login": data.get("last_login"),
                            "is_active": data.get("is_active", True),
                            "is_admin": data.get("is_admin", False),
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to load user file {user_file}: {e}")

        return users

    def get_all_users_detailed(self) -> List[Dict[str, Any]]:
        """Get detailed information about all users (admin only)."""
        users = []

        for user_file in self.users_dir.glob("*.json"):
            try:
                with open(user_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    user = UserProfile.from_dict(data)
                    users.append(user.to_dict())
            except Exception as e:
                logger.warning(f"Failed to load user file {user_file}: {e}")

        return users

    def update_user_password(self, user_id: str, new_password: str) -> bool:
        """Update a user's password."""
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        user.password_hash = UserAuth.hash_password(new_password)
        user.updated_at = datetime.now()
        self.save_user(user)
        return True

    def update_user_profile(self, user_id: str, **kwargs) -> bool:
        """Update a user's profile."""
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        if "display_name" in kwargs:
            user.display_name = kwargs["display_name"]
        if "preferences" in kwargs:
            user.update_preferences(kwargs["preferences"])
        if "metadata" in kwargs:
            user.metadata.update(kwargs["metadata"])

        user.updated_at = datetime.now()
        self.save_user(user)
        return True

    def list_channel_configs(
        self,
        user_id: str,
        channel_type: str | None = None,
    ) -> Dict[str, list[dict[str, Any]]]:
        user = self.get_user_by_id(user_id)
        if not user:
            return {}
        self._ensure_portfolio_scaffold(user)
        if channel_type:
            file_path = self._get_channel_configs_file(user_id, channel_type)
            if not file_path.exists():
                return {channel_type: []}
            try:
                records = json.loads(file_path.read_text(encoding="utf-8"))
                if isinstance(records, list):
                    return {channel_type: records}
            except Exception:
                return {channel_type: []}
            return {channel_type: []}

        result: Dict[str, list[dict[str, Any]]] = {}
        channels_dir = self.get_portfolio_dir(user_id) / "channels"
        for f in channels_dir.glob("*.json"):
            ch = f.stem
            try:
                records = json.loads(f.read_text(encoding="utf-8"))
                result[ch] = records if isinstance(records, list) else []
            except Exception:
                result[ch] = []
        return result

    def save_channel_config(
        self,
        user_id: str,
        channel_type: str,
        name: str,
        config: Dict[str, Any],
        account_id: str | None = None,
        is_active: bool = True,
    ) -> dict[str, Any] | None:
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        self._ensure_portfolio_scaffold(user)
        channel_type = str(channel_type).strip().lower()
        file_path = self._get_channel_configs_file(user_id, channel_type)
        records: list[dict[str, Any]]
        if file_path.exists():
            try:
                loaded = json.loads(file_path.read_text(encoding="utf-8"))
                records = loaded if isinstance(loaded, list) else []
            except Exception:
                records = []
        else:
            records = []
        now = datetime.now().isoformat()
        target_id = account_id or str(uuid4())
        payload = {
            "account_id": target_id,
            "name": name.strip() or f"{channel_type}-{len(records) + 1}",
            "channel_type": channel_type,
            "config": config,
            "is_active": bool(is_active),
            "updated_at": now,
        }
        replaced = False
        for idx, item in enumerate(records):
            if item.get("account_id") == target_id:
                payload["created_at"] = item.get("created_at", now)
                records[idx] = payload
                replaced = True
                break
        if not replaced:
            payload["created_at"] = now
            records.append(payload)
        file_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def delete_channel_config(self, user_id: str, channel_type: str, account_id: str) -> bool:
        user = self.get_user_by_id(user_id)
        if not user:
            return False
        file_path = self._get_channel_configs_file(user_id, channel_type)
        if not file_path.exists():
            return False
        try:
            records = json.loads(file_path.read_text(encoding="utf-8"))
            if not isinstance(records, list):
                return False
            remain = [item for item in records if item.get("account_id") != account_id]
            file_path.write_text(json.dumps(remain, ensure_ascii=False, indent=2), encoding="utf-8")
            return len(remain) != len(records)
        except Exception:
            return False

    def map_identity(
        self,
        user_id: str,
        channel: str,
        external_id: str,
        alias: str = "",
        metadata: Dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if not self.get_user_by_id(user_id):
            return None
        channel_norm, external_norm = self._normalize_identity(channel, external_id)
        if not channel_norm or not external_norm:
            return None
        mappings = self._load_identity_mappings()
        now = datetime.now().isoformat()
        payload = {
            "mapping_id": str(uuid4()),
            "user_id": user_id,
            "channel": channel_norm,
            "external_id": external_norm,
            "alias": alias.strip(),
            "metadata": metadata or {},
            "created_at": now,
            "updated_at": now,
        }
        updated = False
        for idx, item in enumerate(mappings):
            same_identity = (
                item.get("channel") == channel_norm
                and item.get("external_id") == external_norm
            )
            same_user_identity = (
                item.get("user_id") == user_id
                and item.get("channel") == channel_norm
                and item.get("external_id") == external_norm
            )
            if same_identity or same_user_identity:
                payload["mapping_id"] = item.get("mapping_id", payload["mapping_id"])
                payload["created_at"] = item.get("created_at", now)
                mappings[idx] = payload
                updated = True
                break
        if not updated:
            mappings.append(payload)
        self._save_identity_mappings(mappings)
        return payload

    def resolve_user_by_identity(self, channel: str, external_id: str) -> Optional[str]:
        channel_norm, external_norm = self._normalize_identity(channel, external_id)
        mappings = self._load_identity_mappings()
        for item in mappings:
            if item.get("channel") == channel_norm and item.get("external_id") == external_norm:
                return item.get("user_id")
        return None

    def list_identity_mappings(self, user_id: str | None = None) -> list[dict[str, Any]]:
        mappings = self._load_identity_mappings()
        if user_id is None:
            return mappings
        return [item for item in mappings if item.get("user_id") == user_id]

    def delete_identity_mapping(self, mapping_id: str, user_id: str | None = None) -> bool:
        mappings = self._load_identity_mappings()
        remain: list[dict[str, Any]] = []
        deleted = False
        for item in mappings:
            if item.get("mapping_id") != mapping_id:
                remain.append(item)
                continue
            if user_id and item.get("user_id") != user_id:
                remain.append(item)
                continue
            deleted = True
        if deleted:
            self._save_identity_mappings(remain)
        return deleted
