import discord

# Try to import yt_dlp, fall back to youtube_dl if necessary
try:
    import yt_dlp as ytdl_module
except Exception:
    try:
        import youtube_dl as ytdl_module
    except Exception:
        ytdl_module = None

ytdl_options = {
    "format": "bestaudio/best",
    "quiet": True,
    "noplaylist": True,
    "socket_timeout": 15,
    "retries": 2,
    "extractor_retries": 2,
}

ffmpeg_options = {
    "options": "-vn"
}


def _youtube_url(entry: dict) -> str | None:
    entry_url = entry.get("webpage_url") or entry.get("url")
    if not entry_url:
        return None
    if entry_url.startswith("http"):
        return entry_url
    return f"https://www.youtube.com/watch?v={entry_url}"


def search_youtube(query: str, limit: int = 5) -> list[dict]:
    if ytdl_module is None:
        raise RuntimeError("yt_dlp or youtube_dl is required (install with `pip install yt-dlp` or `pip install youtube_dl`).")

    search_options = dict(ytdl_options)
    search_options["noplaylist"] = False
    search_options["extract_flat"] = True

    ytdl = ytdl_module.YoutubeDL(search_options)
    info = ytdl.extract_info(f"ytsearch{limit}:{query}", download=False)

    entries = info.get("entries") if isinstance(info, dict) else None
    if not entries:
        return []

    results = []
    for entry in entries[:limit]:
        if not isinstance(entry, dict):
            continue

        url = _youtube_url(entry)
        if not url:
            continue

        results.append(
            {
                "title": entry.get("title") or "Sin título",
                "url": url,
            }
        )

    return results


def extract_playlist_urls(url: str):
    if ytdl_module is None:
        raise RuntimeError("yt_dlp or youtube_dl is required (install with `pip install yt-dlp` or `pip install youtube_dl`).")

    playlist_options = dict(ytdl_options)
    playlist_options["noplaylist"] = False
    playlist_options["extract_flat"] = True
    playlist_options["ignoreerrors"] = True

    ytdl = ytdl_module.YoutubeDL(playlist_options)
    info = ytdl.extract_info(url, download=False)

    entries = info.get("entries") if isinstance(info, dict) else None
    if not entries:
        title = info.get("title", "Unknown playlist") if isinstance(info, dict) else "Unknown playlist"
        return [url], title

    urls = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue

        entry_url = _youtube_url(entry)
        if not entry_url:
            continue

        urls.append(entry_url)

    title = info.get("title", "Unknown playlist") if isinstance(info, dict) else "Unknown playlist"
    return urls, title


def create_audio_source(url: str):
    if ytdl_module is None:
        raise RuntimeError("yt_dlp or youtube_dl is required (install with `pip install yt-dlp` or `pip install youtube_dl`).")

    ytdl = ytdl_module.YoutubeDL(ytdl_options)
    info = ytdl.extract_info(url, download=False)
    audio_url = info["url"]
    title = info.get("title", "Unknown title")

    source = discord.FFmpegPCMAudio(audio_url, **ffmpeg_options)

    return source, title
