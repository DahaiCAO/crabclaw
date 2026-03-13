"""Multimodal support for Crabclaw."""

import base64
import io
import mimetypes
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger


class MediaType(Enum):
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"


@dataclass
class MediaContent:
    """Content with media type."""
    media_type: MediaType
    data: bytes | str
    mime_type: str
    filename: str | None = None
    url: str | None = None

    @property
    def is_url(self) -> bool:
        return self.url is not None

    @property
    def is_base64(self) -> bool:
        return isinstance(self.data, str) and "," in self.data


class MediaProcessor(ABC):
    """Abstract base class for media processing."""

    @abstractmethod
    async def process(self, content: MediaContent) -> dict[str, Any]:
        """Process media and return structured data."""
        pass

    @abstractmethod
    def supports(self, media_type: MediaType) -> bool:
        """Check if this processor supports a media type."""
        pass


class ImageProcessor(MediaProcessor):
    """Processor for image content."""

    SUPPORTED_FORMATS = {"png", "jpeg", "jpg", "gif", "webp", "bmp"}

    def supports(self, media_type: MediaType) -> bool:
        return media_type == MediaType.IMAGE

    async def process(self, content: MediaContent) -> dict[str, Any]:
        """Process image content."""
        if content.is_url:
            return {
                "type": "image_url",
                "image_url": {"url": content.url}
            }

        image_data = content.data
        if isinstance(image_data, str):
            if "," in image_data:
                image_data = image_data.split(",", 1)[1]
            image_data = base64.b64decode(image_data)

        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:{content.mime_type};base64,{base64.b64encode(image_data).decode()}"
            }
        }


class AudioProcessor(MediaProcessor):
    """Processor for audio content."""

    SUPPORTED_FORMATS = {"mp3", "wav", "ogg", "flac", "m4a", "webm"}

    def supports(self, media_type: MediaType) -> bool:
        return media_type == MediaType.AUDIO

    async def process(self, content: MediaContent) -> dict[str, Any]:
        """Process audio content for transcription."""
        audio_data = content.data
        if isinstance(audio_data, str):
            if "," in audio_data:
                audio_data = audio_data.split(",", 1)[1]
            audio_data = base64.b64decode(audio_data)

        return {
            "type": "audio",
            "data": base64.b64encode(audio_data).decode(),
            "mime_type": content.mime_type
        }


class VideoProcessor(MediaProcessor):
    """Processor for video content."""

    SUPPORTED_FORMATS = {"mp4", "webm", "avi", "mov"}

    def supports(self, media_type: MediaType) -> bool:
        return media_type == MediaType.VIDEO

    async def process(self, content: MediaContent) -> dict[str, Any]:
        """Process video content."""
        return {
            "type": "video",
            "url": content.url or f"data:{content.mime_type};base64,{content.data}",
            "mime_type": content.mime_type
        }


class MultimodalContentBuilder:
    """Builder for multimodal content."""

    def __init__(self):
        self._processors: list[MediaProcessor] = [
            ImageProcessor(),
            AudioProcessor(),
            VideoProcessor(),
        ]

    def add_processor(self, processor: MediaProcessor) -> None:
        """Add a custom media processor."""
        self._processors.append(processor)

    def _detect_media_type(self, filename: str, mime_type: str | None) -> MediaType | None:
        """Detect media type from filename or mime type."""
        if mime_type:
            if mime_type.startswith("image/"):
                return MediaType.IMAGE
            if mime_type.startswith("audio/"):
                return MediaType.AUDIO
            if mime_type.startswith("video/"):
                return MediaType.VIDEO

        ext = Path(filename).suffix.lower().lstrip(".")
        if ext in ImageProcessor.SUPPORTED_FORMATS:
            return MediaType.IMAGE
        if ext in AudioProcessor.SUPPORTED_FORMATS:
            return MediaType.AUDIO
        if ext in VideoProcessor.SUPPORTED_FORMATS:
            return MediaType.VIDEO

        return None

    def _get_mime_type(self, filename: str) -> str:
        """Get mime type from filename."""
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or "application/octet-stream"

    def from_file(self, file_path: str | Path) -> MediaContent:
        """Create media content from a file."""
        path = Path(file_path)
        mime_type = self._get_mime_type(str(path))
        media_type = self._detect_media_type(str(path), mime_type)

        if media_type is None:
            raise ValueError(f"Unsupported file type: {path.suffix}")

        data = path.read_bytes()
        return MediaContent(
            media_type=media_type,
            data=data,
            mime_type=mime_type,
            filename=path.name
        )

    def from_url(self, url: str, media_type: MediaType | None = None) -> MediaContent:
        """Create media content from a URL."""
        if media_type is None:
            raise ValueError("Media type must be specified for URL content")

        ext = Path(url).suffix.lower().lstrip(".")
        mime_type = self._get_mime_type(f"file.{ext}")

        return MediaContent(
            media_type=media_type,
            data="",
            mime_type=mime_type,
            url=url
        )

    def from_base64(self, data: str, filename: str | None = None) -> MediaContent:
        """Create media content from base64 data."""
        mime_type = self._get_mime_type(filename or "file.bin")
        media_type = self._detect_media_type(filename or "file", mime_type)

        if media_type is None:
            raise ValueError("Could not detect media type from filename")

        return MediaContent(
            media_type=media_type,
            data=data,
            mime_type=mime_type,
            filename=filename
        )

    async def build_message_content(
        self,
        text: str | None = None,
        media: list[MediaContent] | None = None
    ) -> str | list[dict[str, Any]]:
        """Build message content with text and media."""
        parts: list[dict[str, Any]] = []

        if text:
            parts.append({"type": "text", "text": text})

        if media:
            for m in media:
                processor = self._get_processor(m.media_type)
                if processor:
                    processed = await processor.process(m)
                    parts.append(processed)

        if len(parts) == 1 and isinstance(parts[0], dict) and parts[0].get("type") == "text":
            return parts[0]["text"]

        return parts

    def _get_processor(self, media_type: MediaType) -> MediaProcessor | None:
        """Get processor for media type."""
        for processor in self._processors:
            if processor.supports(media_type):
                return processor
        return None


class VisionClient:
    """Client for vision model interactions."""

    def __init__(self, provider: Any):
        self._provider = provider
        self._builder = MultimodalContentBuilder()

    async def analyze_image(
        self,
        image: MediaContent,
        prompt: str = "Describe this image in detail."
    ) -> str:
        """Analyze an image using vision capabilities."""
        processed = await self._builder._get_processor(MediaType.IMAGE).process(image)

        messages = [
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                processed
            ]}
        ]

        response = await self._provider.chat(messages)
        return response.content or ""


class TranscriptionClient:
    """Client for audio transcription."""

    def __init__(self, provider: Any):
        self._provider = provider

    async def transcribe(
        self,
        audio: MediaContent,
        language: str | None = None
    ) -> str:
        """Transcribe audio content."""
        processor = AudioProcessor()
        processed = await processor.process(audio)

        messages = [
            {"role": "user", "content": [
                {"type": "text", "text": "Transcribe this audio."},
                processed
            ]}
        ]

        response = await self._provider.chat(messages)
        return response.content or ""


multimodal_builder = MultimodalContentBuilder()


__all__ = [
    "MediaType",
    "MediaContent",
    "MediaProcessor",
    "ImageProcessor",
    "AudioProcessor",
    "VideoProcessor",
    "MultimodalContentBuilder",
    "VisionClient",
    "TranscriptionClient",
    "multimodal_builder",
]
