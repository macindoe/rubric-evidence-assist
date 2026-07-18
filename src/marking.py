import json

from .bedrock_client import get_bedrock_client, get_model_id

ASSESSMENT_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "criteria": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterion_code": {"type": "string"},
                    "criterion_name": {"type": "string"},
                    "max_marks": {"type": "integer"},
                    "suggested_band": {"type": "string"},
                    "suggested_marks": {"type": "integer"},
                    "justification": {
                        "type": "string",
                        "description": "1-2 sentences linking the evidence to the specific language of the chosen band's descriptor.",
                    },
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "quote": {
                                    "type": "string",
                                    "description": "A short passage copied verbatim from the essay.",
                                },
                                "comment": {
                                    "type": "string",
                                    "description": "One sentence on why this quote is relevant to the criterion.",
                                },
                            },
                            "required": ["quote", "comment"],
                        },
                    },
                },
                "required": [
                    "criterion_code",
                    "criterion_name",
                    "max_marks",
                    "suggested_band",
                    "suggested_marks",
                    "justification",
                    "evidence",
                ],
            },
        },
        "ai_concern_passages": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "quote": {
                        "type": "string",
                        "description": "A short passage copied verbatim from the essay.",
                    },
                    "concern_level": {
                        "type": "string",
                        "enum": ["Low", "Medium", "High"],
                    },
                    "reason": {
                        "type": "string",
                        "description": "One sentence grounded in a specific contrast with the rest of the essay's writing.",
                    },
                },
                "required": ["quote", "concern_level", "reason"],
            },
        },
        "total_suggested_marks": {"type": "integer"},
    },
    "required": ["criteria", "ai_concern_passages", "total_suggested_marks"],
}

SYSTEM_PROMPT = """You are assisting a NSW HSC Chemistry teacher in marking a Year 12 Depth \
Study against the provided rubric. You do not assign final marks - you surface evidence and a \
suggested band for the teacher's review and judgement. The teacher will accept or edit \
everything you produce.

For each rubric criterion:
- Choose the band whose descriptor best matches the essay, based only on evidence in the text.
- Quote 2-3 short passages from the essay, copied VERBATIM, that support your choice, each with \
a one-sentence comment linking it to the descriptor.
- Write a short justification (1-2 sentences) that references the specific language of the \
chosen band's descriptor.
Never paraphrase a quote - only use text that appears exactly in the essay, so the teacher can \
find and verify it.

Separately, identify up to 3 passages that show signs of AI-generated writing. Base this on \
internal inconsistency within THIS essay - e.g. a passage's vocabulary, sentence rhythm, or \
register (formal/encyclopedic vs conversational, first-person reasoning vs generic exposition) \
differs markedly from the rest of the same student's writing. Do not rely on generic "AI \
detector" heuristics, and do not treat strong citations or technical detail alone as suspicious. \
For each flagged passage, give a concern_level (Low/Medium/High) and a one-sentence reason \
grounded in the specific contrast you observed. These are prompts for the teacher to look \
closer, not accusations - phrase reasons accordingly. If you see fewer than 3 passages worth \
flagging, return fewer.

Respond only by calling the submit_marking_assessment tool. The "criteria" and \
"ai_concern_passages" fields must be native JSON arrays of objects, matching the tool's input \
schema exactly - never a JSON-encoded string.
"""


def build_user_prompt(rubric: dict, essay_text: str) -> str:
    return (
        f"Rubric (JSON):\n{json.dumps(rubric, indent=2)}\n\n"
        "Student essay text follows, delimited by triple backticks.\n\n"
        f"```\n{essay_text}\n```"
    )


def mark_essay(essay_text: str, rubric: dict, _retries: int = 1) -> dict:
    client = get_bedrock_client()
    model_id = get_model_id()

    response = client.converse(
        modelId=model_id,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": build_user_prompt(rubric, essay_text)}]}],
        toolConfig={
            "tools": [
                {
                    "toolSpec": {
                        "name": "submit_marking_assessment",
                        "description": "Submit the structured marking assessment for teacher review.",
                        "inputSchema": {"json": ASSESSMENT_TOOL_SCHEMA},
                    }
                }
            ],
            "toolChoice": {"tool": {"name": "submit_marking_assessment"}},
        },
        # 8192 leaves headroom even if the model over-serializes a field as an escaped
        # string (roughly doubling its size) instead of a native array - see _normalize.
        inferenceConfig={"maxTokens": 8192, "temperature": 0},
    )

    for block in response["output"]["message"]["content"]:
        if "toolUse" in block:
            try:
                return _normalize(block["toolUse"]["input"])
            except json.JSONDecodeError:
                if _retries > 0:
                    return mark_essay(essay_text, rubric, _retries=_retries - 1)
                raise

    raise RuntimeError("Model response did not include the expected tool call.")


def _normalize(result: dict) -> dict:
    """Defensively unwrap fields the model occasionally over-serializes as a JSON string
    instead of a native array, despite the schema and prompt both specifying an array."""
    for key in ("criteria", "ai_concern_passages"):
        value = result.get(key)
        if isinstance(value, str):
            result[key] = json.loads(value)
    return result
