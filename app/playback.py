import asyncio
import random
from typing import Dict, Iterable

from app.config import MIST_VOICE_ENABLED
from app.music import create_audio_source
from app.voice import cleanup_tts_file, create_tts_source, mist_voice_line


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

    def set_voice_enabled(self, guild_id: int, enabled: bool) -> None:
        self._state.setdefault(guild_id, {})["voice_enabled"] = enabled

    def is_voice_enabled(self, guild_id: int) -> bool:
        return self._state.get(guild_id, {}).get("voice_enabled", MIST_VOICE_ENABLED)

    async def speak(self, guild_id: int, voice_client, event: str, fallback: str, details: dict | None = None) -> None:
        if not voice_client or not self.is_voice_enabled(guild_id):
            return
        if voice_client.is_playing() or voice_client.is_paused():
            return

        text = await mist_voice_line(event, fallback, details)
        tts = await create_tts_source(text)
        if tts is None:
            return

        loop = asyncio.get_running_loop()
        source, output_path = tts
        done = loop.create_future()

        def _after_tts(_err):
            cleanup_tts_file(output_path)
            loop.call_soon_threadsafe(done.set_result, None)

        voice_client.play(source, after=_after_tts)
        await done

    def set_current(self, guild_id: int, url: str) -> None:
        self._state.setdefault(guild_id, {})["current_url"] = url

    def get_current(self, guild_id: int) -> str | None:
        return self._state.get(guild_id, {}).get("current_url")

    def get_current_title(self, guild_id: int) -> str | None:
        return self._state.get(guild_id, {}).get("current_title")

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

        async def _speak(event: str, fallback: str, details: dict | None = None) -> None:
            await self.speak(guild_id, voice_client, event, fallback, details)

        async def _speak_then_start(
            event: str,
            fallback: str,
            details: dict | None,
            next_url: str,
            next_generation: int,
            next_index: int,
        ) -> None:
            try:
                await _speak(event, fallback, details)
            except Exception:
                pass
            if state.get("stopped") or state.get("generation") != next_generation:
                return
            await self._start_url(guild_id, voice_client, next_url, next_generation, next_index)

        async def _speak_then_clear(event: str, fallback: str, details: dict | None, next_generation: int) -> None:
            try:
                await _speak(event, fallback, details)
            except Exception:
                pass
            if state.get("generation") == next_generation:
                self.clear_current(guild_id)

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
                    voice_event = "repeat_song"
                    voice_fallback = "Repitiendo la canción."
                    voice_details = {"posicion": index + 1}
                else:
                    queue = state.get("queue") or []
                    if not queue:
                        state.pop("skip_requested", None)
                        if repeat_mode == "lista":
                            playlist = state.get("playlist") or []
                            if not playlist:
                                self.clear_current(guild_id)
                                return
                            state["queue"] = playlist[1:]
                            next_url = playlist[0]
                            next_index = 0
                            voice_event = "repeat_list"
                            voice_fallback = "La lista vuelve a empezar."
                            voice_details = {"total": len(playlist)}
                        else:
                            try:
                                asyncio.run_coroutine_threadsafe(
                                    _speak_then_clear(
                                        "list_finished",
                                        "La lista terminó. Guardé silencio por ahora.",
                                        {"titulo": state.get("current_title")},
                                        generation,
                                    ),
                                    loop,
                                )
                            except Exception:
                                self.clear_current(guild_id)
                            return
                    else:
                        next_url = queue.pop(0)
                        playlist = state.get("playlist") or []
                        try:
                            next_index = playlist.index(next_url)
                        except ValueError:
                            next_index = index + 1
                        if state.pop("skip_requested", False):
                            voice_event = "skip"
                            voice_fallback = "Saltando canción. Vamos con la siguiente."
                        else:
                            voice_event = "next_song"
                            voice_fallback = "Se terminó la canción. Vamos con la siguiente."
                        voice_details = {
                            "cancion_anterior": state.get("current_title"),
                            "siguiente_posicion": next_index + 1,
                        }

                    if not next_url:
                        self.clear_current(guild_id)
                        return

                try:
                    asyncio.run_coroutine_threadsafe(
                        _speak_then_start(voice_event, voice_fallback, voice_details, next_url, generation, next_index),
                        loop,
                    )
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
            state["skip_requested"] = True
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

    def set_search_results(self, guild_id: int, results: list[dict]) -> None:
        self._state.setdefault(guild_id, {})["search_results"] = results

    def get_search_results(self, guild_id: int) -> list[dict]:
        return list(self._state.get(guild_id, {}).get("search_results") or [])

    def get_search_result(self, guild_id: int, number: int) -> dict | None:
        results = self.get_search_results(guild_id)
        if number < 1 or number > len(results):
            return None
        return results[number - 1]


playback_manager = PlaybackManager()
