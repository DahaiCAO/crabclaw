"""Web tools: web_search and web_fetch with enhanced security."""

import asyncio
import html
import json
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from loguru import logger

from crabclaw.agent.tools.base import Tool

# Security constants
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_2) AppleWebKit/537.36"
MAX_REDIRECTS = 3  # Reduced from 5 to prevent DoS attacks
DEFAULT_TIMEOUT = 15.0  # Reduced from 30s
MAX_TIMEOUT = 60.0  # Maximum allowed timeout
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB max content size
MAX_RESPONSE_SIZE = 5 * 1024 * 1024  # 5MB max response size

# Blocked URL patterns (private networks, localhost, etc.)
BLOCKED_URL_PATTERNS = [
    r'^https?://127\.\d+\.\d+\.\d+',  # localhost
    r'^https?://10\.\d+\.\d+\.\d+',  # private 10.x.x.x
    r'^https?://172\.(1[6-9]|2[0-9]|3[01])\.\d+\.\d+',  # private 172.16-31.x.x
    r'^https?://192\.168\.\d+\.\d+',  # private 192.168.x.x
    r'^https?://0\.0\.0\.0',
    r'^https?://localhost',
    r'^https?://\[::1\]',
    r'^file://',
    r'^ftp://',
    r'^sftp://',
    r'^data:text/html',
]

# Blocked content types
BLOCKED_CONTENT_TYPES = [
    'application/octet-stream',
    'application/x-msdownload',
    'application/x-executable',
    'application/x-dosexec',
    'application/java-archive',
    'application/x-shockwave-flash',
]


def _strip_tags(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = re.sub(r'<script[\s\S]*?</script>', '', text, flags=re.I)
    text = re.sub(r'<style[\s\S]*?</style>', '', text, flags=re.I)
    text = re.sub(r'<[^>]+>', '', text)
    return html.unescape(text).strip()


def _normalize(text: str) -> str:
    """Normalize whitespace."""
    text = re.sub(r'[ \t]+', ' ', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def _validate_url(url: str, allow_private: bool = False) -> tuple[bool, str]:
    """
    Validate URL: must be http(s) with valid domain.
    
    Args:
        url: URL to validate
        allow_private: Whether to allow private network addresses
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Check URL length
        if len(url) > 2048:
            return False, "URL too long (max 2048 characters)"
        
        p = urlparse(url)
        
        # Check scheme
        if p.scheme not in ('http', 'https'):
            return False, f"Only http/https allowed, got '{p.scheme or 'none'}'"
        
        # Check for empty netloc
        if not p.netloc:
            return False, "Missing domain"
        
        # Check for blocked patterns (private networks, etc.)
        if not allow_private:
            for pattern in BLOCKED_URL_PATTERNS:
                if re.match(pattern, url, re.IGNORECASE):
                    return False, f"URL matches blocked pattern: {pattern}"
        
        # Check for suspicious characters
        if '\x00' in url or '\n' in url or '\r' in url:
            return False, "URL contains invalid characters"
        
        # Check port
        if p.port and (p.port < 1 or p.port > 65535):
            return False, f"Invalid port number: {p.port}"
        
        return True, ""
    except Exception as e:
        return False, f"URL validation error: {str(e)}"


def _is_content_type_blocked(content_type: str) -> bool:
    """Check if content type is blocked."""
    content_type_lower = content_type.lower()
    for blocked in BLOCKED_CONTENT_TYPES:
        if blocked in content_type_lower:
            return True
    return False


class WebSearchTool(Tool):
    """Search the web using Brave Search API with enhanced security."""

    name = "web_search"
    description = "Search the web. Returns titles, URLs, and snippets."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "count": {"type": "integer", "description": "Results (1-10)", "minimum": 1, "maximum": 10}
        },
        "required": ["query"]
    }

    def __init__(
        self, 
        api_key: str | None = None, 
        max_results: int = 5, 
        proxy: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self._init_api_key = api_key
        self.max_results = max_results
        self.proxy = proxy
        self.timeout = min(timeout, MAX_TIMEOUT)
        
        # Rate limiting
        self._request_semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests
        self._last_request_time = 0
        self._min_request_interval = 0.5  # Minimum 0.5s between requests

    @property
    def api_key(self) -> str:
        """Resolve API key at call time so env/config changes are picked up."""
        return self._init_api_key or os.environ.get("BRAVE_API_KEY", "")

    async def execute(self, query: str, count: int | None = None, **kwargs: Any) -> str:
        # Validate query
        if not query or len(query.strip()) == 0:
            return "Error: Empty search query"
        
        if len(query) > 500:
            return "Error: Search query too long (max 500 characters)"
        
        if not self.api_key:
            return (
                "Error: Brave Search API key not configured. Set it in "
                "~/.crabclaw/config.json under tools.web.search.apiKey "
                "(or export BRAVE_API_KEY), then restart the gateway."
            )

        async with self._request_semaphore:
            # Rate limiting
            current_time = asyncio.get_event_loop().time()
            time_since_last = current_time - self._last_request_time
            if time_since_last < self._min_request_interval:
                await asyncio.sleep(self._min_request_interval - time_since_last)
            
            try:
                n = min(max(count or self.max_results, 1), 10)
                logger.debug("WebSearch: {}", "proxy enabled" if self.proxy else "direct connection")
                
                # Create client with security settings
                limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
                async with httpx.AsyncClient(
                    proxy=self.proxy,
                    limits=limits,
                    timeout=httpx.Timeout(self.timeout, connect=5.0),
                ) as client:
                    r = await client.get(
                        "https://api.search.brave.com/res/v1/web/search",
                        params={"q": query, "count": n},
                        headers={
                            "Accept": "application/json", 
                            "X-Subscription-Token": self.api_key,
                            "User-Agent": USER_AGENT,
                        },
                    )
                    r.raise_for_status()

                results = r.json().get("web", {}).get("results", [])[:n]
                if not results:
                    return f"No results for: {query}"

                lines = [f"Results for: {query}\n"]
                for i, item in enumerate(results, 1):
                    lines.append(f"{i}. {item.get('title', '')}\n   {item.get('url', '')}")
                    if desc := item.get("description"):
                        lines.append(f"   {desc}")
                
                self._last_request_time = asyncio.get_event_loop().time()
                return "\n".join(lines)
                
            except httpx.TimeoutException:
                logger.error("WebSearch timeout for query: {}", query[:50])
                return "Error: Search request timed out"
            except httpx.ProxyError as e:
                logger.error("WebSearch proxy error: {}", e)
                return f"Proxy error: {e}"
            except httpx.HTTPStatusError as e:
                logger.error("WebSearch HTTP error: {} - {}", e.response.status_code, e.response.text[:200])
                return f"Search API error: {e.response.status_code}"
            except Exception as e:
                logger.error("WebSearch error: {}", e)
                return f"Error: {e}"


class WebFetchTool(Tool):
    """Fetch and extract content from a URL using Readability with enhanced security."""

    name = "web_fetch"
    description = "Fetch URL and extract readable content (HTML → markdown/text)."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
            "extractMode": {"type": "string", "enum": ["markdown", "text"], "default": "markdown"},
            "maxChars": {"type": "integer", "minimum": 100, "maximum": 100000}
        },
        "required": ["url"]
    }

    def __init__(
        self, 
        max_chars: int = 50000, 
        proxy: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        allow_private: bool = False,
    ):
        self.max_chars = min(max_chars, 100000)  # Cap at 100k
        self.proxy = proxy
        self.timeout = min(timeout, MAX_TIMEOUT)
        self.allow_private = allow_private
        
        # Rate limiting
        self._request_semaphore = asyncio.Semaphore(3)  # Max 3 concurrent fetches
        self._last_request_time = 0
        self._min_request_interval = 1.0  # Minimum 1s between requests
        
        # Domain rate limiting
        self._domain_last_request: dict[str, float] = {}
        self._domain_min_interval = 2.0  # Minimum 2s between requests to same domain

    async def execute(self, url: str, extractMode: str = "markdown", maxChars: int | None = None, **kwargs: Any) -> str:
        from readability import Document

        max_chars = min(maxChars or self.max_chars, 100000)
        
        # Validate URL
        is_valid, error_msg = _validate_url(url, self.allow_private)
        if not is_valid:
            return json.dumps({"error": f"URL validation failed: {error_msg}", "url": url}, ensure_ascii=False)

        # Parse domain for rate limiting
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        async with self._request_semaphore:
            # Global rate limiting
            current_time = asyncio.get_event_loop().time()
            time_since_last = current_time - self._last_request_time
            if time_since_last < self._min_request_interval:
                await asyncio.sleep(self._min_request_interval - time_since_last)
            
            # Domain-specific rate limiting
            if domain in self._domain_last_request:
                domain_time_since = current_time - self._domain_last_request[domain]
                if domain_time_since < self._domain_min_interval:
                    await asyncio.sleep(self._domain_min_interval - domain_time_since)

            try:
                logger.debug("WebFetch: {}", "proxy enabled" if self.proxy else "direct connection")
                
                # Create client with security settings
                limits = httpx.Limits(max_connections=5, max_keepalive_connections=3)
                async with httpx.AsyncClient(
                    follow_redirects=True,
                    max_redirects=MAX_REDIRECTS,
                    timeout=httpx.Timeout(self.timeout, connect=5.0, read=10.0),
                    proxy=self.proxy,
                    limits=limits,
                ) as client:
                    # Stream the response to check size
                    async with client.stream(
                        "GET", 
                        url, 
                        headers={"User-Agent": USER_AGENT},
                    ) as response:
                        # Check status
                        response.raise_for_status()
                        
                        # Check content type
                        content_type = response.headers.get("content-type", "").lower()
                        if _is_content_type_blocked(content_type):
                            return json.dumps({
                                "error": f"Content type blocked: {content_type}", 
                                "url": url
                            }, ensure_ascii=False)
                        
                        # Check content length
                        content_length = response.headers.get("content-length")
                        if content_length:
                            try:
                                length = int(content_length)
                                if length > MAX_CONTENT_LENGTH:
                                    return json.dumps({
                                        "error": f"Content too large: {length} bytes (max {MAX_CONTENT_LENGTH})", 
                                        "url": url
                                    }, ensure_ascii=False)
                            except ValueError:
                                pass
                        
                        # Read response with size limit
                        content = b""
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            content += chunk
                            if len(content) > MAX_RESPONSE_SIZE:
                                return json.dumps({
                                    "error": f"Response too large (max {MAX_RESPONSE_SIZE} bytes)", 
                                    "url": url
                                }, ensure_ascii=False)
                        
                        text = content.decode('utf-8', errors='replace')

                # Process content
                if "application/json" in content_type:
                    try:
                        parsed_json = json.loads(text)
                        result_text = json.dumps(parsed_json, indent=2, ensure_ascii=False)
                        extractor = "json"
                    except json.JSONDecodeError:
                        result_text = text
                        extractor = "raw"
                elif "text/html" in content_type or text[:256].lower().startswith(("<!doctype", "<html")):
                    try:
                        doc = Document(text)
                        summary = doc.summary()
                        if extractMode == "markdown":
                            content = self._to_markdown(summary)
                        else:
                            content = _strip_tags(summary)
                        title = doc.title() or ""
                        result_text = f"# {title}\n\n{content}" if title else content
                        extractor = "readability"
                    except Exception as e:
                        logger.warning("Readability extraction failed for {}: {}", url, e)
                        result_text = _strip_tags(text)
                        extractor = "stripped_html"
                else:
                    result_text = text
                    extractor = "raw"

                # Truncate if needed
                truncated = len(result_text) > max_chars
                if truncated:
                    result_text = result_text[:max_chars]

                # Update rate limit timestamps
                self._last_request_time = asyncio.get_event_loop().time()
                self._domain_last_request[domain] = self._last_request_time

                return json.dumps({
                    "url": url, 
                    "finalUrl": str(response.url), 
                    "status": response.status_code,
                    "extractor": extractor, 
                    "truncated": truncated, 
                    "length": len(result_text), 
                    "text": result_text
                }, ensure_ascii=False)
                
            except httpx.TimeoutException:
                logger.error("WebFetch timeout for {}: {}", url)
                return json.dumps({"error": "Request timed out", "url": url}, ensure_ascii=False)
            except httpx.TooManyRedirects:
                logger.error("WebFetch too many redirects for {}: {}", url)
                return json.dumps({"error": f"Too many redirects (max {MAX_REDIRECTS})", "url": url}, ensure_ascii=False)
            except httpx.ProxyError as e:
                logger.error("WebFetch proxy error for {}: {}", url, e)
                return json.dumps({"error": f"Proxy error: {e}", "url": url}, ensure_ascii=False)
            except httpx.HTTPStatusError as e:
                logger.error("WebFetch HTTP error for {}: {} - {}", url, e.response.status_code, e.response.text[:200])
                return json.dumps({"error": f"HTTP {e.response.status_code}", "url": url}, ensure_ascii=False)
            except Exception as e:
                logger.error("WebFetch error for {}: {}", url, e)
                return json.dumps({"error": str(e), "url": url}, ensure_ascii=False)

    def _to_markdown(self, html: str) -> str:
        """Convert HTML to markdown."""
        # Convert links, headings, lists before stripping tags
        text = re.sub(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',
                      lambda m: f'[{_strip_tags(m[2])}]({m[1]})', html, flags=re.I)
        text = re.sub(r'<h([1-6])[^>]*>([\s\S]*?)</h\1>',
                      lambda m: f'\n{"#" * int(m[1])} {_strip_tags(m[2])}\n', text, flags=re.I)
        text = re.sub(r'<li[^>]*>([\s\S]*?)</li>', lambda m: f'\n- {_strip_tags(m[1])}', text, flags=re.I)
        text = re.sub(r'</(p|div|section|article)>', '\n\n', text, flags=re.I)
        text = re.sub(r'<(br|hr)\s*/?>', '\n', text, flags=re.I)
        return _normalize(_strip_tags(text))
