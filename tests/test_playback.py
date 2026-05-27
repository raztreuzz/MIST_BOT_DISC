import os
import unittest

os.environ.setdefault("DISCORD_TOKEN", "test-token")

from app.playback import PlaybackManager


class FakeVoiceClient:
    def __init__(self, playing=False, paused=False):
        self._playing = playing
        self._paused = paused
        self.stopped = False

    def is_playing(self):
        return self._playing

    def is_paused(self):
        return self._paused

    def stop(self):
        self.stopped = True
        self._playing = False
        self._paused = False


class PlaybackManagerTests(unittest.TestCase):
    def test_repeat_mode_validation_and_defaults(self):
        manager = PlaybackManager()

        self.assertEqual(manager.get_repeat_mode(1), "off")
        manager.set_repeat_mode(1, "cancion")
        self.assertTrue(manager.is_repeat(1))
        manager.set_repeat(1, False)
        self.assertEqual(manager.get_repeat_mode(1), "off")

        with self.assertRaises(ValueError):
            manager.set_repeat_mode(1, "todo")

    def test_search_results_are_numbered_from_one(self):
        manager = PlaybackManager()
        results = [{"title": "Uno"}, {"title": "Dos"}]
        manager.set_search_results(1, results)

        self.assertEqual(manager.get_search_result(1, 1), {"title": "Uno"})
        self.assertEqual(manager.get_search_result(1, 2), {"title": "Dos"})
        self.assertIsNone(manager.get_search_result(1, 0))
        self.assertIsNone(manager.get_search_result(1, 3))

    def test_skip_marks_next_song_and_stops_voice(self):
        manager = PlaybackManager()
        state = manager._state.setdefault(1, {})
        state["playlist"] = ["a", "b", "c"]
        state["queue"] = ["b", "c"]
        state["current_index"] = 0
        voice = FakeVoiceClient(playing=True)

        skipped, next_number, next_url = manager.skip(1, voice)

        self.assertTrue(skipped)
        self.assertEqual(next_number, 2)
        self.assertEqual(next_url, "b")
        self.assertTrue(state["skip_requested"])
        self.assertTrue(voice.stopped)

    def test_stop_clears_current_and_queue(self):
        manager = PlaybackManager()
        state = manager._state.setdefault(1, {})
        state["queue"] = ["next"]
        manager.set_current(1, "current")
        voice = FakeVoiceClient(playing=True)

        manager.stop(1, voice)

        self.assertIsNone(manager.get_current(1))
        self.assertEqual(state["queue"], [])
        self.assertTrue(state["stopped"])
        self.assertTrue(voice.stopped)


if __name__ == "__main__":
    unittest.main()
