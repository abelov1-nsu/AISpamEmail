"""
EML Dataset Workbench
Single-file local email builder and AI-inclusion dataset tool.

Requirements:
    Python 3.9+
    requests

All other dependencies are from the Python standard library.
The application creates local .eml files; it never sends email.
"""

from __future__ import annotations

import html
import json
import mimetypes
import os
import random
import re
import threading
import uuid
import stat
import webbrowser
from datetime import datetime, timezone
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import formatdate, make_msgid, getaddresses, parseaddr
from html.parser import HTMLParser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

try:
    import requests
except ImportError:
    requests = None


APP_NAME = "EML Dataset Workbench"
IMAGE_RE = re.compile(r"\[\[IMAGE:([^\]]+)\]\]")
AI_OPEN = "<AI>"
AI_CLOSE = "</AI>"


class ToolTip:
    """Small Tk tooltip with Russian technical explanations."""
    def __init__(self, widget, text, delay=450):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.window = None
        self.after_id = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._cancel()
        self.after_id = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self.after_id:
            try:
                self.widget.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None

    def _show(self):
        if self.window or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 14
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
            win = tk.Toplevel(self.widget)
            win.wm_overrideredirect(True)
            win.wm_geometry(f"+{x}+{y}")
            label = tk.Label(
                win, text=self.text, justify="left", wraplength=390,
                background="#fff8dc", foreground="#222", relief="solid",
                borderwidth=1, padx=9, pady=6,
            )
            label.pack()
            self.window = win
        except tk.TclError:
            self.window = None

    def _hide(self, _event=None):
        self._cancel()
        if self.window:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
            self.window = None


class OpenWebUIClient:
    """OpenAI-compatible HTTP transport for Open WebUI."""

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        model: str = "",
        timeout: float = 90.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def list_models(self) -> list[str]:
        """Fetch model IDs from Open WebUI's /api/models endpoint."""
        if requests is None:
            raise RuntimeError("Не установлен пакет requests. Выполните: pip install requests")
        if not self.base_url:
            raise RuntimeError("Сначала укажите базовый URL сервера.")
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        response = requests.get(
            f"{self.base_url}/api/models", headers=headers, timeout=self.timeout
        )
        if not response.ok:
            raise RuntimeError(
                f"Ошибка HTTP {response.status_code} при загрузке моделей.\n"
                f"Ответ сервера: {response.text[:2000]}"
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(f"Сервер вернул не JSON: {response.text[:1000]}") from exc
        if isinstance(data, dict):
            items = data.get("data", data.get("models", []))
        else:
            items = data
        if not isinstance(items, list):
            raise RuntimeError("Неожиданный формат /api/models: ожидался список моделей.")
        ids = []
        for item in items:
            if isinstance(item, str):
                model_id = item
            elif isinstance(item, dict):
                model_id = item.get("id") or item.get("name") or item.get("model")
            else:
                model_id = None
            if isinstance(model_id, str) and model_id.strip():
                ids.append(model_id.strip())
        return list(dict.fromkeys(ids))

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 2048,
        response_format_json: bool = True,
    ) -> str:
        if requests is None:
            raise RuntimeError("The 'requests' package is missing. Install it with: pip install requests")
        if not self.base_url or not self.model:
            raise RuntimeError("Configure the Open WebUI base URL and model first.")

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = requests.post(
            f"{self.base_url}/api/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        if not response.ok:
            raise RuntimeError(
                f"Ошибка Open WebUI: HTTP {response.status_code}\n"
                f"URL: {response.url}\n"
                f"Ответ сервера: {response.text[:3000]}\n\n"
                f"Проверьте точный ID модели и параметры запроса."
            )
        try:
            content = response.json()["choices"][0]["message"]["content"]
            if isinstance(content, list):
                content = "".join(
                    part.get("text", "") for part in content if isinstance(part, dict)
                )
            if not isinstance(content, str):
                raise TypeError("message content is not text")
            return content
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                f"Unexpected Open WebUI response shape: {response.text[:1000]}"
            ) from exc


def split_ai_segments(text: str) -> list[dict]:
    """Remove annotation tags and return contiguous text/AI-labelled segments."""
    segments = []
    cursor = 0
    ai_state = False

    for match in re.finditer(r"</?AI>", text, flags=re.IGNORECASE):
        chunk = text[cursor:match.start()]
        if chunk:
            if segments and segments[-1]["ai"] == ai_state:
                segments[-1]["text"] += chunk
            else:
                segments.append({"text": chunk, "ai": ai_state})
        tag = match.group(0).upper()
        if tag == AI_OPEN:
            ai_state = True
        else:
            ai_state = False
        cursor = match.end()

    tail = text[cursor:]
    if tail:
        if segments and segments[-1]["ai"] == ai_state:
            segments[-1]["text"] += tail
        else:
            segments.append({"text": tail, "ai": ai_state})

    # Keep an explicit empty segment for an empty body.
    return segments or [{"text": "", "ai": False}]


class PlainTextFromHTML(HTMLParser):
    """Extract readable text and AI annotations from HTML source."""

    BLOCKS = {
        "p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4",
        "blockquote", "section", "article", "header", "footer",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.ai = False
        self.segments = []

    def _append(self, value):
        if not value:
            return
        if self.segments and self.segments[-1]["ai"] == self.ai:
            self.segments[-1]["text"] += value
        else:
            self.segments.append({"text": value, "ai": self.ai})

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "ai":
            self.ai = True
        elif tag.lower() == "img":
            attrs_map = dict(attrs)
            src = attrs_map.get("src", "")
            alt = attrs_map.get("alt", "")
            cid_map = getattr(self, "image_cid_map", {})
            marker = cid_map.get(src)
            if marker:
                self._append(f"[[IMAGE:{marker}]]")
            elif alt:
                self._append(f"[Image: {alt}]")
        elif tag.lower() in self.BLOCKS:
            self._append("\n")

    def handle_endtag(self, tag):
        if tag.lower() == "ai":
            self.ai = False
        elif tag.lower() in self.BLOCKS:
            self._append("\n")

    def handle_data(self, data):
        self._append(data)

    def result(self):
        combined = []
        for segment in self.segments:
            value = segment["text"]
            # Collapse excessive structural whitespace without flattening paragraphs.
            value = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", value)
            if value:
                if combined and combined[-1]["ai"] == segment["ai"]:
                    combined[-1]["text"] += value
                else:
                    combined.append({"text": value, "ai": segment["ai"]})
        return combined or [{"text": "", "ai": False}]


def segments_to_text(segments):
    return "".join(part["text"] for part in segments)


def strip_ai_tags(value):
    return re.sub(r"</?AI>", "", value, flags=re.IGNORECASE)


def safe_filename(value):
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return (value[:70] or "email")


def html_from_annotated_text(body, image_map):
    """Convert annotated plain text into HTML; image placeholders become CID images."""
    chunks = []
    cursor = 0
    ai_state = False

    def convert_fragment(fragment, marked):
        # Escape all user text before introducing controlled HTML.
        escaped = html.escape(fragment, quote=True)
        escaped = escaped.replace("\r\n", "\n").replace("\r", "\n")
        escaped = escaped.replace("\n", "<br>\n")

        def image_sub(match):
            key = match.group(1)
            info = image_map.get(key)
            if not info:
                return html.escape(match.group(0))
            cid = info["cid"]
            alt = html.escape(info["name"], quote=True)
            return (
                f'<img src="cid:{cid}" alt="{alt}" '
                'style="max-width:100%;height:auto;display:block;margin:12px 0;">'
            )

        escaped = IMAGE_RE.sub(image_sub, escaped)
        if marked:
            return f"<AI>{escaped}</AI>"
        return escaped

    for match in re.finditer(r"</?AI>", body, flags=re.IGNORECASE):
        chunks.append(convert_fragment(body[cursor:match.start()], ai_state))
        ai_state = match.group(0).upper() == AI_OPEN
        cursor = match.end()
    chunks.append(convert_fragment(body[cursor:], ai_state))
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\"></head>"
        "<body style=\"font-family:Arial,sans-serif;font-size:14px;line-height:1.5;\">"
        + "".join(chunks)
        + "</body></html>"
    )


def validate_addresses(value, field, required=False):
    if not value.strip():
        if required:
            raise ValueError(f"{field} is required.")
        return
    # getaddresses handles display names containing commas more reliably than split(",").
    parsed = getaddresses([value])
    valid = [addr for _, addr in parsed if addr]
    if not valid or len(valid) != len([x for x in parsed if x[1]]):
        raise ValueError(f"Please check the {field} address field.")
    for addr in valid:
        if "@" not in addr or addr.startswith("@") or addr.endswith("@") or any(c.isspace() for c in addr):
            raise ValueError(f"Invalid {field} address: {addr}")


def json_from_ai(content):
    """Accept strict JSON, with a conservative fallback for fenced JSON."""
    value = content.strip()
    value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*```$", "", value)
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("AI response must be a JSON object.")
    return parsed


class EMLWorkbench:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1120x850")
        self.root.minsize(850, 650)

        self.settings_path = Path.home() / ".eml_dataset_workbench" / "settings.json"
        saved = self._load_settings()
        self.output_dir = tk.StringVar(value=saved.get("output_dir", str(Path.home() / "EML Dataset")))
        self.from_var = tk.StringVar(value="sender@example.test")
        self.to_var = tk.StringVar(value="recipient@example.test")
        self.cc_var = tk.StringVar()
        self.bcc_var = tk.StringVar()
        self.reply_to_var = tk.StringVar()
        self.subject_var = tk.StringVar(value="A sample email")
        self.message_id_var = tk.StringVar()
        self.in_reply_to_var = tk.StringVar()
        self.references_var = tk.StringVar()

        self.base_url_var = tk.StringVar(value=saved.get("base_url", "http://localhost:3000"))
        self.api_key_var = tk.StringVar(value=saved.get("api_key", ""))
        self.model_var = tk.StringVar(value=saved.get("model", ""))
        self.timeout_var = tk.StringVar(value=str(saved.get("timeout", "90")))
        self.temperature_var = tk.StringVar(value=str(saved.get("temperature", "0.3")))
        self.max_tokens_var = tk.StringVar(value=str(saved.get("max_tokens", "2048")))
        self.model_combo = None
        self.models_status_var = tk.StringVar(value="Модели ещё не загружены")

        self.images = {}       # marker name -> file path
        self.attachments = []
        self.html_mode = False
        self.current_html = None
        self.html_cid_markers = {}
        self.busy = False
        self.last_saved = None
        self._build_ui()
        for variable in (self.output_dir, self.base_url_var, self.api_key_var, self.model_var,
                         self.timeout_var, self.temperature_var, self.max_tokens_var):
            variable.trace_add("write", self._schedule_save_settings)
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)
        self.root.after(500, self.refresh_models)

    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)

        top = ttk.Frame(outer)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="Output folder").pack(side="left")
        ttk.Entry(top, textvariable=self.output_dir).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(top, text="Browse…", command=self.choose_folder).pack(side="left")

        self.tabs = ttk.Notebook(outer)
        self.tabs.pack(fill="both", expand=True)

        self.email_tab = ttk.Frame(self.tabs, padding=8)
        self.ai_tab = ttk.Frame(self.tabs, padding=8)
        self.dataset_tab = ttk.Frame(self.tabs, padding=8)
        self.settings_tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(self.email_tab, text="Email")
        self.tabs.add(self.ai_tab, text="AI tools")
        self.tabs.add(self.dataset_tab, text="Dataset")
        self.tabs.add(self.settings_tab, text="AI connection")

        self._build_email_tab()
        self._build_ai_tab()
        self._build_dataset_tab()
        self._build_settings_tab()

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(8, 0))
        self.status_var = tk.StringVar(value="Ready — files are saved locally and never sent.")
        ttk.Label(bottom, textvariable=self.status_var).pack(side="left", fill="x", expand=True)
        ttk.Button(bottom, text="Clear", command=self.clear_form).pack(side="right", padx=(6, 0))
        ttk.Button(bottom, text="Preview", command=self.preview_email).pack(side="right", padx=(6, 0))
        ttk.Button(bottom, text="Create .eml + JSON", command=self.save_email).pack(side="right")

    def _build_email_tab(self):
        fields = ttk.LabelFrame(self.email_tab, text="Headers", padding=8)
        fields.pack(fill="x", pady=(0, 8))
        rows = [
            ("From *", self.from_var), ("To *", self.to_var),
            ("CC", self.cc_var), ("BCC", self.bcc_var),
            ("Reply-To", self.reply_to_var), ("Subject *", self.subject_var),
            ("Message-ID (optional)", self.message_id_var),
            ("In-Reply-To", self.in_reply_to_var), ("References", self.references_var),
        ]
        for i, (label, var) in enumerate(rows):
            r, c = divmod(i, 2)
            ttk.Label(fields, text=label).grid(row=r, column=c * 2, sticky="w", padx=(0, 5), pady=3)
            ttk.Entry(fields, textvariable=var).grid(row=r, column=c * 2 + 1, sticky="ew", padx=(0, 12), pady=3)
        fields.columnconfigure(1, weight=1)
        fields.columnconfigure(3, weight=1)

        editor_frame = ttk.LabelFrame(self.email_tab, text="Message body", padding=8)
        editor_frame.pack(fill="both", expand=True)
        toolbar = ttk.Frame(editor_frame)
        toolbar.pack(fill="x", pady=(0, 5))
        ttk.Button(toolbar, text="Insert inline image at cursor…", command=self.add_inline_image).pack(side="left")
        ttk.Button(toolbar, text="Add attachment…", command=self.add_attachments).pack(side="left", padx=5)
        ttk.Button(toolbar, text="HTML source", command=self.open_html_source).pack(side="left")
        ttk.Button(toolbar, text="Insert <AI> markers", command=self.wrap_selection_ai).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Check annotations", command=self.check_annotations).pack(side="left")
        self.body = tk.Text(editor_frame, wrap="word", undo=True, font=("Segoe UI", 10), height=18)
        self.body.pack(fill="both", expand=True)
        self.body.bind("<KeyRelease>", self._body_edited)
        self.body.insert("1.0", "Hello,\n\nI wanted to ask about the delivery.\n\nPlease let me know if you have an update.\n\nBest regards.")
        self.media_var = tk.StringVar(value="No inline images or attachments.")
        ttk.Label(editor_frame, textvariable=self.media_var, foreground="#555").pack(anchor="w", pady=(5, 0))
        ttk.Label(
            editor_frame,
            text="AI content is marked with literal <AI> and </AI> tags. Image placeholders are inserted at the cursor.",
            foreground="#555",
        ).pack(anchor="w")

    def _build_ai_tab(self):
        split = ttk.Panedwindow(self.ai_tab, orient="horizontal")
        split.pack(fill="both", expand=True)
        left = ttk.Frame(split, padding=5)
        right = ttk.Frame(split, padding=5)
        split.add(left, weight=3)
        split.add(right, weight=2)

        ttk.Label(left, text="Context-aware snippet generation", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(left, text="The current subject, headers, and body are supplied as context.").pack(anchor="w", pady=(2, 8))
        ttk.Label(left, text="What should the snippet communicate?").pack(anchor="w")
        self.snippet_prompt = tk.Text(left, height=5, wrap="word")
        self.snippet_prompt.pack(fill="x", pady=(2, 8))
        controls = ttk.Frame(left)
        controls.pack(fill="x")
        ttk.Label(controls, text="Target tokens").pack(side="left")
        self.snippet_tokens = tk.StringVar(value="120")
        ttk.Spinbox(controls, from_=10, to=4000, increment=10, textvariable=self.snippet_tokens, width=8).pack(side="left", padx=5)
        ttk.Label(controls, text="Type").pack(side="left", padx=(12, 3))
        self.snippet_type = tk.StringVar(value="paragraph")
        ttk.Combobox(
            controls, textvariable=self.snippet_type, state="readonly", width=16,
            values=("paragraph", "sentence", "reply segment", "greeting", "closing", "signature", "custom"),
        ).pack(side="left")
        ttk.Label(left, text="Style").pack(anchor="w", pady=(8, 2))
        self.snippet_style = tk.StringVar(value="natural and contextually appropriate")
        ttk.Entry(left, textvariable=self.snippet_style).pack(fill="x")
        ttk.Button(left, text="Generate and insert at cursor", command=self.generate_snippet).pack(anchor="w", pady=8)

        ttk.Separator(left).pack(fill="x", pady=8)
        ttk.Label(left, text="Rewrite entire email", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.rewrite_mode = tk.StringVar(value="Improve writing while preserving meaning")
        ttk.Combobox(
            left, textvariable=self.rewrite_mode, state="readonly",
            values=(
                "Full rewrite with a new formulation",
                "Improve writing while preserving meaning",
                "Expand with contextual detail",
                "Condense",
                "Change tone to formal",
                "Change tone to casual",
                "Continue the email",
            ),
        ).pack(fill="x", pady=(5, 0))
        ttk.Button(left, text="Rewrite entire body (mark as AI)", command=self.rewrite_email).pack(anchor="w", pady=8)

        ttk.Label(right, text="AI output / preview", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.ai_output = tk.Text(right, wrap="word", state="disabled", font=("Segoe UI", 9))
        self.ai_output.pack(fill="both", expand=True, pady=(5, 0))
        output_actions = ttk.Frame(right)
        output_actions.pack(fill="x", pady=(6, 0))
        ttk.Button(output_actions, text="Insert snippet at cursor", command=self.insert_ai_output_as_snippet).pack(side="left")
        ttk.Button(output_actions, text="Apply as full rewrite", command=self.apply_rewrite).pack(side="left", padx=5)
        ttk.Label(
            right,
            text="Generated snippets are automatically wrapped in <AI> tags. Review before saving.",
            foreground="#555", wraplength=280,
        ).pack(anchor="w", pady=5)

    def _build_dataset_tab(self):
        ttk.Label(self.dataset_tab, text="Dataset controls", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(
            self.dataset_tab,
            text="Each saved email gets a companion JSON file containing contiguous text segments and their AI labels. "
                 "The JSON is ground truth; do not expose it to the classifier as an input feature.",
            wraplength=900,
        ).pack(anchor="w", pady=(4, 10))

        stats = ttk.LabelFrame(self.dataset_tab, text="Current draft annotation statistics", padding=8)
        stats.pack(fill="x", pady=(0, 8))
        self.stats_var = tk.StringVar(value="Press Refresh to calculate segment and token estimates.")
        ttk.Label(stats, textvariable=self.stats_var).pack(anchor="w")
        ttk.Button(stats, text="Refresh statistics", command=self.refresh_stats).pack(anchor="w", pady=(5, 0))

        batch = ttk.LabelFrame(self.dataset_tab, text="Batch generation (AI-only samples)", padding=8)
        batch.pack(fill="x", pady=(0, 8))
        ttk.Label(batch, text="Generate multiple independently prompted AI-written emails. These are labelled AI=true throughout.").pack(anchor="w")
        row = ttk.Frame(batch)
        row.pack(fill="x", pady=5)
        ttk.Label(row, text="Count").pack(side="left")
        self.batch_count = tk.StringVar(value="5")
        ttk.Spinbox(row, from_=1, to=100, textvariable=self.batch_count, width=6).pack(side="left", padx=5)
        ttk.Label(row, text="Topic / scenario").pack(side="left", padx=(12, 4))
        self.batch_topic = tk.StringVar(value="Everyday professional and personal email scenarios")
        ttk.Entry(row, textvariable=self.batch_topic).pack(side="left", fill="x", expand=True)
        ttk.Button(batch, text="Generate batch", command=self.generate_batch).pack(anchor="w")

        tools = ttk.LabelFrame(self.dataset_tab, text="Dataset utilities", padding=8)
        tools.pack(fill="x")
        ttk.Button(tools, text="Validate current draft", command=self.validate_draft).pack(side="left")
        ttk.Button(tools, text="Open output folder", command=self.open_output_folder).pack(side="left", padx=5)
        ttk.Button(tools, text="Export dataset manifest", command=self.export_manifest).pack(side="left")
        ttk.Label(
            self.dataset_tab,
            text="Important: batch-generated AI emails are not human examples. Create human-only examples from genuinely human-written source material, "
                 "and keep train/test splits grouped by source, model, template, or generation session to reduce leakage.",
            wraplength=900, foreground="#7a4b00",
        ).pack(anchor="w", pady=12)

    def _build_settings_tab(self):
        frame = ttk.LabelFrame(self.settings_tab, text="Подключение к Open WebUI", padding=10)
        frame.pack(fill="x", anchor="n")

        url_label = ttk.Label(frame, text="Базовый адрес сервера")
        url_label.grid(row=0, column=0, sticky="w", pady=4, padx=(0, 8))
        ttk.Entry(frame, textvariable=self.base_url_var).grid(row=0, column=1, columnspan=2, sticky="ew", pady=4)
        ToolTip(url_label, "Корневой адрес Open WebUI, например http://localhost:3000. Не добавляйте сюда /api и /api/chat/completions: приложение добавит путь самостоятельно. Если сервер опубликован через подпуть reverse proxy, укажите этот подпуть после домена.")

        key_label = ttk.Label(frame, text="API-ключ (необязательно)")
        key_label.grid(row=1, column=0, sticky="w", pady=4, padx=(0, 8))
        ttk.Entry(frame, textvariable=self.api_key_var, show="*").grid(row=1, column=1, columnspan=2, sticky="ew", pady=4)
        ToolTip(key_label, "Ключ передаётся в заголовке Authorization: Bearer … для запросов к /api/models и /api/chat/completions. Если сервер не требует авторизацию, поле можно оставить пустым.")

        model_label = ttk.Label(frame, text="Модель (ID из API)")
        model_label.grid(row=2, column=0, sticky="w", pady=4, padx=(0, 8))
        self.model_combo = ttk.Combobox(frame, textvariable=self.model_var, state="normal")
        self.model_combo.grid(row=2, column=1, sticky="ew", pady=4)
        ToolTip(model_label, "Используйте именно ID модели, возвращённый /api/models, а не её отображаемое название. Сравнение ID может учитывать регистр: если сервер показывает qwen3:8b, значение Qwen3:8B может привести к HTTP 400. Выберите модель из списка, чтобы избежать опечаток.")
        refresh_button = ttk.Button(frame, text="Загрузить модели", command=self.refresh_models)
        refresh_button.grid(row=2, column=2, sticky="ew", padx=(6, 0), pady=4)
        ToolTip(refresh_button, "Выполняет GET-запрос к {базовый_адрес}/api/models и заполняет список точными ID. Требует доступности сервера и корректного API-ключа.")
        lower_button = ttk.Button(frame, text="В нижний регистр", command=self.lowercase_model)
        lower_button.grid(row=3, column=1, sticky="w", pady=(0, 4))
        ToolTip(lower_button, "Преобразует введённый ID модели в нижний регистр. Используйте только если именно такой ID указан в /api/models. Не все серверы требуют lowercase; безопаснее выбирать точное значение из списка.")
        ttk.Label(frame, textvariable=self.models_status_var, foreground="#555").grid(row=3, column=2, sticky="w", padx=(6, 0))

        timeout_label = ttk.Label(frame, text="Тайм-аут, секунд")
        timeout_label.grid(row=4, column=0, sticky="w", pady=4, padx=(0, 8))
        ttk.Entry(frame, textvariable=self.timeout_var, width=12).grid(row=4, column=1, sticky="w", pady=4)
        ToolTip(timeout_label, "Максимальное время ожидания HTTP-ответа. Большие модели и длинные ответы могут генерироваться дольше обычного; при тайм-ауте увеличьте значение.")

        temp_label = ttk.Label(frame, text="Температура")
        temp_label.grid(row=5, column=0, sticky="w", pady=4, padx=(0, 8))
        ttk.Entry(frame, textvariable=self.temperature_var, width=12).grid(row=5, column=1, sticky="w", pady=4)
        ToolTip(temp_label, "Параметр temperature управляет случайностью генерации. Низкие значения дают более стабильный результат; высокие — больше разнообразия. Некоторые backend-модели могут ограничивать допустимый диапазон.")

        tokens_label = ttk.Label(frame, text="Максимум токенов по умолчанию")
        tokens_label.grid(row=6, column=0, sticky="w", pady=4, padx=(0, 8))
        ttk.Entry(frame, textvariable=self.max_tokens_var, width=12).grid(row=6, column=1, sticky="w", pady=4)
        ToolTip(tokens_label, "Передаётся как max_tokens в запросе генерации. Это верхняя граница длины ответа, а не точное число токенов. Поддержка и лимиты зависят от модели и backend.")

        frame.columnconfigure(1, weight=1)
        ttk.Label(
            frame,
            text="Запросы: GET {URL}/api/models и POST {URL}/api/chat/completions\n"
                 "Настройки сохраняются локально в домашней папке пользователя. API-ключ хранится в файле настроек в открытом виде; не используйте общий аккаунт Windows.",
            foreground="#555", wraplength=850, justify="left",
        ).grid(row=7, column=0, columnspan=3, sticky="w", pady=(9, 4))
        ttk.Button(frame, text="Проверить генерацию", command=self.test_connection).grid(row=8, column=0, sticky="w", pady=5)
        ttk.Button(frame, text="Сохранить настройки", command=self.save_settings).grid(row=8, column=1, sticky="w", pady=5)

    def _load_settings(self):
        try:
            if self.settings_path.exists():
                data = json.loads(self.settings_path.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            pass
        return {}

    def _schedule_save_settings(self, *_args):
        # Save directly; values are small and this avoids losing settings on abrupt close.
        self.save_settings(silent=True)

    def save_settings(self, silent=False):
        data = {
            "output_dir": self.output_dir.get(),
            "base_url": self.base_url_var.get().strip(),
            "api_key": self.api_key_var.get(),
            "model": self.model_var.get().strip(),
            "timeout": self.timeout_var.get().strip(),
            "temperature": self.temperature_var.get().strip(),
            "max_tokens": self.max_tokens_var.get().strip(),
        }
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            self.settings_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            try:
                self.settings_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
            except OSError:
                pass
            if not silent:
                messagebox.showinfo("Настройки", f"Настройки сохранены в:\n{self.settings_path}")
        except OSError as exc:
            if not silent:
                messagebox.showerror("Ошибка сохранения настроек", str(exc))

    def close_app(self):
        self.save_settings(silent=True)
        self.root.destroy()

    def lowercase_model(self):
        self.model_var.set(self.model_var.get().strip().lower())

    def refresh_models(self):
        if self.busy:
            messagebox.showinfo("Запрос выполняется", "Дождитесь завершения текущего AI-запроса.")
            return
        self.busy = True
        self.models_status_var.set("Загрузка списка моделей…")
        self.status_var.set("Запрос списка моделей Open WebUI…")

        def worker():
            try:
                try:
                    timeout = float(self.timeout_var.get())
                except ValueError:
                    timeout = 90.0
                client = OpenWebUIClient(self.base_url_var.get().strip(), self.api_key_var.get(), timeout=timeout)
                models = client.list_models()
                self.root.after(0, lambda values=models: self._models_loaded(values, None))
            except Exception as exc:
                self.root.after(0, lambda err=str(exc): self._models_loaded([], err))

        threading.Thread(target=worker, daemon=True).start()

    def _models_loaded(self, models, error):
        self.busy = False
        if error:
            self.models_status_var.set("Не удалось загрузить модели")
            self.status_var.set("Ошибка загрузки моделей.")
            messagebox.showerror("Ошибка /api/models", error)
            return
        current = self.model_var.get().strip()
        values = list(models)
        if current and current not in values:
            values.insert(0, current)
        self.model_combo["values"] = values
        self.models_status_var.set(f"Найдено моделей: {len(models)}")
        if models and (not current or current not in models):
            self.model_var.set(models[0])
        self.status_var.set(f"Список моделей обновлён: {len(models)}")
        self.save_settings(silent=True)

    def choose_folder(self):
        selected = filedialog.askdirectory(initialdir=self.output_dir.get() or str(Path.home()))
        if selected:
            self.output_dir.set(selected)

    def get_body(self):
        return self.body.get("1.0", "end-1c")

    def _body_edited(self, _event=None):
        # Once the plain-text editor changes, the previously applied HTML is stale.
        self.current_html = None
        self.html_cid_markers = {}

    def set_body(self, value):
        self.current_html = None
        self.html_cid_markers = {}
        self.body.delete("1.0", "end")
        self.body.insert("1.0", value)

    def update_media_label(self):
        image_names = [Path(path).name for path in self.images.values()]
        attachment_names = [Path(path).name for path in self.attachments]
        self.media_var.set(
            f"Inline images ({len(image_names)}): {', '.join(image_names) or 'none'} | "
            f"Attachments ({len(attachment_names)}): {', '.join(attachment_names) or 'none'}"
        )

    def add_inline_image(self):
        paths = filedialog.askopenfilenames(
            title="Choose inline images",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.webp *.bmp"), ("All files", "*.*")],
        )
        if not paths:
            return
        for path in paths:
            marker = Path(path).name
            # Avoid collisions when different folders contain identically named files.
            if marker in self.images and self.images[marker] != path:
                marker = f"{Path(path).stem}_{uuid.uuid4().hex[:6]}{Path(path).suffix}"
            self.images[marker] = path
            self.body.insert("insert", f"\n[[IMAGE:{marker}]]\n")
        self.update_media_label()

    def add_attachments(self):
        paths = filedialog.askopenfilenames(title="Choose regular attachments")
        for path in paths:
            if path not in self.attachments:
                self.attachments.append(path)
        self.update_media_label()

    def wrap_selection_ai(self):
        try:
            start = self.body.index("sel.first")
            end = self.body.index("sel.last")
            selected = self.body.get(start, end)
            self.body.delete(start, end)
            self.body.insert(start, f"<AI>{selected}</AI>")
        except tk.TclError:
            messagebox.showinfo("Select text", "Select the text you want to mark as AI-generated first.")

    def check_annotations(self):
        value = self.get_body()
        opens = len(re.findall(r"<AI>", value, re.I))
        closes = len(re.findall(r"</AI>", value, re.I))
        if opens != closes:
            messagebox.showwarning("Annotation check", f"Found {opens} opening and {closes} closing AI markers. Check the body before saving.")
        else:
            messagebox.showinfo("Annotation check", f"Found {opens} AI segment opening/closing pairs.")

    def open_html_source(self):
        body = self.get_body()
        image_map = {
            key: {"cid": f"inline-{i}@eml-workbench", "name": Path(path).name}
            for i, (key, path) in enumerate(self.images.items(), 1)
        }
        generated = html_from_annotated_text(body, image_map)
        win = tk.Toplevel(self.root)
        win.title("HTML source — edit and apply")
        cid_to_marker = {
            f"cid:{info['cid']}": key for key, info in image_map.items()
        }
        win.geometry("900x650")
        ttk.Label(win, text="Edit HTML directly. Use <AI>...</AI> around AI-generated HTML/text.").pack(anchor="w", padx=8, pady=5)
        editor = tk.Text(win, wrap="none", undo=True, font=("Consolas", 10))
        editor.pack(fill="both", expand=True, padx=8, pady=5)
        editor.insert("1.0", generated)
        buttons = ttk.Frame(win)
        buttons.pack(fill="x", padx=8, pady=8)

        def apply_html():
            source = editor.get("1.0", "end-1c")
            parser = PlainTextFromHTML()
            parser.image_cid_map = cid_to_marker
            try:
                parser.feed(source)
                segments = parser.result()
                # Preserve labels by rebuilding the annotated plain-text representation.
                rebuilt = []
                for seg in segments:
                    text = seg["text"]
                    rebuilt.append(f"<AI>{text}</AI>" if seg["ai"] else text)
                self.set_body("".join(rebuilt))
                self.current_html = source
                self.html_cid_markers = dict(cid_to_marker)
                win.destroy()
                self.status_var.set("HTML source converted into the annotated text editor.")
            except Exception as exc:
                messagebox.showerror("HTML parsing error", str(exc), parent=win)

        ttk.Button(buttons, text="Apply HTML text to editor", command=apply_html).pack(side="right")
        ttk.Button(buttons, text="Close", command=win.destroy).pack(side="right", padx=5)

    def preview_email(self):
        body = self.get_body()
        image_map = {
            key: {"cid": f"inline-{i}@eml-workbench", "name": Path(path).name}
            for i, (key, path) in enumerate(self.images.items(), 1)
        }
        rendered = self.current_html if self.current_html is not None else html_from_annotated_text(body, image_map)
        # Re-map source CIDs to current local image paths for browser preview.
        for old_cid, key in self.html_cid_markers.items():
            info = image_map.get(key)
            if info and key in self.images:
                rendered = rendered.replace(old_cid, f"cid:{info['cid']}")
        for key, info in image_map.items():
            path = self.images.get(key)
            if path:
                rendered = rendered.replace(f"cid:{info['cid']}", Path(path).resolve().as_uri())
        preview_dir = Path(self.output_dir.get()).expanduser() / ".preview"
        preview_dir.mkdir(parents=True, exist_ok=True)
        preview_file = preview_dir / "preview.html"
        preview_file.write_text(strip_ai_tags(rendered), encoding="utf-8")
        webbrowser.open(preview_file.resolve().as_uri())
        self.status_var.set("Opened HTML preview in your default browser.")

    def client(self):
        try:
            timeout = float(self.timeout_var.get())
            temperature = float(self.temperature_var.get())
            max_tokens = int(self.max_tokens_var.get())
        except ValueError:
            raise ValueError("Timeout, temperature, and max-token settings must be numeric.")
        return OpenWebUIClient(
            self.base_url_var.get().strip(),
            self.api_key_var.get(),
            self.model_var.get().strip(),
            timeout,
        ), temperature, max_tokens

    def set_ai_output(self, value):
        self.ai_output.configure(state="normal")
        self.ai_output.delete("1.0", "end")
        self.ai_output.insert("1.0", value)
        self.ai_output.configure(state="disabled")

    def run_ai_task(self, title, task):
        if self.busy:
            messagebox.showinfo("AI busy", "An AI request is already running.")
            return
        self.busy = True
        self.status_var.set(f"{title}…")

        def worker():
            try:
                result = task()
                self.root.after(0, lambda: self._ai_done(title, result, None))
            except Exception as exc:
                self.root.after(0, lambda err=str(exc): self._ai_done(title, None, err))

        threading.Thread(target=worker, daemon=True).start()

    def _ai_done(self, title, result, error):
        self.busy = False
        if error:
            self.status_var.set("AI request failed.")
            messagebox.showerror("AI error", error)
        else:
            self.status_var.set(f"{title} completed.")
            self.set_ai_output(result)

    def context_messages(self, instruction):
        context = (
            f"Subject: {self.subject_var.get()}\n"
            f"From: {self.from_var.get()}\nTo: {self.to_var.get()}\n"
            f"Current email body:\n{self.get_body()}\n\n"
            f"Task: {instruction}"
        )
        return [
            {"role": "system", "content": "You write realistic, contextually coherent emails. Follow the requested output schema exactly. Do not invent factual claims beyond the supplied context unless asked to create fictional sample content."},
            {"role": "user", "content": context},
        ]

    def generate_snippet(self):
        prompt = self.snippet_prompt.get("1.0", "end-1c").strip()
        if not prompt:
            messagebox.showwarning("Missing instruction", "Describe what the snippet should communicate.")
            return
        try:
            target = int(self.snippet_tokens.get())
            if target < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid token count", "Enter a positive integer token target.")
            return

        kind = self.snippet_type.get()
        style = self.snippet_style.get().strip()
        instruction = (
            f"Write one {kind} for this email. Purpose: {prompt}. Style: {style}. "
            f"Target approximately {target} tokens. Aim close to the target; do not pad with meaningless text. "
            "Return JSON with a single string property named 'text'. Return only the requested snippet, without explanation."
        )

        def task():
            client, temp, _ = self.client()
            raw = client.chat(self.context_messages(instruction), temperature=temp, max_tokens=min(max(target * 2, 128), 8192))
            data = json_from_ai(raw)
            snippet = data.get("text")
            if not isinstance(snippet, str) or not snippet.strip():
                raise ValueError("AI response did not contain a non-empty 'text' string.")
            return snippet.strip()

        def insert_result():
            pass

        def worker_task():
            return task()

        self.run_ai_task("Generating snippet", worker_task)

    def insert_ai_output_as_snippet(self):
        value = self.ai_output.get("1.0", "end-1c").strip()
        if not value:
            return
        # Avoid double-wrapping if a model returned tags despite instructions.
        value = strip_ai_tags(value)
        self.body.insert("insert", f"<AI>{value}</AI>")
        self.tabs.select(self.email_tab)
        self.status_var.set("Inserted generated snippet at the editor cursor.")

    def rewrite_email(self):
        body = self.get_body()
        if not body.strip():
            messagebox.showwarning("Empty email", "Write an email before requesting a rewrite.")
            return
        mode = self.rewrite_mode.get()
        instruction = (
            f"{mode}. Rewrite the complete message body. Preserve its factual meaning, names, dates, "
            "links, and image placeholders such as [[IMAGE:filename]] where possible. "
            "Return JSON with a single string property named 'body'. Do not include commentary."
        )

        def task():
            client, temp, max_tokens = self.client()
            raw = client.chat(self.context_messages(instruction), temperature=temp, max_tokens=max_tokens)
            data = json_from_ai(raw)
            rewritten = data.get("body")
            if not isinstance(rewritten, str) or not rewritten.strip():
                raise ValueError("AI response did not contain a non-empty 'body' string.")
            return rewritten.strip()

        self.run_ai_task("Rewriting email", task)

    def apply_rewrite(self):
        value = self.ai_output.get("1.0", "end-1c").strip()
        if not value:
            return
        if not messagebox.askyesno("Replace email body", "Replace the entire current body with this AI-generated version?"):
            return
        self.set_body(f"<AI>{strip_ai_tags(value)}</AI>")
        self.tabs.select(self.email_tab)
        self.status_var.set("Replaced body; entire rewritten body is marked as AI-generated.")

    def test_connection(self):
        def task():
            client, temp, _ = self.client()
            return client.chat(
                [{"role": "user", "content": "Reply with JSON: {\"status\":\"ok\"}"}],
                temperature=0,
                max_tokens=64,
            )
        self.run_ai_task("Testing Open WebUI connection", task)

    def build_email(self, destination_base=None):
        sender = self.from_var.get().strip()
        to_value = self.to_var.get().strip()
        subject = self.subject_var.get().strip()
        body = self.get_body()

        validate_addresses(sender, "From", True)
        validate_addresses(to_value, "To", True)
        for name, value in (
            ("CC", self.cc_var.get()), ("BCC", self.bcc_var.get()),
            ("Reply-To", self.reply_to_var.get()),
        ):
            validate_addresses(value, name)
        if not subject:
            raise ValueError("Subject is required.")
        if not body.strip():
            raise ValueError("Message body is required.")

        opens = len(re.findall(r"<AI>", body, re.I))
        closes = len(re.findall(r"</AI>", body, re.I))
        if opens != closes:
            raise ValueError(f"Unbalanced AI markers: {opens} opening and {closes} closing.")

        # Image references must resolve before any file is written.
        for match in IMAGE_RE.finditer(body):
            if match.group(1) not in self.images:
                raise ValueError(f"Missing inline image for placeholder: {match.group(1)}")

        output = Path(self.output_dir.get()).expanduser()
        output.mkdir(parents=True, exist_ok=True)

        image_map = {}
        for i, (key, path) in enumerate(self.images.items(), 1):
            image_map[key] = {
                "cid": f"inline-{i}-{uuid.uuid4().hex[:8]}@eml-workbench",
                "name": Path(path).name,
                "path": path,
            }

        if self.current_html is not None:
            html_body = self.current_html
            for old_cid, key in self.html_cid_markers.items():
                info = image_map.get(key)
                if info:
                    html_body = html_body.replace(old_cid, f"cid:{info['cid']}")
        else:
            html_body = html_from_annotated_text(body, image_map)
        segments = split_ai_segments(body)
        # Replace image placeholders in the text labels with readable descriptions.
        for segment in segments:
            segment["text"] = IMAGE_RE.sub(
                lambda m: f"[Image: {Path(self.images[m.group(1)]).name}]", segment["text"]
            )

        msg = EmailMessage(policy=SMTP)
        msg["From"] = sender
        msg["To"] = to_value
        if self.cc_var.get().strip():
            msg["Cc"] = self.cc_var.get().strip()
        # BCC is deliberately omitted from the saved message headers to avoid disclosure.
        if self.reply_to_var.get().strip():
            msg["Reply-To"] = self.reply_to_var.get().strip()
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = self.message_id_var.get().strip() or make_msgid()
        if self.in_reply_to_var.get().strip():
            msg["In-Reply-To"] = self.in_reply_to_var.get().strip()
        if self.references_var.get().strip():
            msg["References"] = self.references_var.get().strip()
        msg["X-Local-Only"] = "true"
        msg["MIME-Version"] = "1.0"

        plain = segments_to_text(segments)
        msg.set_content(plain)
        msg.add_alternative(strip_ai_tags(html_body), subtype="html")
        html_part = msg.get_payload()[-1]

        for key, info in image_map.items():
            path = Path(info["path"])
            data = path.read_bytes()
            mime, _ = mimetypes.guess_type(str(path))
            if not mime or not mime.startswith("image/"):
                raise ValueError(f"Cannot determine a supported image MIME type: {path}")
            maintype, subtype = mime.split("/", 1)
            html_part.add_related(
                data, maintype=maintype, subtype=subtype,
                cid=f"<{info['cid']}>", filename=info["name"], disposition="inline",
            )

        for path_string in self.attachments:
            path = Path(path_string)
            data = path.read_bytes()
            mime, _ = mimetypes.guess_type(str(path))
            maintype, subtype = mime.split("/", 1) if mime else ("application", "octet-stream")
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=path.name)

        safe = safe_filename(subject)
        destination = output / f"{safe}.eml"
        counter = 2
        while destination.exists():
            destination = output / f"{safe}_{counter}.eml"
            counter += 1

        # Manifest contains no API key and no synthetic marker header that reveals AI status.
        manifest = {
            "schema_version": 1,
            "email_file": destination.name,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "label": "ai_inclusive" if any(s["ai"] for s in segments) else "human_only",
            "ai_inclusion": any(s["ai"] for s in segments),
            "segments": segments,
            "counts": {
                "characters": sum(len(s["text"]) for s in segments),
                "ai_characters": sum(len(s["text"]) for s in segments if s["ai"]),
                "human_characters": sum(len(s["text"]) for s in segments if not s["ai"]),
                "segment_count": len(segments),
            },
            "assets": {
                "inline_images": [Path(p).name for p in self.images.values()],
                "attachments": [Path(p).name for p in self.attachments],
            },
            "headers": {
                "subject": subject,
                "from": sender,
                "to": to_value,
                "cc": self.cc_var.get().strip(),
                "bcc_present": bool(self.bcc_var.get().strip()),
            },
        }
        return destination, msg, manifest

    def save_email(self):
        try:
            destination, msg, manifest = self.build_email()
            json_path = destination.with_suffix(".json")
            # Write temp files first, then replace to avoid half-written output pairs.
            eml_tmp = destination.with_suffix(".eml.tmp")
            json_tmp = json_path.with_suffix(".json.tmp")
            eml_tmp.write_bytes(msg.as_bytes())
            json_tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(eml_tmp, destination)
            os.replace(json_tmp, json_path)
            self.last_saved = destination
            self.status_var.set(f"Saved {destination.name} and companion JSON.")
            messagebox.showinfo("Email created", f"Saved locally:\n{destination}\n{json_path}")
        except Exception as exc:
            messagebox.showerror("Could not save email", str(exc))

    def refresh_stats(self):
        segments = split_ai_segments(self.get_body())
        ai_chars = sum(len(s["text"]) for s in segments if s["ai"])
        human_chars = sum(len(s["text"]) for s in segments if not s["ai"])
        ai_words = sum(len(s["text"].split()) for s in segments if s["ai"])
        human_words = sum(len(s["text"].split()) for s in segments if not s["ai"])
        total = ai_chars + human_chars
        pct = (100 * ai_chars / total) if total else 0
        self.stats_var.set(
            f"Segments: {len(segments)} | AI: {ai_chars} chars / ~{ai_words} words | "
            f"Human: {human_chars} chars / ~{human_words} words | AI share: {pct:.1f}%"
        )

    def validate_draft(self):
        try:
            body = self.get_body()
            opens = len(re.findall(r"<AI>", body, re.I))
            closes = len(re.findall(r"</AI>", body, re.I))
            if opens != closes:
                raise ValueError(f"Unbalanced AI tags: {opens} opening, {closes} closing.")
            for match in IMAGE_RE.finditer(body):
                if match.group(1) not in self.images:
                    raise ValueError(f"Unresolved image placeholder: {match.group(1)}")
            validate_addresses(self.from_var.get(), "From", True)
            validate_addresses(self.to_var.get(), "To", True)
            if not self.subject_var.get().strip():
                raise ValueError("Subject is empty.")
            if not body.strip():
                raise ValueError("Body is empty.")
            self.refresh_stats()
            messagebox.showinfo("Validation", "Draft checks passed. This does not guarantee every receiving email client will render identically.")
        except Exception as exc:
            messagebox.showerror("Validation failed", str(exc))

    def open_output_folder(self):
        path = Path(self.output_dir.get()).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(path)
            elif hasattr(os, "startfile"):
                os.startfile(path)
            else:
                import subprocess
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror("Open folder", str(exc))

    def export_manifest(self):
        output = Path(self.output_dir.get()).expanduser()
        files = sorted(output.glob("*.json"))
        rows = []
        for path in files:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                rows.append({
                    "json_file": path.name,
                    "email_file": data.get("email_file"),
                    "label": data.get("label"),
                    "ai_inclusion": data.get("ai_inclusion"),
                    "segments": data.get("counts", {}).get("segment_count"),
                    "ai_characters": data.get("counts", {}).get("ai_characters"),
                    "human_characters": data.get("counts", {}).get("human_characters"),
                })
            except Exception:
                continue
        destination = output / "dataset_manifest.json"
        destination.write_text(json.dumps({
            "schema_version": 1,
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "sample_count": len(rows),
            "samples": rows,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        messagebox.showinfo("Manifest exported", f"Exported {len(rows)} sample records:\n{destination}")

    def generate_batch(self):
        try:
            count = int(self.batch_count.get())
            if not 1 <= count <= 100:
                raise ValueError
        except ValueError:
            messagebox.showerror("Batch size", "Choose a batch size between 1 and 100.")
            return
        topic = self.batch_topic.get().strip()
        if not topic:
            messagebox.showerror("Batch topic", "Enter a topic or scenario.")
            return
        if self.busy:
            messagebox.showinfo("AI busy", "An AI request is already running.")
            return

        self.busy = True
        self.status_var.set(f"Generating batch of {count} emails…")

        def worker():
            created = []
            errors = []
            try:
                client, temp, max_tokens = self.client()
                for index in range(count):
                    prompt = (
                        f"Create one realistic standalone email for this dataset scenario: {topic}. "
                        f"Sample number: {index + 1} of {count}. Vary situation, phrasing, length, and structure. "
                        "Make the entire body AI-generated. Return JSON with string properties 'subject' and 'body'. "
                        "Do not include markdown fences or explanations."
                    )
                    raw = client.chat(
                        [{"role": "system", "content": "Generate plausible, varied synthetic email examples. Do not claim they are real correspondence."},
                         {"role": "user", "content": prompt}],
                        temperature=max(temp, 0.5),
                        max_tokens=max_tokens,
                    )
                    data = json_from_ai(raw)
                    subj, body = data.get("subject"), data.get("body")
                    if not isinstance(subj, str) or not isinstance(body, str) or not body.strip():
                        raise ValueError(f"Sample {index + 1}: response missing subject/body.")
                    created.append((subj.strip(), body.strip()))
                self.root.after(0, lambda: self._save_batch(created, errors))
            except Exception as exc:
                self.root.after(0, lambda err=str(exc): self._batch_failed(err))

        threading.Thread(target=worker, daemon=True).start()

    def _batch_failed(self, error):
        self.busy = False
        self.status_var.set("Batch generation failed.")
        messagebox.showerror("Batch generation", error)

    def _save_batch(self, samples, errors):
        self.busy = False
        output = Path(self.output_dir.get()).expanduser()
        output.mkdir(parents=True, exist_ok=True)
        saved = 0
        for index, (subject, body) in enumerate(samples, 1):
            msg = EmailMessage(policy=SMTP)
            msg["From"] = self.from_var.get().strip() or "synthetic@example.test"
            msg["To"] = self.to_var.get().strip() or "recipient@example.test"
            msg["Subject"] = subject
            msg["Date"] = formatdate(localtime=True)
            msg["Message-ID"] = make_msgid()
            msg["X-Local-Only"] = "true"
            msg.set_content(body)
            msg.add_alternative(
                "<html><body style=\"font-family:Arial,sans-serif;white-space:pre-wrap\">"
                + html.escape(body).replace("\n", "<br>\n") + "</body></html>",
                subtype="html",
            )
            base = safe_filename(f"AI_{index:04d}_{subject}")
            destination = output / f"{base}.eml"
            suffix = 2
            while destination.exists():
                destination = output / f"{base}_{suffix}.eml"
                suffix += 1
            segments = [{"text": body, "ai": True}]
            manifest = {
                "schema_version": 1,
                "email_file": destination.name,
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "label": "ai_only",
                "ai_inclusion": True,
                "segments": segments,
                "counts": {
                    "characters": len(body),
                    "ai_characters": len(body),
                    "human_characters": 0,
                    "segment_count": 1,
                },
                "generation": {
                    "method": "batch_openwebui",
                    "model": self.model_var.get().strip(),
                    "scenario": self.batch_topic.get().strip(),
                    "sample_index": index,
                },
            }
            destination.write_bytes(msg.as_bytes())
            destination.with_suffix(".json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            saved += 1
        self.status_var.set(f"Batch complete: {saved} AI-only emails saved.")
        messagebox.showinfo("Batch complete", f"Created {saved} .eml files and companion JSON labels in:\n{output}")

    def clear_form(self):
        if not messagebox.askyesno("Clear form", "Clear the current email body, headers, images, and attachments?"):
            return
        self.to_var.set("")
        self.cc_var.set("")
        self.bcc_var.set("")
        self.reply_to_var.set("")
        self.subject_var.set("")
        self.message_id_var.set("")
        self.in_reply_to_var.set("")
        self.references_var.set("")
        self.set_body("")
        self.images.clear()
        self.attachments.clear()
        self.update_media_label()
        self.status_var.set("Draft cleared.")

def main():
    root = tk.Tk()
    app = EMLWorkbench(root)
    root.mainloop()


if __name__ == "__main__":
    main()
