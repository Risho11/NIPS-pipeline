"""membrane_quality_llm.py — dedicated vision-LLM call for qualitative membrane quality.

Deliberately separate from activeLearning_29.py: this call gets ONLY the raw membrane photo and
a fixed rubric -- no synthesis params, no mechanical properties, no active-learning ranges/
bounds. Keeps the quality judgment uncontaminated by performance context.
"""
import base64
import os
import time
from pathlib import Path

from openai import OpenAI, APIConnectionError
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed — rely on env var being set directly

import system_prompt

def _client():
    """Build a client from the current environment so a replaced key is not cached forever."""
    try:
        load_dotenv(override=True)
    except NameError:
        pass
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENROUTER_API_KEY not set. Add it to .env or set it as an environment variable."
        )
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key,
                  max_retries=0, timeout=60.0)


def _encode_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def Generate_quality_report(image_path, Model="anthropic/claude-sonnet-4.6", Temperature=0.0, sleep=0.5):
    request = dict(
        model=Model,
        messages=[
            {"role": "system", "content": system_prompt.QUALITY_CHECKER_PROMPT},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {
                    "url": f"data:image/jpeg;base64,{_encode_image(Path(image_path))}"
                }},
            ]},
        ],
        temperature=Temperature,
    )
    # SDK retries disabled above: at most three calls, with bounded per-call timeout.
    # APIConnectionError includes APITimeoutError; authentication/validation errors propagate.
    with _client() as client:
        for attempt in range(1, 4):
            try:
                response = client.chat.completions.create(**request)
                break
            except APIConnectionError as exc:
                print(f"[quality] destination=https://openrouter.ai/api/v1 stage=quality-report "
                      f"attempt={attempt}/3 error={exc.__cause__ or exc}")
                if attempt == 3:
                    print("[quality] Retries exhausted. Check internet/DNS/proxy; resume the same campaign checkpoint.")
                    raise
                time.sleep(2 ** (attempt - 1))
    time.sleep(sleep)
    return response.choices[0].message.content
