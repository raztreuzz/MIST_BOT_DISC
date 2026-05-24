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


def create_audio_source(url: str):
    if ytdl_module is None:
        raise RuntimeError("yt_dlp or youtube_dl is required (install with `pip install yt-dlp` or `pip install youtube_dl`).")

    ytdl = ytdl_module.YoutubeDL(ytdl_options)
    info = ytdl.extract_info(url, download=False)
    audio_url = info["url"]
    title = info.get("title", "Unknown title")

    source = discord.FFmpegPCMAudio(audio_url, **ffmpeg_options)

    return source, title