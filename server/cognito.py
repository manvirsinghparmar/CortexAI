"""Amazon Cognito JWT validation and token exchange for server-side auth.

Validates ID tokens issued by Cognito (e.g. from Google IdP). Uses JWKS from
Cognito user pool. Configure via COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID,
COGNITO_REGION, COGNITO_DOMAIN. Optional COGNITO_CLIENT_SECRET for token exchange.
"""

import ssl
import json
import os
import urllib.parse
import urllib.request
import jwt
from dataclasses import dataclass
from typing import Any
from utils.logger import get_logger

logger = get_logger(__name__)

# Lazy import to avoid requiring PyJWT when Cognito is not configured
_jwks_client = None


def _cognito_enabled() -> bool:
    pool_id = (os.getenv("COGNITO_USER_POOL_ID") or "").strip()
    client_id = (os.getenv("COGNITO_CLIENT_ID") or "").strip()
    region = (os.getenv("COGNITO_REGION") or "").strip()
    return bool(pool_id and client_id and region)


def _jwks_url() -> str:
    region = (os.getenv("COGNITO_REGION") or "").strip()
    pool_id = (os.getenv("COGNITO_USER_POOL_ID") or "").strip()
    return f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json"


def _get_jwks_client():
    global _jwks_client
    if _jwks_client is None:
        import jwt
        url = _jwks_url()
        _jwks_client = jwt.PyJWKClient(url, cache_jwk_set=True, lifespan=3600)
    return _jwks_client

def get_cognito_public_keys():
    """Get public keys from Cognito JWKS endpoint"""
    url = _jwks_url()
    #Remove _create_unverified_context from ssl
    response = urllib.request.urlopen(url, context=ssl._create_unverified_context() , timeout=15)
    return json.loads(response.read().decode())

@dataclass(frozen=True)
class CognitoClaims:
    """Verified claims from Cognito ID token."""

    sub: str
    email: str | None
    email_verified: bool
    iss: str
    aud: str
    token_use: str

    @property
    def display_email(self) -> str:
        return self.email or self.sub


def verify_cognito_id_token(token: str) -> CognitoClaims | None:
    """
    Verify a Cognito ID token (e.g. from Google sign-in via Cognito).

    Returns CognitoClaims if valid, None otherwise.
    """
    if not _cognito_enabled():
        return None
    
    pool_id = (os.getenv("COGNITO_USER_POOL_ID") or "").strip()
    client_id = (os.getenv("COGNITO_CLIENT_ID") or "").strip()
    region = (os.getenv("COGNITO_REGION") or "").strip()
    expected_issuer = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"
    #print(f"expected_issuer: {expected_issuer}")
    try:
        #print(f"importing jwt")
        #import jwt
        #print(f"imported jwt")
        
        #print(f"getting jwks client")
        client = _get_jwks_client()
        #except Exception as e:
        #    #print(f"error: {e}")
        #    return None
        #print(f"client: {client}")
        # Get the key ID from token header
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header['kid']
        #print(f"kid: {kid}")
        # Get public keys
        jwks = get_cognito_public_keys()
        #print(f"jwks: {jwks}")
        signing_key = None
        for jwk in jwks['keys']:
            if jwk['kid'] == kid:
                signing_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
                break
        
        #signing_key = client.get_signing_key_from_jwt(token)
       # print(f"signing_key: {signing_key}")
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=expected_issuer,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": True,
                "verify_iss": True,
            },
        )
        #print(f"payload: {payload}")
    except Exception as e:
        logger.debug("Cognito token verification failed: %s", e)
        return None

    token_use = payload.get("token_use")
    if token_use != "id":
        logger.debug("Cognito token_use is not 'id': %s", token_use)
        return None
    #print(f"payload: {payload}")
    return CognitoClaims(
        sub=str(payload.get("sub", "")),
        email=payload.get("email"),
        email_verified=bool(payload.get("email_verified", False)),
        iss=str(payload.get("iss", "")),
        aud=str(payload.get("aud", "")),
        token_use=str(token_use),
    )


def cognito_enabled() -> bool:
    """Return True if Cognito auth is configured."""
    return _cognito_enabled()


def get_cognito_config_for_frontend() -> dict[str, Any]:
    """
    Return public Cognito config for frontend (no secrets).
    Used by /v1/auth/cognito-config and frontend to init Hosted UI / Amplify.
    """
    if not _cognito_enabled():
        return {}
    region = (os.getenv("COGNITO_REGION") or "").strip()
    pool_id = (os.getenv("COGNITO_USER_POOL_ID") or "").strip()
    client_id = (os.getenv("COGNITO_CLIENT_ID") or "").strip()
    domain = (os.getenv("COGNITO_DOMAIN") or "").strip()
    # Optional: custom redirect for callback (e.g. same-origin or SPA URL)
    redirect_uri = (os.getenv("COGNITO_REDIRECT_URI") or "").strip()
    # COGNITO_DOMAIN = Hosted UI base URL (e.g. https://your-prefix.auth.region.amazoncognito.com)
    domain_normalized = domain.rstrip("/") if domain else ""
    if not domain_normalized.startswith("http"):
        domain_normalized = "https://" + domain_normalized if domain_normalized else ""
    logout_path = f"{domain_normalized}/logout?client_id={urllib.parse.quote(client_id)}" if (domain_normalized and client_id) else ""
    return {
        "enabled": True,
        "region": region,
        "userPoolId": pool_id,
        "clientId": client_id,
        "domain": domain,
        "redirectUri": redirect_uri,
        "logoutUrl": logout_path,
    }


def get_cognito_domain() -> str:
    """Return Cognito domain base URL (no trailing slash), or empty if not configured."""
    domain = (os.getenv("COGNITO_DOMAIN") or "").strip().rstrip("/")
    return domain


def get_cognito_authorize_url(redirect_uri: str, state: str | None = None) -> str:
    """
    Build Cognito Hosted UI authorize URL (authorization code flow).
    redirect_uri must match the value configured in the Cognito app client.
    """
    domain = get_cognito_domain()
    client_id = (os.getenv("COGNITO_CLIENT_ID") or "").strip()
    if not domain or not client_id:
        return ""
    params = [
        ("client_id", client_id),
        ("response_type", "code"),
        ("scope", "openid email"),
        ("redirect_uri", redirect_uri),
    ]
    if state:
        params.append(("state", state))
    qs = "&".join(f"{k}={urllib.parse.quote(v)}" for k, v in params)
    return f"{domain}/login?{qs}"


def exchange_code_for_tokens(code: str, redirect_uri: str) -> dict[str, Any] | None:
    """
    Exchange authorization code for tokens via Cognito /oauth2/token.
    Returns token response dict (id_token, access_token, etc.) or None on failure.
    """
    domain = get_cognito_domain()
    client_id = (os.getenv("COGNITO_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("COGNITO_CLIENT_SECRET") or "").strip()
    ctx = ssl._create_unverified_context()
    if not domain or not client_id:
        return None
    url = f"{domain}/oauth2/token"
    body_parts = [
        "grant_type=authorization_code",
        f"code={urllib.parse.quote(code)}",
        f"client_id={urllib.parse.quote(client_id)}",
        f"redirect_uri={urllib.parse.quote(redirect_uri)}",
    ]
    if client_secret:
        body_parts.append(f"client_secret={urllib.parse.quote(client_secret)}")
    body = "&".join(body_parts).encode("utf-8")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:

        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        logger.debug("Token exchange failed: %s", e)
        print(f"error: {e}")
        return None
