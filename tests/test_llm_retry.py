"""No API requests or real sleeps: connection retry regression tests."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

import httpx
from openai import APIConnectionError, APITimeoutError, AuthenticationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/pipeline'))
import llm_retry


class RetryTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.caller = self.client.with_options.return_value
        self.caller.base_url = 'https://openrouter.ai/api/v1/'
        self.create = self.caller.chat.completions.create
        self.request = httpx.Request('POST', 'https://openrouter.ai/api/v1/chat/completions')
        self.payload = dict(model='test-model', messages=[{'role': 'user', 'content': 'context'}], temperature=0)

    def invoke(self):
        return llm_retry.create_chat_completion(self.client, stage='test', **self.payload)

    def test_transient_failure_retries_identical_request_then_returns(self):
        result = object()
        self.create.side_effect = [APIConnectionError(request=self.request), result]
        with patch.object(llm_retry.time, 'sleep') as sleep:
            self.assertIs(self.invoke(), result)
        self.client.with_options.assert_called_once_with(max_retries=0, timeout=60)
        self.assertEqual(self.create.call_count, 2)
        self.assertTrue(all(c.kwargs == self.payload for c in self.create.call_args_list))
        sleep.assert_called_once_with(375)

    def test_connection_and_timeout_exhaustion_have_five_attempts_four_waits(self):
        for error in (APIConnectionError(request=self.request), APITimeoutError(request=self.request)):
            with self.subTest(error=type(error).__name__):
                self.create.reset_mock()
                self.create.side_effect = error
                with patch.object(llm_retry.time, 'sleep') as sleep:
                    with self.assertRaises(APIConnectionError) as raised:
                        self.invoke()
                self.assertIs(raised.exception, error)
                self.assertEqual(self.create.call_count, 5)
                self.assertEqual([c.args[0] for c in sleep.call_args_list], [375] * 4)

    def test_authentication_error_is_not_retried(self):
        self.create.side_effect = AuthenticationError('bad key', response=httpx.Response(401, request=self.request), body=None)
        with patch.object(llm_retry.time, 'sleep') as sleep:
            with self.assertRaises(AuthenticationError):
                self.invoke()
        self.assertEqual(self.create.call_count, 1)
        sleep.assert_not_called()

    def test_success_does_not_wait(self):
        with patch.object(llm_retry.time, 'sleep') as sleep:
            self.assertIs(self.invoke(), self.create.return_value)
        self.create.assert_called_once_with(**self.payload)
        sleep.assert_not_called()


if __name__ == '__main__':
    unittest.main()
