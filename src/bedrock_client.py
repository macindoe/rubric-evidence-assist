import os

import boto3
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()

# Structured, evidence-heavy marking responses can take longer than boto3's
# 60s default read timeout to generate, especially for longer essays.
BEDROCK_CONFIG = Config(read_timeout=300, connect_timeout=10, retries={"max_attempts": 2, "mode": "standard"})

# The only regions the AU-scoped inference profile is permitted to touch - see
# AGENTS.md "Architecture" and "The Bedrock model saga". Student data must never
# leave Australia, so this is enforced here rather than trusting .env to be correct.
APPROVED_AU_REGIONS = {"ap-southeast-2", "ap-southeast-4"}  # Sydney, Melbourne


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable '{name}'. "
            "Copy .env.example to .env and fill in real values."
        )
    return value


def get_bedrock_client():
    region = _require_env("AWS_DEFAULT_REGION")
    if region not in APPROVED_AU_REGIONS:
        raise RuntimeError(
            f"AWS_DEFAULT_REGION='{region}' is not an approved Australian region "
            f"({', '.join(sorted(APPROVED_AU_REGIONS))}). Student data must stay in-country - "
            "see AGENTS.md Compliance posture. Refusing to create a Bedrock client."
        )
    return boto3.client(
        "bedrock-runtime",
        region_name=region,
        config=BEDROCK_CONFIG,
    )


def get_model_id() -> str:
    return _require_env("BEDROCK_MODEL_ID")
