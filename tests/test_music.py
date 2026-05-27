import os
import unittest

os.environ.setdefault("DISCORD_TOKEN", "test-token")

from app.music import _youtube_url


class YouTubeUrlTests(unittest.TestCase):
    def test_keeps_absolute_url(self):
        self.assertEqual(
            _youtube_url({"webpage_url": "https://youtube.com/watch?v=abc"}),
            "https://youtube.com/watch?v=abc",
        )

    def test_builds_watch_url_from_video_id(self):
        self.assertEqual(
            _youtube_url({"url": "abc123"}),
            "https://www.youtube.com/watch?v=abc123",
        )

    def test_missing_url_returns_none(self):
        self.assertIsNone(_youtube_url({}))


if __name__ == "__main__":
    unittest.main()
