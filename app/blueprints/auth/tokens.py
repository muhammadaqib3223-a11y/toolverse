"""Checking Supabase access tokens (JWTs) on our own server.

Supabase signs tokens with a private key and publishes the matching public keys (JWKS).
We download those public keys once, keep them in memory, and check every token locally,
so a normal page view does not need a network call to Supabase.

Older projects sign with a shared secret (HS256) that we do not have. Those tokens are
checked by asking Supabase instead (one network call per request); switch the project to
"JWT Signing Keys" in Supabase to make it fast.
"""
import logging
import threading

import jwt

logger = logging.getLogger(__name__)

ASYMMETRIC_ALGORITHMS = ["ES256", "RS256", "EdDSA"]
AUDIENCE = "authenticated"
JWKS_CACHE_SECONDS = 600
LEEWAY_SECONDS = 10  # small clock differences between servers

_jwks_clients = {}
_jwks_lock = threading.Lock()


class LegacySecretToken(Exception):
    """The token is signed with the old shared secret and must be checked by Supabase."""


def read_claims(access_token, supabase_url, api_key, timeout):
    """Return the verified claims of `access_token`.

    Raises jwt.ExpiredSignatureError, jwt.InvalidTokenError, jwt.PyJWKClientConnectionError
    or LegacySecretToken.
    """
    header = jwt.get_unverified_header(access_token)
    if header.get("alg") == "HS256":
        raise LegacySecretToken()
    if header.get("alg") not in ASYMMETRIC_ALGORITHMS:
        raise jwt.InvalidAlgorithmError(f"Unexpected token algorithm {header.get('alg')!r}")

    signing_key = _jwks_client(supabase_url, api_key, timeout).get_signing_key_from_jwt(access_token)
    return jwt.decode(
        access_token,
        signing_key.key,
        algorithms=ASYMMETRIC_ALGORITHMS,
        audience=AUDIENCE,
        issuer=f"{supabase_url}/auth/v1",
        leeway=LEEWAY_SECONDS,
        options={"require": ["exp", "sub", "aud", "iss"]},
    )


def _jwks_client(supabase_url, api_key, timeout):
    # One client per Supabase project, kept for the life of the server process.
    client = _jwks_clients.get(supabase_url)
    if client is None:
        with _jwks_lock:
            client = _jwks_clients.get(supabase_url)
            if client is None:
                client = jwt.PyJWKClient(
                    f"{supabase_url}/auth/v1/.well-known/jwks.json",
                    cache_jwk_set=True,
                    lifespan=JWKS_CACHE_SECONDS,
                    headers={"apikey": api_key},
                    timeout=timeout,
                )
                _jwks_clients[supabase_url] = client
    return client
