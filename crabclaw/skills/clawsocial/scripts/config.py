"""Configuration for ClawSocial skills."""
import os


class ClawSocialConfig:
    """ClawSocial configuration."""
    
    @property
    def router_url(self):
        """Get ClawLink router URL."""
        return os.getenv("CLAWLINK_ROUTER_URL", "http://localhost:8000")
    
    @property
    def timeout_sec(self):
        """Get timeout in seconds."""
        return float(os.getenv("CLAWLINK_TIMEOUT_SEC", "10.0"))


config = ClawSocialConfig()