"""Parsing utilities for RFC/MIME email messages."""

from __future__ import annotations

from email import policy
from email.message import Message
from email.parser import BytesParser
from pathlib import Path
from typing import Any


class EmailParser:
    """Convert an ``.eml`` file or parsed message into plain structures."""

    def parse_file(self, path: Path) -> dict[str, Any]:
        """Read and parse an EML file from disk."""
        message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
        return self.parse_message(message, path.name)

    def parse_message(
        self,
        message: Message,
        email_id: str,
    ) -> dict[str, Any]:
        """Extract headers, text parts, HTML parts and attachments.

        Text decoding is tolerant: malformed byte sequences are replaced so
        that one damaged MIME part does not stop analysis of the message.
        """
        headers = {
            key.lower(): str(value)
            for key, value in message.items()
        }

        text_parts: list[str] = []
        html_parts: list[str] = []
        attachments: list[dict[str, Any]] = []
        parts = message.walk() if message.is_multipart() else [message]

        for index, part in enumerate(parts):
            if part.is_multipart():
                continue

            payload = part.get_payload(decode=True)
            if payload is None:
                continue

            content_type = part.get_content_type()
            disposition = part.get_content_disposition()
            filename = part.get_filename()

            if disposition == "attachment" or filename:
                attachments.append(
                    {
                        "index": index,
                        "filename": filename,
                        "content_type": content_type,
                        "size": len(payload),
                    }
                )
                continue

            text = payload.decode(
                part.get_content_charset() or "utf-8",
                errors="replace",
            )

            if content_type == "text/html":
                html_parts.append(text)
            else:
                text_parts.append(text)

        return {
            "email_id": email_id,
            "headers": headers,
            "text": "\n\n".join(text_parts),
            "html": "\n\n".join(html_parts),
            "attachments": attachments,
        }


__all__ = ["EmailParser"]
