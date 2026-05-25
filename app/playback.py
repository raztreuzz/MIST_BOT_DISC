import asyncio
import random
from typing import Dict, Iterable

from app.music import create_audio_source


class PlaybackManager:
    def __init__(self):
        # per-guild state
        self._state: Dict[int, Dict] = {}

    def set_repeat(self, guild_id: int, value: bool) -> None:
        self.set_repeat_mode(guild_id, "cancion" if value else "off")

    def is_repeat(self, guild_id: int) -> bool:
        return self.get_repeat_mode(guild_id) == "cancion"

    def set_repeat_mode(self, guild_id: int, mode: str) -> None:
        if mode not in ("off", "cancion", "lista"):
            raise ValueError("Modo de repetición inválido.")
        self._state.setdefault(guild_id, {})["repeat_mode"] = mode

    def get_repeat_mode(self, guild_id: int) -> str:
        return self._state.get(guild_id, {}).get("repeat_mode", "off")

    def set_current(self, guild_id: int, url: str) -> None:
        self._state.setdefault(guild_id, {})["current_url"] = url

    def get_current(self, guild_id: int) -> str | None:
        return self._state.get(guild_id, {}).get("current_url")

    def clear_current(self, guild_id: int) -> None:
        if guild_id in self._state:
            self._state[guild_id].pop("current_url", None)
            self._state[guild_id].pop("current_title", None)

    async def play(self, guild_id: int, voice_client, url: str) -> str:
        state = self._state.setdefault(guild_id, {})
        state["generation"] = state.get("generation", 0) + 1
        state["playlist"] = [url]
        state["source_name"] = None
        state["current_index"] = 0
        state["queue"] = []
        state["stopped"] = False
        return await self._start_url(guild_id, voice_client, url, state["generation"], 0)

    async def play_queue(self, guild_id: int, voice_client, urls: Iterable[str], source_name: str | None = None) -> str:
        urls = list(urls)
        if not urls:
            raise ValueError("La lista está vacía.")

        state = self._state.setdefault(guild_id, {})
        state["generation"] = state.get("generation", 0) + 1
        state["playlist"] = urls
        state["source_name"] = source_name
        state["current_index"] = 0
        state["queue"] = urls[1:]
        state["stopped"] = False
        return await self._start_url(guild_id, voice_client, urls[0], state["generation"], 0)

    async def _start_url(self, guild_id: int, voice_client, url: str, generation: int, index: int) -> str:
        """Start one URL and schedule the next queued item from the after callback."""
        loop = asyncio.get_running_loop()
        state = self._state.setdefault(guild_id, {})

        async def _play_once() -> str:
            source, title = await asyncio.to_thread(create_audio_source, url)
            self.set_current(guild_id, url)
            state["current_title"] = title
            state["current_index"] = index

            def _after(err):
                if err:
                    try:
                        print("Playback error:", err)
                    except Exception:
                        pass

                if state.get("stopped"):
                    return

                if state.get("generation") != generation:
                    return

                repeat_mode = self.get_repeat_mode(guild_id)
                if repeat_mode == "cancion":
                    next_url = url
                    next_index = index
                else:
                    queue = state.get("queue") or []
                    if not queue:
                        if repeat_mode == "lista":
                            playlist = state.get("playlist") or []
                            if not playlist:
                                self.clear_current(guild_id)
                                return
                            state["queue"] = playlist[1:]
                            next_url = playlist[0]
                            next_index = 0
                        else:
                            self.clear_current(guild_id)
                            return
                    else:
                        next_url = queue.pop(0)
                        playlist = state.get("playlist") or []
                        try:
                            next_index = playlist.index(next_url)
                        except ValueError:
                            next_index = index + 1

                    if not next_url:
                        self.clear_current(guild_id)
                        return

                try:
                    asyncio.run_coroutine_threadsafe(self._start_url(guild_id, voice_client, next_url, generation, next_index), loop)
                except Exception:
                    pass

            try:
                voice_client.play(source, after=_after)
            except Exception as e:
                print("Error starting playback:", e)
                raise

            return title

        return await _play_once()

    def stop(self, guild_id: int, voice_client) -> None:
        state = self._state.setdefault(guild_id, {})
        state["generation"] = state.get("generation", 0) + 1
        state["stopped"] = True
        state["queue"] = []
        self.clear_current(guild_id)
        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            voice_client.stop()

    def skip(self, guild_id: int, voice_client) -> tuple[bool, int | None, str | None]:
        state = self._state.get(guild_id, {})
        queue = state.get("queue") or []
        next_url = queue[0] if queue else None
        next_number = None
        if next_url:
            playlist = state.get("playlist") or []
            try:
                next_number = playlist.index(next_url) + 1
            except ValueError:
                next_number = (state.get("current_index") or 0) + 2

        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            voice_client.stop()
            return True, next_number, next_url
        return False, next_number, next_url

    def queue_summary(self, guild_id: int, limit: int = 10) -> tuple[str | None, list[str], int]:
        state = self._state.get(guild_id, {})
        current = state.get("current_title") or state.get("current_url")
        queue = list(state.get("queue") or [])
        return current, queue[:limit], max(len(queue) - limit, 0)

    def nowplaying_info(self, guild_id: int) -> dict:
        state = self._state.get(guild_id, {})
        playlist = list(state.get("playlist") or [])
        current_index = state.get("current_index")
        queue = list(state.get("queue") or [])
        return {
            "title": state.get("current_title"),
            "url": state.get("current_url"),
            "position": current_index + 1 if current_index is not None and playlist else None,
            "total": len(playlist) if playlist else None,
            "source_name": state.get("source_name"),
            "repeat_mode": self.get_repeat_mode(guild_id),
            "queued": len(queue),
        }

    def shuffle_queue(self, guild_id: int) -> int:
        state = self._state.get(guild_id, {})
        queue = state.get("queue") or []
        random.shuffle(queue)
        state["queue"] = queue
        return len(queue)


playback_manager = PlaybackManager()
