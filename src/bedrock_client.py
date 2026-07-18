import os

import boto3
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()

# Structured, evidence-heavy marking responses can take longer than boto3's
# 60s default read timeout to generate, especially for longer essays.
BEDROCK_CONFIG = Config(read_timeout=300, connect_timeout=10, retries={"max_attempts": 2, "mode": "standard"})


def get_bedrock_client():
    return boto3.client(
        "bedrock-runtime",
        region_name=os.environ["AWS_DEFAULT_REGION"],
        config=BEDROCK_CONFIG,
    )


def get_model_id() -> str:
    return os.environ["BEDROCK_MODEL_ID"]
