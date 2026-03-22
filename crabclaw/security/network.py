"""Network security utilities for Crabclaw."""

import ipaddress
from urllib.parse import urlparse


def validate_url_target(url: str) -> tuple[bool, str]:
    """Validate that a URL target is safe to access (SSRF protection).
    
    This function checks if a URL points to a safe external address and not
    to internal/private network addresses that could be used for SSRF attacks.
    
    Args:
        url: The URL to validate.
        
    Returns:
        A tuple of (is_safe, error_message). If is_safe is True, error_message is empty.
    """
    try:
        parsed = urlparse(url)
        
        # Only allow HTTP and HTTPS schemes
        if parsed.scheme not in ('http', 'https'):
            return False, f"unsupported scheme: {parsed.scheme}"
        
        # Must have a hostname
        if not parsed.hostname:
            return False, "no hostname provided"
        
        # Check if hostname is an IP address
        try:
            ip = ipaddress.ip_address(parsed.hostname)
            
            # Block private IP ranges
            if ip.is_private:
                return False, f"private IP address: {ip}"
            
            # Block loopback addresses
            if ip.is_loopback:
                return False, f"loopback address: {ip}"
            
            # Block link-local addresses
            if ip.is_link_local:
                return False, f"link-local address: {ip}"
            
            # Block multicast addresses
            if ip.is_multicast:
                return False, f"multicast address: {ip}"
            
            # Block reserved addresses
            if ip.is_reserved:
                return False, f"reserved address: {ip}"
            
        except ValueError:
            # Hostname is not an IP address, check for localhost variants
            hostname_lower = parsed.hostname.lower()
            
            # Block localhost and local domain names
            localhost_variants = [
                'localhost',
                'localhost.localdomain',
                'localhost4',
                'localhost6',
                'ip6-localhost',
                'ip6-loopback',
            ]
            
            if hostname_lower in localhost_variants:
                return False, f"blocked hostname: {parsed.hostname}"
            
            # Block internal domain names
            if hostname_lower.endswith('.local') or hostname_lower.endswith('.internal'):
                return False, f"internal domain: {parsed.hostname}"
        
        # Block non-standard ports
        if parsed.port:
            # Block common internal service ports
            blocked_ports = {
                22,    # SSH
                23,    # Telnet
                25,    # SMTP
                53,    # DNS
                139,   # NetBIOS
                445,   # SMB
                3306,  # MySQL
                3389,  # RDP
                5432,  # PostgreSQL
                6379,  # Redis
                27017, # MongoDB
            }
            
            if parsed.port in blocked_ports:
                return False, f"blocked port: {parsed.port}"
        
        return True, ""
        
    except Exception as e:
        return False, f"validation error: {e}"
