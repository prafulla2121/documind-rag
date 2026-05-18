"""
YouTube transcript parser for ingestion.

Extracts a YouTube video ID, fetches transcript captions, enriches them with
video metadata, and groups short caption snippets into natural passage windows.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse


YOUTUBE_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.|m\.|music\.)?(?:youtube\.com/(?:watch\?v=|shorts/|live/|embed/|v/)|youtu\.be/)([\w-]{11})",
    re.IGNORECASE,
)


class InvalidYouTubeURLError(ValueError):
    """Raised when a URL is not a supported YouTube video URL."""


class TranscriptNotAvailableError(RuntimeError):
    """Raised when no transcript can be fetched for a YouTube video."""


class YouTubeMetadataError(RuntimeError):
    """Raised when video metadata cannot be fetched."""


@dataclass(frozen=True)
class YouTubeMetadata:
    video_id: str
    title: str
    channel_name: str
    duration_seconds: int
    thumbnail_url: str
    published_date: str


def extract_video_id(url: str) -> str:
    """Return the YouTube video ID from supported URL formats."""
    raw_url = url.strip()
    match = YOUTUBE_URL_RE.search(raw_url)
    if match:
        return match.group(1)

    parsed = urlparse(raw_url if "://" in raw_url else f"https://{raw_url}")
    host = parsed.netloc.lower().replace("www.", "")
    if host in {"youtube.com", "m.youtube.com", "music.youtube.com"}:
        video_id = parse_qs(parsed.query).get("v", [""])[0]
        if re.fullmatch(r"[\w-]{11}", video_id):
            return video_id

    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
        if re.fullmatch(r"[\w-]{11}", video_id):
            return video_id

    if not match:
        raise InvalidYouTubeURLError(
            "Invalid YouTube URL. Use youtube.com/watch?v=ID, youtube.com/shorts/ID, youtube.com/live/ID, or youtu.be/ID."
        )


def is_youtube_url(url: str) -> bool:
    """Return True when the URL looks like a supported YouTube video URL."""
    try:
        extract_video_id(url)
        return True
    except InvalidYouTubeURLError:
        return False


def canonical_youtube_url(video_id: str) -> str:
    """Return a clean single-video URL without playlist or tracking params."""
    return f"https://www.youtube.com/watch?v={video_id}"


class YouTubeParser:
    """Fetch and normalize YouTube transcript data for RAG ingestion."""

    WINDOW_SECONDS = 60.0

    def parse(self, url: str, user_id: str | None = None) -> list[dict[str, Any]]:
        """Fetch metadata and transcript passages for a YouTube URL."""
        video_id = extract_video_id(url)
        metadata = self.fetch_metadata(canonical_youtube_url(video_id), video_id)
        transcript = self.fetch_transcript(video_id)
        return self._group_transcript(transcript, metadata)

    def fetch_transcript(self, video_id: str) -> list[dict[str, Any]]:
        """Fetch manual captions first, then fall back to generated captions."""
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            from youtube_transcript_api._errors import (
                AgeRestricted,
                NoTranscriptFound,
                TranscriptsDisabled,
                VideoUnavailable,
            )
        except ImportError as exc:
            raise TranscriptNotAvailableError(
                "youtube-transcript-api is not installed. Run: pip install youtube-transcript-api"
            ) from exc

        try:
            api = YouTubeTranscriptApi()
            if hasattr(api, "list"):
                transcript_list = api.list(video_id)
            else:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcripts = list(transcript_list)
            manual = [item for item in transcripts if not getattr(item, "is_generated", False)]
            generated = [item for item in transcripts if getattr(item, "is_generated", False)]
            selected = (manual or generated)[0]
            fetched = selected.fetch()
            return [self._snippet_to_dict(item) for item in fetched]
        except (NoTranscriptFound, TranscriptsDisabled) as exc:
            raise TranscriptNotAvailableError(
                "No transcript captions are available for this video."
            ) from exc
        except AgeRestricted as exc:
            raise TranscriptNotAvailableError(
                "This video is age-restricted, so its transcript cannot be fetched."
            ) from exc
        except VideoUnavailable as exc:
            raise TranscriptNotAvailableError(
                "This video is private, unavailable, or cannot be accessed."
            ) from exc
        except IndexError as exc:
            raise TranscriptNotAvailableError(
                "No transcript captions are available for this video."
            ) from exc

    def fetch_metadata(self, url: str, video_id: str) -> YouTubeMetadata:
        """Fetch public video metadata with yt-dlp."""
        try:
            from yt_dlp import YoutubeDL
            from yt_dlp.utils import DownloadError
        except ImportError as exc:
            raise YouTubeMetadataError("yt-dlp is not installed. Run: pip install yt-dlp") from exc

        options = {
            "quiet": True,
            "skip_download": True,
            "no_warnings": True,
            "extract_flat": False,
            "noplaylist": True,
        }
        try:
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
        except DownloadError as exc:
            message = str(exc)
            if "Private video" in message:
                raise YouTubeMetadataError("This video is private and cannot be ingested.") from exc
            if "age" in message.lower() and "restrict" in message.lower():
                raise YouTubeMetadataError("This video is age-restricted and cannot be ingested.") from exc
            raise YouTubeMetadataError(f"Unable to fetch YouTube metadata: {message}") from exc

        thumbnails = info.get("thumbnails") or []
        thumbnail_url = info.get("thumbnail") or (
            thumbnails[-1].get("url", "") if thumbnails else f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
        )

        return YouTubeMetadata(
            video_id=video_id,
            title=info.get("title") or "Untitled YouTube video",
            channel_name=info.get("channel") or info.get("uploader") or "Unknown channel",
            duration_seconds=int(info.get("duration") or 0),
            thumbnail_url=thumbnail_url,
            published_date=str(info.get("upload_date") or ""),
        )

    def _group_transcript(
        self,
        transcript: list[dict[str, Any]],
        metadata: YouTubeMetadata,
    ) -> list[dict[str, Any]]:
        grouped: list[dict[str, Any]] = []
        current_texts: list[str] = []
        window_start = 0.0
        window_end = 0.0

        for item in transcript:
            text = str(item.get("text", "")).replace("\n", " ").strip()
            if not text:
                continue

            start = float(item.get("start", 0.0))
            duration = float(item.get("duration", 0.0))
            end = start + duration

            if not current_texts:
                window_start = start
                window_end = end

            current_texts.append(text)
            window_end = max(window_end, end)

            if window_end - window_start >= self.WINDOW_SECONDS:
                grouped.append(self._build_segment(current_texts, window_start, window_end, metadata))
                current_texts = []

        if current_texts:
            grouped.append(self._build_segment(current_texts, window_start, window_end, metadata))

        if not grouped:
            raise TranscriptNotAvailableError("Transcript captions were found, but they did not contain usable text.")

        return grouped

    def _build_segment(
        self,
        texts: list[str],
        start_seconds: float,
        end_seconds: float,
        metadata: YouTubeMetadata,
    ) -> dict[str, Any]:
        return {
            "text": " ".join(texts),
            "start_seconds": round(start_seconds, 2),
            "duration_seconds": round(max(end_seconds - start_seconds, 0.0), 2),
            "video_id": metadata.video_id,
            "video_title": metadata.title,
            "title": metadata.title,
            "channel_name": metadata.channel_name,
            "thumbnail_url": metadata.thumbnail_url,
            "published_date": metadata.published_date,
            "video_duration_seconds": metadata.duration_seconds,
            "source_url": f"https://youtu.be/{metadata.video_id}?t={int(start_seconds)}",
            "source_type": "youtube",
        }

    @staticmethod
    def _snippet_to_dict(snippet: Any) -> dict[str, Any]:
        if isinstance(snippet, dict):
            return snippet
        return {
            "text": getattr(snippet, "text", ""),
            "start": getattr(snippet, "start", 0.0),
            "duration": getattr(snippet, "duration", 0.0),
        }


def parse(url: str, user_id: str | None = None) -> list[dict[str, Any]]:
    """Convenience parser function used by ingestion callers."""
    return YouTubeParser().parse(url, user_id=user_id)
