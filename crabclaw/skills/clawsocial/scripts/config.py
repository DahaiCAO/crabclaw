"""Configuration for ClawSocial skills."""
import os
from typing import Optional, Dict, Any


class ClawSocialConfig:
    """ClawSocial configuration."""
    
    def __init__(self):
        self._config = None
        self._load_config()
    
    def _load_config(self):
        """Load configuration from config.json."""
        try:
            from crabclaw.config.loader import load_config
            self._config = load_config()
        except Exception:
            self._config = None
    
    @property
    def clawsociety_enabled(self) -> bool:
        """Check if ClawSociety is globally enabled."""
        if self._config:
            return getattr(self._config, "clawsociety_enabled", False)
        return False
    
    @property
    def clawsocial_connections(self) -> Dict[str, Dict[str, Any]]:
        """Get all ClawSocial connections from config."""
        if self._config:
            return getattr(self._config, "clawsocial_connections", {})
        return {}
    
    @property
    def enabled_connections(self) -> Dict[str, Dict[str, Any]]:
        """Get all enabled ClawSocial connections."""
        connections = self.clawsocial_connections
        return {
            conn_id: conn
            for conn_id, conn in connections.items()
            if conn.get("enabled", False)
        }
    
    @property
    def active_connection(self) -> Optional[Dict[str, Any]]:
        """Get the first enabled ClawSocial connection (for backward compatibility)."""
        connections = self.enabled_connections
        if connections:
            return next(iter(connections.values()))
        return None
    
    @property
    def router_url(self) -> str:
        """Get ClawLink router URL (for backward compatibility).
        
        Priority:
        1. First enabled connection from config.json
        2. Legacy clawsocial_url from config.json
        3. Environment variable CLAWLINK_ROUTER_URL
        4. Default: http://localhost:8000
        """
        active_conn = self.active_connection
        if active_conn and "url" in active_conn:
            return active_conn["url"]
        
        if self._config:
            legacy_url = getattr(self._config, "clawsocial_url", None)
            if legacy_url:
                return legacy_url
        
        return os.getenv("CLAWLINK_ROUTER_URL", "http://localhost:8000")
    
    @property
    def timeout_sec(self) -> float:
        """Get timeout in seconds."""
        return float(os.getenv("CLAWLINK_TIMEOUT_SEC", "10.0"))
    
    def refresh_config(self):
        """Refresh configuration from disk."""
        self._load_config()


config = ClawSocialConfig()