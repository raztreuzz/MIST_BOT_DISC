import os
import unittest

os.environ.setdefault("DISCORD_TOKEN", "test-token")

from app.music import _youtube_url, is_youtube_playlist_url, is_youtube_url


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

    def test_youtube_url_validation(self):
        self.assertTrue(is_youtube_url("https://www.youtube.com/watch?v=abc"))
        self.assertTrue(is_youtube_url("https://youtu.be/abc"))
        self.assertFalse(is_youtube_url("olmo"))
        self.assertFalse(is_youtube_url("https://example.com/watch?v=abc"))

    def test_playlist_url_detection(self):
        self.assertTrue(is_youtube_playlist_url("https://www.youtube.com/playlist?list=PL123"))
        self.assertFalse(is_youtube_playlist_url("https://www.youtube.com/watch?v=abc&list=PL123"))


if __name__ == "__main__":
    unittest.main()
