import os
import tempfile
import unittest
from importlib import import_module
from pathlib import Path

os.environ.setdefault("DISCORD_TOKEN", "test-token")


class StorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(cls.temp_dir.name) / "mist-test.sqlite3"
        database_url = f"sqlite:///{db_path}"

        config = import_module("app.config")
        config.DATABASE_URL = database_url
        cls.storage = import_module("app.lists.storage")

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_create_add_get_and_delete_list(self):
        storage = self.storage
        guild_id = 1001

        self.assertTrue(storage.create_list(guild_id, "zen", "musica", creator_id=42))
        self.assertFalse(storage.create_list(guild_id, "zen", "musica", creator_id=42))

        self.assertTrue(storage.add_to_list(guild_id, "zen", "https://youtube.com/watch?v=one"))
        self.assertTrue(storage.add_to_list(guild_id, "zen", "https://youtube.com/watch?v=two"))

        saved = storage.get_list(guild_id, "zen")
        self.assertEqual(saved.name, "zen")
        self.assertEqual(
            saved.items,
            ["https://youtube.com/watch?v=one", "https://youtube.com/watch?v=two"],
        )

        self.assertEqual(storage.delete_list(guild_id, "zen"), 2)
        self.assertIsNone(storage.get_list(guild_id, "zen"))

    def test_user_and_ai_log_stats(self):
        storage = self.storage
        guild_id = 1377499113808986266
        user_id = 942904057205514290
        channel_id = 1377499113808986267

        storage.ensure_user(guild_id, user_id, "Sara", '{"names":["Miembro"]}')
        user = storage.get_user(guild_id, user_id)
        self.assertEqual(user["display_name"], "Sara")

        storage.record_ai_interaction(
            guild_id,
            channel_id=channel_id,
            user_id=user_id,
            display_name="Sara",
            model="tinyllama",
            prompt="hola",
            response="hola",
        )

        logs = storage.recent_ai_interactions(guild_id, 5)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].prompt, "hola")

        stats = storage.storage_stats(guild_id)
        self.assertEqual(stats.users, 1)
        self.assertEqual(stats.ai_logs, 1)


if __name__ == "__main__":
    unittest.main()
