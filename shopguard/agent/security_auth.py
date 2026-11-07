"""
ShopGuard AI - Agent Security & Authentication
Handles API key resolution, generation, validation, and timing-attack safe verification.
Enforces local security policies: local binding, unauthorized request rejection, secret isolation.
"""

import hmac
import os
import secrets
from typing import Optional
from fastapi import Header, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials

from ..utils.logger import get_logger

logger = get_logger("agent.auth")

DEFAULT_SECRET_FILE = "config/agent_api_key.secret"
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
BEARER_AUTH = HTTPBearer(auto_error=False)


class AgentAuthManager:
    """
    Manages API authentication tokens for the local security agent.
    Ensures secrets are stored outside source code and validated securely.
    """

    def __init__(self, secret_path: str = DEFAULT_SECRET_FILE):
        self.secret_path = os.path.abspath(secret_path)
        self._api_key = self._resolve_api_key()

    def _resolve_api_key(self) -> str:
        """
        Resolves the API key from:
        1. Environment variable 'SHOPGUARD_API_KEY'
        2. Persistent local secret file in config/
        3. Generates a new cryptographically secure key if none exists
        """
        # 1. Check environment
        env_key = os.environ.get("SHOPGUARD_API_KEY", "").strip()
        if env_key:
            logger.info("Local Security Agent API key loaded from environment variable (SHOPGUARD_API_KEY).")
            return env_key

        # 2. Check persistent secret file
        if os.path.isfile(self.secret_path):
            try:
                with open(self.secret_path, "r", encoding="utf-8") as f:
                    file_key = f.read().strip()
                if file_key:
                    logger.info(f"Local Security Agent API key loaded from secret file: {self.secret_path}")
                    return file_key
            except Exception as e:
                logger.error(f"Failed to read existing secret file '{self.secret_path}': {e}")

        # 3. Generate new 256-bit secure key
        new_key = secrets.token_hex(32)
        try:
            os.makedirs(os.path.dirname(self.secret_path), exist_ok=True)
            with open(self.secret_path, "w", encoding="utf-8") as f:
                f.write(new_key + "\n")
            logger.info(
                f"Generated new secure local agent API key and saved to: {self.secret_path} "
                "(File is protected in .gitignore)."
            )
        except Exception as e:
            logger.warning(f"Could not persist API key to '{self.secret_path}': {e}. Using in-memory ephemeral key.")

        return new_key

    @property
    def api_key(self) -> str:
        return self._api_key

    def validate_key(self, provided_key: Optional[str]) -> bool:
        """Timing-attack-safe comparison of provided key against active agent secret."""
        if not provided_key or not self._api_key:
            return False
        return hmac.compare_digest(provided_key.strip(), self._api_key)


# Global singleton auth manager
auth_manager = AgentAuthManager()


async def require_control_auth(
    request: Request,
    api_key_header: Optional[str] = Security(API_KEY_HEADER),
    bearer_token: Optional[HTTPAuthorizationCredentials] = Security(BEARER_AUTH),
) -> str:
    """
    FastAPI dependency enforcing strict authentication for control operations (arm/disarm).
    Accepts 'X-API-Key: <key>' or 'Authorization: Bearer <key>'.
    Rejects unauthorized requests with HTTP 401.
    """
    token = api_key_header
    if not token and bearer_token:
        token = bearer_token.credentials

    if not token or not auth_manager.validate_key(token):
        client_ip = request.client.host if request.client else "unknown"
        logger.warning(
            f"Unauthorized access attempt rejected on '{request.method} {request.url.path}' from {client_ip}."
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "UNAUTHORIZED",
                "message": "Invalid or missing API authentication credentials. Provide a valid 'X-API-Key' or 'Authorization: Bearer' header.",
            },
        )

    return token


async def optional_read_auth(
    request: Request,
    api_key_header: Optional[str] = Security(API_KEY_HEADER),
    bearer_token: Optional[HTTPAuthorizationCredentials] = Security(BEARER_AUTH),
) -> Optional[str]:
    """
    Optional authentication for read operations. If provided, validates key.
    """
    token = api_key_header
    if not token and bearer_token:
        token = bearer_token.credentials

    if token and not auth_manager.validate_key(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "UNAUTHORIZED",
                "message": "The provided API authentication key is invalid.",
            },
        )
    return token
