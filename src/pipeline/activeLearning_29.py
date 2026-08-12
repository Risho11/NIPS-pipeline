import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
import random
import logging
import time
import yaml
import seaborn as sns
import json
import glob
import re

import base64
from pathlib import Path

import polymer_additive_bounds as bounds
import system_prompt

# ignore warnings
import warnings
warnings.filterwarnings("ignore")


from openai import OpenAI
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed — rely on env var being set directly

_api_key = os.environ.get("OPENROUTER_API_KEY")
if not _api_key:
    raise EnvironmentError("OPENROUTER_API_KEY not set. Add it to .env or set it as an environment variable.")
client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=_api_key,
)


params = {
    "mixing_temp": "the temperature in Celsius at which the polymer solution is mixed and heated",
    "pullcast_speed": "the speed in mm/s at which the blade moves when casting the polymer solution",
    "coupon_to_bath_wait_time": "how long the sample is waited in seconds after blade casting before immersion in the NIPS bath. If nitrogen is True, the sample is being blown with dry nitrogen for the time period. If nitrogen is False, the sample is just sitting in ambient conditions for the time period",
    "nitrogen": "whether the polymer solution undergoes a laminar dry nitrogen blow to remove humidity after it is blade-cast until it is immersed into the NIPS bath",
    "nips_bath_wait_time": "how long the sample is waited in seconds in the NIPS bath after immersion",
    "bath_temp": "the temperature in Celsius of the NIPS bath",
    "polymer_wt": "the polymer (polysulfone) concentration in the final solution (solvent is PolarClean)",
    "additive_wt": "the additive (PVP) concentration in the final solution",
}

def Generate_report(Formatted_Parameters, Model = "anthropic/claude-sonnet-4.6", Temperature = 0.0, sleep = 0.5):
    param_descriptions = " ".join(f'"{k}" means {v}.' for k, v in params.items())
    response = client.chat.completions.create(
      model= Model,
      messages=[{"role": "system", "content":
                 system_prompt.EXPERIMENTAL_REPORT_PROMPT.format(param_descriptions=param_descriptions)},
                {"role": "user", "content": Formatted_Parameters}
                ],
      temperature=Temperature
    )
    time.sleep(sleep)
    return response.choices[0].message.content

_BASE_RANGES = 'The "mixing_temp" can be between 25 and 80 degrees Celsius. The "bath_temp" can be between 5 and 25 degrees Celsius. The "pullcast_speed" can be between 1 and 20 mm/s. The "coupon_to_bath_wait_time" can be between 0 and 600 seconds. The "nips_bath_wait_time" can be between 1200 and 1800seconds. The "nitrogen" can be either True or False.'


def build_ranges(locked_additive_wt=None):
    """Compose the parameter-ranges text fed to the LLM's system prompt.

    Pass locked_additive_wt (e.g. run_loop.LOCK_ADDITIVE_WT_VALUE) when a campaign phase is
    forcing additive_wt to a fixed value downstream -- otherwise this describes the full
    triangle (up to additive_wt_max), the LLM keeps proposing nonzero additive_wt within that
    range, and run_loop.py silently overrides every suggestion back to the locked value. The
    model never sees why its suggestions get discarded, which derails active learning.
    """
    triangle = bounds.get_composition_bounds()
    if locked_additive_wt is None:
        tri_ranges = (
            f' The "polymer_wt" maximum is {triangle["polymer_wt_max"]} and the "additive_wt" '
            f'maximum is {triangle["additive_wt_max"]}. The "polymer_wt" and "additive_wt" '
            f'should be within the triangular bounds {triangle["vertices"]}.'
        )
    else:
        tri_ranges = (
            f' The "additive_wt" is locked at {locked_additive_wt} for this campaign phase -- '
            f'always suggest exactly {locked_additive_wt} for "additive_wt", regardless of '
            f'prior observations. The "polymer_wt" maximum is {triangle["polymer_wt_max"]}.'
        )
    return _BASE_RANGES + tri_ranges


ranges = build_ranges()
print(ranges)
### we want the triangle range, but it would be generated from the tester function i believe...
#-----------#
def _encode_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")
#-----------#


def LLM_AL(performance_observations, ranges, quality_observations=None, image_paths=None,
           Model="anthropic/claude-sonnet-4.6", Temperature=0.0, sleep=0.5):
    text = f'\nPrior Performance Observations: {performance_observations}'
    if quality_observations:
        text += f'\n\nPrior Quality Observations: {quality_observations}'
    user_content = [{"type": "text", "text": text}]
    if image_paths:
        for p in image_paths:
            p = Path(p)
            if p.exists():
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{_encode_image(p)}"},
                })

    response = client.chat.completions.create(
        model=Model,
        messages=[
            {"role": "system", "content":
                system_prompt.ACTIVE_LEARNING_PROMPT_TEMPLATE.format(ranges=ranges)},
            {"role": "user", "content": user_content}
        ],
        temperature=Temperature
    )
    time.sleep(sleep)
    return response.choices[0].message.content