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

def Generate_report(Formatted_Parameters, Model = "anthropic/claude-sonnet-4.6", Temperature = 0.0, sleep = 0.5):
    response = client.chat.completions.create(
      model= Model,
      messages=[{"role": "system", "content": 
                 f'Here I have a set of experimental parameters for my automated membrane synthesis via non-solvent-induced phase seperation (NIPS) using my robotic system. '
                 f'"weight_percent" means the polymer (polysulfone) concentration in the solution (solvent is PolarClean). '
                 f'"mixing_temp" means the temperature in Celsius at which the polymer solution is mixed and heated. '
                 f'"pullcast_speed" means the speed in mm/s at which the blade moves when casting the polymer solution. '
                 f'"coupon_to_bath_wait_time" means how long the sample is waited in seconds after blade casting before immersion in the NIPS bath. If nitrogen is True, the sample is being blown with dry nitrogen for the time period. If nitrogen is False, the sample is just sitting in ambient conditions for the time period. '
                 f'"nitrogen" means whether the polymer solution undergoes a laminar dry nitrgen blow to remove humidity after it is blade-cast until it is immersed into the NIPS bath. '
                 f'"nips_bath_wait_time" means how long the sample is waited in seconds in the NIPS bath after immersion. '
                 f'"bath_temp" means the temperature in Celsius of the NIPS bath. '
                 f'Can you translate that into a short experimental report? '},
                {"role": "user", "content": Formatted_Parameters}
                ],
      temperature=Temperature
    )
    time.sleep(sleep)
    return response.choices[0].message.content

ranges = 'The "mixing_temp" can be between 25 and 80 degrees Celsius. The "bath_temp" can be between 5 and 25 degrees Celsius. The "weight_percent" can be between 10 and 17 percent. The "pullcast_speed" can be between 1 and 20 mm/s. The "coupon_to_bath_wait_time" can be between 0 and 600 seconds. The "nips_bath_wait_time" can be between 1200 and 1800seconds. The "nitrogen" can be either True or False.'

#-----------#
def _encode_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")
#-----------#


def LLM_AL(observations_str, ranges, image_paths=None, Model="anthropic/claude-sonnet-4.6", Temperature=0.0, sleep=0.5):
    user_content = [{"type": "text", "text": f'\nPrior Observations: {observations_str}'}]
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
                f"Here I have a set of structured experimental parameters for my automated membrane synthesis via non-solvent-induced phase separation (NIPS). "
                f"My goal is to iteratively find the best experiment to maximize modulus. "
                f"Based on the following previous experimental observations, recommend the next experiment that minimizes strain at 50 bar, taking the coefficient of variation (CV) into account when it is appropriate. "
                f"Suggest the next set of experimental parameters that is expected to maximize modulus given the parameter ranges: {ranges}. "
            
            },
            
            {"role": "user", "content": user_content}
        ],
        temperature=Temperature
    )
    time.sleep(sleep)
    return response.choices[0].message.content