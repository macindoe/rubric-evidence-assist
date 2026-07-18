import os

import boto3
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()

# Structured, evidence-heavy marking responses can take longer than boto3's
# 60s default read timeout to generate, especially for longer essays.
BEDROCK_CONFIG = Config(read_timeout=300, connect_timeout=10, retries={"max_attempts": 2, "mode": "standard"})


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable '{name}'. "
            "Copy .env.example to .env and fill in real values."
        )
    return value


def get_bedrock_client():
    return boto3.client(
        "bedrock-runtime",
        region_name=_require_env("AWS_DEFAULT_REGION"),
        config=BEDROCK_CONFIG,
    )


def get_model_id() -> str:
    return _require_env("BEDROCK_MODEL_ID")
