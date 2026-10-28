"""Bounded connection retries for report/recommendation calls, not pipeline stages."""
import time
from openai import APIConnectionError

ATTEMPTS = 5
TIMEOUT_SECONDS = 60
WAIT_SECONDS = 375


def create_chat_completion(client, *, stage, **request):
    # Disable nested SDK retries so each logged attempt is one SDK request.
    caller = client.with_options(max_retries=0, timeout=TIMEOUT_SECONDS)
    destination = str(caller.base_url)
    for attempt in range(1, ATTEMPTS + 1):
        print(f'[llm] destination={destination} stage={stage} attempt={attempt}/{ATTEMPTS} '
              f'timeout={TIMEOUT_SECONDS}s')
        try:
            return caller.chat.completions.create(**request)
        except APIConnectionError as exc:
            # Includes APITimeoutError. Authentication/validation HTTP errors
            # propagate immediately rather than waiting through five attempts.
            print(f'[llm] stage={stage} connection_error={exc.__cause__ or exc}')
            if attempt == ATTEMPTS:
                print('[llm] Retries exhausted. Restore internet/DNS/proxy connectivity '
                      'and resume the same campaign checkpoint. Completed processing is retained.')
                raise
            print(f'[llm] stage={stage} retry_in={WAIT_SECONDS}s')
            time.sleep(WAIT_SECONDS)
