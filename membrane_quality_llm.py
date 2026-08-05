"""membrane_quality_llm.py — dedicated vision-LLM call for qualitative membrane quality.

Deliberately separate from activeLearning_29.py: this call gets ONLY the raw membrane photo and
a fixed rubric -- no synthesis params, no mechanical properties, no active-learning ranges/
bounds. Keeps the quality judgment uncontaminated by performance context.
"""
import base64
import os
import time
from pathlib import Path

from openai import OpenAI
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed — rely on env var being set directly

import system_prompt

_api_key = os.environ.get("OPENROUTER_API_KEY")
if not _api_key:
    raise EnvironmentError("OPENROUTER_API_KEY not set. Add it to .env or set it as an environment variable.")
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=_api_key,
)


def _encode_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def Generate_quality_report(image_path, Model="anthropic/claude-sonnet-4.6", Temperature=0.0, sleep=0.5):
    response = client.chat.completions.create(
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
    time.sleep(sleep)
    return response.choices[0].message.content
