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
}

ffmpeg_options = {
    "options": "-vn"
}


def extract_playlist_urls(url: str):
    if ytdl_module is None:
        raise RuntimeError("yt_dlp or youtube_dl is required (install with `pip install yt-dlp` or `pip install youtube_dl`).")

    playlist_options = dict(ytdl_options)
    playlist_options["noplaylist"] = False
    playlist_options["extract_flat"] = True

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

        entry_url = entry.get("webpage_url") or entry.get("url")
        if not entry_url:
            continue

        if entry_url.startswith("http"):
            urls.append(entry_url)
        else:
            urls.append(f"https://www.youtube.com/watch?v={entry_url}")

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