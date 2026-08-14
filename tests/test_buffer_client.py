import io
import unittest
import urllib.error
from email.message import Message
from unittest.mock import patch

from src.buffer_client import BufferClient, BufferRateLimitError


class BufferClientRateLimitTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
