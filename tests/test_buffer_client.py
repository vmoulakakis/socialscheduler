import io
import json
import unittest
import urllib.error
from email.message import Message
from unittest.mock import patch

from src.buffer_client import BufferAuthError, BufferClient, BufferRateLimitError


class FakeResponse:
    def __init__(self, body: dict):
        self.payload = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


class BufferClientTests(unittest.TestCase):
    def test_long_retry_after_fails_fast_with_rate_limit_error(self):
        headers = Message()
        headers["Retry-After"] = "52069"
        error = urllib.error.HTTPError(
            "https://api.buffer.com",
            429,
            "Too Many Requests",
            headers,
            io.BytesIO(b"rate limited"),
        )
        client = BufferClient(api_key="test-key", max_retry_after_seconds=30)

        with patch("src.buffer_client.urllib.request.urlopen", side_effect=error):
            with self.assertRaises(BufferRateLimitError) as ctx:
                client.execute("query { account { id } }")

        self.assertEqual(ctx.exception.retry_after_seconds, 52069)

    def test_401_is_classified_and_never_retried(self):
        error = urllib.error.HTTPError(
            "https://api.buffer.com",
            401,
            "Unauthorized",
            Message(),
            io.BytesIO(b'{"errors":[{"message":"Access token is not valid"}]}'),
        )
        client = BufferClient(api_key="bad-key", max_retries=5)

        with patch("src.buffer_client.urllib.request.urlopen", side_effect=error) as urlopen:
            with self.assertRaises(BufferAuthError) as ctx:
                client.execute("query { account { id } }")

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(urlopen.call_count, 1)

    def test_504_read_is_retried_then_succeeds(self):
        error = urllib.error.HTTPError(
            "https://api.buffer.com",
            504,
            "Gateway Timeout",
            Message(),
            io.BytesIO(b"gateway timeout"),
        )
        client = BufferClient(api_key="test-key", max_retries=2)
        success = FakeResponse({"data": {"account": {"id": "acct"}}})

        with patch("src.buffer_client.time.sleep"), patch(
            "src.buffer_client.urllib.request.urlopen", side_effect=[error, success]
        ) as urlopen:
            data = client.execute("query { account { id } }")

        self.assertEqual(data["account"]["id"], "acct")
        self.assertEqual(urlopen.call_count, 2)

    def test_mutation_transient_failure_is_not_retried(self):
        error = urllib.error.HTTPError(
            "https://api.buffer.com",
            504,
            "Gateway Timeout",
            Message(),
            io.BytesIO(b"gateway timeout"),
        )
        client = BufferClient(api_key="test-key", max_retries=5)

        with patch("src.buffer_client.urllib.request.urlopen", side_effect=error) as urlopen:
            with self.assertRaises(Exception):
                client.execute("mutation { x }", retry_transient=False)

        self.assertEqual(urlopen.call_count, 1)

    def test_graphql_unauthenticated_is_classified(self):
        client = BufferClient(api_key="test-key")
        response = FakeResponse(
            {
                "errors": [
                    {
                        "message": "Access token is not valid",
                        "extensions": {"code": "UNAUTHENTICATED"},
                    }
                ]
            }
        )
        with patch("src.buffer_client.urllib.request.urlopen", return_value=response):
            with self.assertRaises(BufferAuthError):
                client.execute("query { account { id } }")


if __name__ == "__main__":
    unittest.main()
