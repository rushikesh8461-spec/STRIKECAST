"""Make each owned module importable for a repository-root test run."""
import os
os.environ.update({
    "STRIKECAST_MODE": "DEMO",
    "CORS_ORIGINS": "http://localhost:3000,http://localhost:5173",
    "LIGHTNING_MODE": "demo",
    "RISK_POLICY_VERSION": "provisional-1",
    "RISK_MODERATE_THRESHOLD": "0.35",
    "RISK_HIGH_THRESHOLD": "0.60",
    "RISK_SEVERE_THRESHOLD": "0.80",
})
