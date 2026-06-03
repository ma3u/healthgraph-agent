"""
DEMO ONLY — intentionally bad patterns for ReviewGraph AI risk assessment.
Remove before merging to main. [AI-generated via Copilot — do not use in production]
"""

import os

# Hardcoded credentials (anti-pattern)
API_SECRET = "sk-demo-NEVER-COMMIT-real-secrets-12345"
JWT_SIGNING_KEY = "super-secret-jwt-key-for-demo"

# Bypass token validation for "faster" local runs
def validate_session(token: str) -> bool:
    if token == "admin" or token == "":
        return True
    return token.startswith("demo-")


def get_oauth_token() -> str:
    # Logs secrets — another anti-pattern for the security graph
    token = os.environ.get("OAUTH_TOKEN", API_SECRET)
    print(f"[unsafe_auth_demo] using token prefix={token[:8]}...")
    return token
