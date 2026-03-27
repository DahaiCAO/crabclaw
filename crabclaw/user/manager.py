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
        self.sessions_dir = ensure_dir(self.workspace / "sessions")
        self.portfolios_dir = ensure_dir(self.workspace / "portfolios")
        self._cache: Dict[str, UserProfile] = {}
        # Create default admin user if not exists
        self._ensure_default_admin()

    def _get_user_path(self, user_id: str) -> Path:
        """Get the file path for a user."""
        return self.get_portfolio_dir(user_id) / "portfolio.json"

    def _get_session_path(self, session_id: str) -> Path:
        """Get the file path for a session."""
        return self.sessions_dir / f"session_{session_id}.json"

    def _get_channel_configs_file(self, user_id: str, channel_type: str) -> Path:
        channel_key = safe_filename(str(channel_type).strip().lower())
        return self.get_portfolio_dir(user_id) / "channels" / channel_key / f"{channel_key}.json"

    def _load_channel_records(self, user_id: str, channel_type: str) -> list[dict[str, Any]]:
        file_path = self._get_channel_configs_file(user_id, channel_type)
        if not file_path.exists():
            return []
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to load channel config file {file_path}: {e}")
            return []

        if not isinstance(payload, list):
            return []

        records: list[dict[str, Any]] = []
        for idx, item in enumerate(payload):
            if not isinstance(item, dict):
                continue
            records.append(self._normalize_channel_record(channel_type, item, idx))
        return records

    def _save_channel_records(self, user_id: str, channel_type: str, records: list[dict[str, Any]]) -> None:
        file_path = self._get_channel_configs_file(user_id, channel_type)
        normalized = [
            self._normalize_channel_record(channel_type, item, idx)
            for idx, item in enumerate(records)
            if isinstance(item, dict)
        ]
        ensure_dir(file_path.parent)
        
        # Custom JSON serialization to handle allow_from compactly
        def custom_serializer(obj):
            if isinstance(obj, dict):
                # For allow_from field, use compact format
                if 'config' in obj and isinstance(obj['config'], dict) and 'allow_from' in obj['config']:
                    config = obj['config'].copy()
                    if isinstance(config['allow_from'], list):
                        # Create a compact version for allow_from
                        compact_config = obj.copy()
                        compact_config['config'] = config.copy()
                        # Convert allow_from to compact format
                        compact_config['config']['allow_from'] = config['allow_from']
                        return compact_config
                return obj
            return obj
        
        # First serialize with indent for readability
        json_str = json.dumps(normalized, ensure_ascii=False, indent=2)
        
        # Then compact the allow_from fields
        import re
        # Pattern to match allow_from with indentation and newlines
        pattern = r'"allow_from":\s*\[\s*"\*"\s*\]'
        # Replace with compact format
        json_str = re.sub(pattern, '"allow_from": ["*"]', json_str)
        
        # Also handle multi-line format
        multi_line_pattern = r'"allow_from":\s*\[\s*\n\s*"\*"\s*\n\s*\]'
        json_str = re.sub(multi_line_pattern, '"allow_from": ["*"]', json_str)
        
        file_path.write_text(json_str, encoding="utf-8")

    def _normalize_channel_record(
        self,
        channel_type: str,
        record: dict[str, Any],
        index: int = 0,
    ) -> dict[str, Any]:
        now = datetime.now().isoformat()
        config = record.get("config")
        is_active = bool(record.get("is_active", False))
        runtime_status = str(record.get("runtime_status") or ("running" if is_active else "stopped"))
        return {
            "account_id": str(record.get("account_id") or uuid4()),
            "name": str(record.get("name") or f"{channel_type}-{index + 1}").strip() or f"{channel_type}-{index + 1}",
            "channel_type": str(record.get("channel_type") or channel_type).strip().lower(),
            "config": config if isinstance(config, dict) else {},
            "is_active": is_active,
            "runtime_status": runtime_status,
            "created_at": record.get("created_at") or now,
            "updated_at": record.get("updated_at") or now,
            "started_at": record.get("started_at"),
            "stopped_at": record.get("stopped_at"),
            "last_error": str(record.get("last_error") or ""),
        }

    def _get_identity_mappings_file(self, user_id: str) -> Path:
        return self.get_portfolio_dir(user_id) / "channels" / "channel_identity_mappings.json"

    def _normalize_identity_mapping_record(
        self,
        record: dict[str, Any],
        *,
        user_id_fallback: str = "",
    ) -> dict[str, Any] | None:
        if not isinstance(record, dict):
            return None
        user_id = str(record.get("user_id") or user_id_fallback).strip()
        channel, external_id = self._normalize_identity(
            str(record.get("channel", "")),
            str(record.get("external_id", "")),
        )
        if not user_id or not channel or not external_id:
            return None
        now = datetime.now().isoformat()
        metadata = record.get("metadata")
        return {
            "mapping_id": str(record.get("mapping_id") or uuid4()),
            "user_id": user_id,
            "channel": channel,
            "external_id": external_id,
            "alias": str(record.get("alias") or "").strip(),
            "metadata": metadata if isinstance(metadata, dict) else {},
            "created_at": record.get("created_at") or now,
            "updated_at": record.get("updated_at") or now,
        }

    def _load_identity_records_from_file(
        self,
        file_path: Path,
        *,
        user_id_fallback: str = "",
    ) -> list[dict[str, Any]]:
        if not file_path.exists():
            return []
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
            raw = payload.get("mappings", []) if isinstance(payload, dict) else payload
            if not isinstance(raw, list):
                return []
        except Exception as e:
            logger.warning(f"Failed to load identity mappings from {file_path}: {e}")
            return []

        records: list[dict[str, Any]] = []
        for item in raw:
            normalized = self._normalize_identity_mapping_record(item, user_id_fallback=user_id_fallback)
            if normalized:
                records.append(normalized)
        return records

    def _save_identity_records_to_file(self, file_path: Path, mappings: list[dict[str, Any]]) -> None:
        normalized = []
        for item in mappings:
            normalized_item = self._normalize_identity_mapping_record(item)
            if normalized_item:
                normalized.append(normalized_item)
        ensure_dir(file_path.parent)
        file_path.write_text(
            json.dumps({"version": 1, "mappings": normalized}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_identity_mappings_from_portfolios(self, user_id: str | None = None) -> list[dict[str, Any]]:
        if user_id:
            file_path = self._get_identity_mappings_file(user_id)
            return self._load_identity_records_from_file(file_path, user_id_fallback=user_id)

        records: list[dict[str, Any]] = []
        for portfolio_dir in self.portfolios_dir.iterdir():
            if not portfolio_dir.is_dir():
                continue
            records.extend(
                self._load_identity_records_from_file(
                    portfolio_dir / "channels" / "channel_identity_mappings.json",
                    user_id_fallback=portfolio_dir.name,
                )
            )
        return records

    def _save_identity_mappings_to_portfolios(
        self,
        mappings: list[dict[str, Any]],
        user_id: str | None = None,
    ) -> None:
        if user_id:
            own = [item for item in mappings if str(item.get("user_id")) == user_id]
            self._save_identity_records_to_file(self._get_identity_mappings_file(user_id), own)
            return

        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in mappings:
            normalized = self._normalize_identity_mapping_record(item)
            if not normalized:
                continue
            grouped.setdefault(normalized["user_id"], []).append(normalized)

        existing_files = [
            p / "channels" / "channel_identity_mappings.json"
            for p in self.portfolios_dir.iterdir()
            if p.is_dir()
        ]
        for file_path in existing_files:
            if file_path.exists():
                user_key = file_path.parent.parent.name
                if user_key not in grouped:
                    file_path.unlink(missing_ok=True)

        for uid, items in grouped.items():
            self._save_identity_records_to_file(self._get_identity_mappings_file(uid), items)

    def _load_identity_mappings(self, user_id: str | None = None) -> list[dict[str, Any]]:
        return self._load_identity_mappings_from_portfolios(user_id=user_id)

    def _save_identity_mappings(self, mappings: list[dict[str, Any]], user_id: str | None = None) -> None:
        self._save_identity_mappings_to_portfolios(mappings, user_id=user_id)

    @staticmethod
    def _normalize_identity(channel: str, external_id: str) -> tuple[str, str]:
        return (str(channel).strip().lower(), str(external_id).strip())

    def get_portfolio_dir(self, user_id: str) -> Path:
        safe_id = safe_filename(user_id)
        return self.portfolios_dir / safe_id

    def _ensure_portfolio_scaffold(self, user: UserProfile) -> Path:
        portfolio_dir = ensure_dir(self.get_portfolio_dir(user.user_id))
        
        # Core scaffold directories
        dirs_to_create = [
            "history",
            "memory",
            "channels",
            "channels/email",
            "channels/feishu",
            "channels/slack",
            "channels/telegram",
            "channels/discord",
            "channels/dingtalk",
            "assets",
            "assets/images",
            "assets/videos",
            "assets/files",
        ]
        
        for d in dirs_to_create:
            ensure_dir(portfolio_dir / d)
            
        profile_file = portfolio_dir / "portfolio.json"
        if not profile_file.exists():
            profile_file.write_text(
                json.dumps(user.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return portfolio_dir

    def _read_user_payload(self, file_path: Path) -> dict[str, Any] | None:
        if not file_path.exists():
            return None
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to load user file {file_path}: {e}")
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def _user_from_payload(self, payload: dict[str, Any]) -> Optional[UserProfile]:
        required = ("user_id", "username", "display_name", "password_hash")
        if not all(payload.get(key) for key in required):
            return None
        try:
            return UserProfile.from_dict(payload)
        except Exception as e:
            logger.warning(f"Failed to parse user payload: {e}")
            return None

    def _load_user_from_path(self, file_path: Path) -> Optional[UserProfile]:
        payload = self._read_user_payload(file_path)
        if not payload:
            return None
        return self._user_from_payload(payload)

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
        for portfolio_dir in self.portfolios_dir.iterdir():
            if not portfolio_dir.is_dir():
                continue
            profile_path = portfolio_dir / "portfolio.json"
            payload = self._read_user_payload(profile_path)
            if not payload:
                continue
            if payload.get("username") != username:
                continue
            user = self._user_from_payload(payload)
            if user:
                self._cache[user.user_id] = user
                return user
        return None

    def _load_user(self, user_id: str) -> Optional[UserProfile]:
        """Load a user from disk."""
        path = self._get_user_path(user_id)
        user = self._load_user_from_path(path)
        if user:
            return user
        return None

    def save_user(self, user: UserProfile) -> None:
        """Save a user to disk."""
        path = self._get_user_path(user.user_id)
        ensure_dir(path.parent)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(user.to_dict(), f, ensure_ascii=False, indent=2)

        self._cache[user.user_id] = user

    def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        path = self._get_user_path(user_id)
        portfolio_dir = self.get_portfolio_dir(user_id)
        if not path.exists() and not portfolio_dir.exists():
            return False

        try:
            if path.exists():
                path.unlink()
            self._cache.pop(user_id, None)
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
        seen: set[str] = set()
        for portfolio_dir in self.portfolios_dir.iterdir():
            if not portfolio_dir.is_dir():
                continue
            profile_path = portfolio_dir / "portfolio.json"
            payload = self._read_user_payload(profile_path)
            if not payload:
                continue
            user = self._user_from_payload(payload)
            if not user or user.user_id in seen:
                continue
            seen.add(user.user_id)
            users.append(
                {
                    "user_id": user.user_id,
                    "username": user.username,
                    "display_name": user.display_name,
                    "created_at": user.created_at.isoformat(),
                    "last_login": user.last_login.isoformat() if user.last_login else None,
                    "is_active": user.is_active,
                    "is_admin": user.is_admin,
                }
            )

        return users

    def get_all_users_detailed(self) -> List[Dict[str, Any]]:
        """Get detailed information about all users (admin only)."""
        users = []
        seen: set[str] = set()
        for portfolio_dir in self.portfolios_dir.iterdir():
            if not portfolio_dir.is_dir():
                continue
            profile_path = portfolio_dir / "portfolio.json"
            payload = self._read_user_payload(profile_path)
            if not payload:
                continue
            user = self._user_from_payload(payload)
            if not user or user.user_id in seen:
                continue
            seen.add(user.user_id)
            users.append(user.to_dict())

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
            return {channel_type: self._load_channel_records(user_id, channel_type)}

        result: Dict[str, list[dict[str, Any]]] = {}
        channels_dir = self.get_portfolio_dir(user_id) / "channels"
        for channel_dir in channels_dir.iterdir():
            if not channel_dir.is_dir():
                continue
            channel_key = channel_dir.name
            channel_file = channel_dir / f"{channel_key}.json"
            if not channel_file.exists():
                continue
            result[channel_key] = self._load_channel_records(user_id, channel_key)
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
        records = self._load_channel_records(user_id, channel_type)
        now = datetime.now().isoformat()
        target_id = account_id or str(uuid4())
        payload = {
            "account_id": target_id,
            "name": name.strip() or f"{channel_type}-{len(records) + 1}",
            "channel_type": channel_type,
            "config": config if isinstance(config, dict) else {},
            "is_active": bool(is_active),
            "runtime_status": "running" if is_active else "stopped",
            "updated_at": now,
            "last_error": "",
        }
        replaced = False
        for idx, item in enumerate(records):
            if item.get("account_id") == target_id:
                payload["created_at"] = item.get("created_at", now)
                payload["started_at"] = item.get("started_at")
                payload["stopped_at"] = item.get("stopped_at")
                if bool(item.get("is_active")) != bool(is_active):
                    if is_active:
                        payload["started_at"] = now
                    else:
                        payload["stopped_at"] = now
                records[idx] = payload
                replaced = True
                break
        if not replaced:
            payload["created_at"] = now
            payload["started_at"] = now if is_active else None
            payload["stopped_at"] = None if is_active else now
            records.append(payload)
        self._save_channel_records(user_id, channel_type, records)
        return self._normalize_channel_record(channel_type, payload)

    def set_channel_config_active(
        self,
        user_id: str,
        channel_type: str,
        account_id: str,
        is_active: bool,
    ) -> dict[str, Any] | None:
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        channel_type = str(channel_type).strip().lower()
        records = self._load_channel_records(user_id, channel_type)
        now = datetime.now().isoformat()
        for idx, item in enumerate(records):
            if item.get("account_id") != account_id:
                continue
            item["is_active"] = bool(is_active)
            item["runtime_status"] = "running" if is_active else "stopped"
            item["updated_at"] = now
            item["last_error"] = ""
            if is_active:
                item["started_at"] = now
            else:
                item["stopped_at"] = now
            records[idx] = self._normalize_channel_record(channel_type, item, idx)
            self._save_channel_records(user_id, channel_type, records)
            return records[idx]
        return None

    def delete_channel_config(self, user_id: str, channel_type: str, account_id: str) -> bool:
        user = self.get_user_by_id(user_id)
        if not user:
            return False
        channel_type = str(channel_type).strip().lower()
        file_path = self._get_channel_configs_file(user_id, channel_type)
        if not file_path.exists():
            return False
        try:
            records = self._load_channel_records(user_id, channel_type)
            remain = [item for item in records if item.get("account_id") != account_id]
            self._save_channel_records(user_id, channel_type, remain)
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
        if user_id is None:
            return self._load_identity_mappings()
        return self._load_identity_mappings(user_id=user_id)

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
