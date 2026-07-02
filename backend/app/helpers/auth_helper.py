import jwt
import requests
from typing import Optional, Any
import os
from functools import lru_cache

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "https://www.michaeldumontdev.com/auth")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "Contract AI")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "contract-ai-web")

# URL for public keys
JWKS_URL = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"

@lru_cache(maxsize=1)
def get_jwks():
    try:
        response = requests.get(JWKS_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching JWKS: {e}")
        return None

def validate_token(token: str) -> Optional[dict[str, Any]]:
    if not token:
        return None
    
    if token.startswith("Bearer "):
        token = token[7:]
        
    jwks = get_jwks()
    if not jwks:
        return None
        
    try:
        # Get the kid from the token header
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        
        # Find the correct key in JWKS
        key = next((k for k in jwks["keys"] if k["kid"] == kid), None)
        if not key:
            print("KID not found in JWKS")
            return None
            
        # Construct the public key
        from jwt.algorithms import RSAAlgorithm
        public_key = RSAAlgorithm.from_jwk(key)
        
        # Decode and validate
        # Note: audience validation depends on Keycloak config. 
        # Often it's 'account' or the clientId.
        # We'll allow common audiences or skip audience check if needed.
        decoded = jwt.decode(
            token, 
            public_key, 
            algorithms=["RS256"],
            audience=KEYCLOAK_CLIENT_ID,
            options={"verify_aud": False} # Set to True if audience is strictly enforced
        )
        return decoded
    except Exception as e:
        print(f"Token validation error: {e}")
        return None
