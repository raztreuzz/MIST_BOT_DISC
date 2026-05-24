import asyncio
from typing import Dict

from app.music import create_audio_source


class PlaybackManager:
    def __init__(self):
        # per-guild state
        self._state: Dict[int, Dict] = {}

    def set_repeat(self, guild_id: int, value: bool) -> None:
        self._state.setdefault(guild_id, {})["repeat"] = bool(value)

    def is_repeat(self, guild_id: int) -> bool:
        return bool(self._state.get(guild_id, {}).get("repeat", False))

    def set_current(self, guild_id: int, url: str) -> None:
        self._state.setdefault(guild_id, {})["current_url"] = url

    def get_current(self, guild_id: int) -> str | None:
        return self._state.get(guild_id, {}).get("current_url")

    def clear_current(self, guild_id: int) -> None:
        if guild_id in self._state:
            self._state[guild_id].pop("current_url", None)

    def play(self, guild_id: int, voice_client, url: str):
        """Schedule playback of `url` on given voice_client. Handles repeat using after callback."""

        async def _play_once():
            source, title = create_audio_source(url)

            def _after(err):
                if err:
                    # log and stop
                    try:
                        print("Playback error:", err)
                    except Exception:
                        pass
                # if repeat is enabled, schedule replay
                if self.is_repeat(guild_id):
                    try:
                        # schedule next play
                        asyncio.create_task(_play_once())
                    except Exception:
                        pass

            # play the source (this runs in event loop)
            try:
                voice_client.play(source, after=_after)
            except Exception as e:
                print("Error starting playback:", e)

        # save current url
        self.set_current(guild_id, url)
        # schedule first play
        asyncio.create_task(_play_once())


playback_manager = PlaybackManager()
