"""
Local EML Test Email Builder
- Creates .eml files locally; does not send email.
- Supports HTML body, inline images (CID), and regular attachments.
- Adds an X-Generated-Test-Email header to identify synthetic messages.
Python 3.9+; standard library only.
"""

import mimetypes
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path
from html import escape


class EMLBuilder:
    def __init__(self, root):
        self.root = root
        self.root.title("Local EML Test Email Builder")
        self.root.geometry("850x760")
        self.root.minsize(700, 620)

        self.output_dir = tk.StringVar(value=str(Path.home() / "EML Test Emails"))
        self.from_var = tk.StringVar(value="tester@example.test")
        self.to_var = tk.StringVar()
        self.cc_var = tk.StringVar()
        self.bcc_var = tk.StringVar()
        self.subject_var = tk.StringVar()
        self.images = []
        self.attachments = []

        self._build_ui()

    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        folder_frame = ttk.LabelFrame(outer, text="Save location", padding=8)
        folder_frame.pack(fill="x", pady=(0, 10))
        ttk.Entry(folder_frame, textvariable=self.output_dir).pack(
            side="left", fill="x", expand=True, padx=(0, 8)
        )
        ttk.Button(folder_frame, text="Browse…", command=self.choose_folder).pack(side="right")

        fields = ttk.LabelFrame(outer, text="Email headers", padding=8)
        fields.pack(fill="x", pady=(0, 10))
        rows = [
            ("From *", self.from_var),
            ("To *", self.to_var),
            ("CC", self.cc_var),
            ("BCC", self.bcc_var),
            ("Subject *", self.subject_var),
        ]
        for i, (label, variable) in enumerate(rows):
            ttk.Label(fields, text=label, width=12).grid(row=i, column=0, sticky="w", pady=3)
            ttk.Entry(fields, textvariable=variable).grid(
                row=i, column=1, sticky="ew", pady=3
            )
        fields.columnconfigure(1, weight=1)

        body_frame = ttk.LabelFrame(outer, text="Message body", padding=8)
        body_frame.pack(fill="both", expand=True, pady=(0, 10))
        ttk.Label(
            body_frame,
            text="Write the message as plain text. It will also be converted to a basic HTML body.",
        ).pack(anchor="w", pady=(0, 5))
        self.body = tk.Text(body_frame, wrap="word", height=15, undo=True)
        self.body.pack(fill="both", expand=True)

        media_frame = ttk.LabelFrame(outer, text="Images and attachments", padding=8)
        media_frame.pack(fill="x", pady=(0, 10))

        image_row = ttk.Frame(media_frame)
        image_row.pack(fill="x", pady=3)
        ttk.Button(image_row, text="Add inline image(s)…", command=self.add_images).pack(side="left")
        ttk.Label(image_row, text="Images are embedded in the HTML message body.").pack(
            side="left", padx=10
        )
        self.image_label = ttk.Label(media_frame, text="No inline images selected")
        self.image_label.pack(anchor="w", pady=(0, 5))

        attachment_row = ttk.Frame(media_frame)
        attachment_row.pack(fill="x", pady=3)
        ttk.Button(attachment_row, text="Add attachment(s)…", command=self.add_attachments).pack(
            side="left"
        )
        self.attachment_label = ttk.Label(media_frame, text="No attachments selected")
        self.attachment_label.pack(anchor="w", pady=(0, 2))

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x")
        ttk.Label(
            bottom,
            text="* Required: From, To, Subject, and message body",
            foreground="#555",
        ).pack(side="left")
        ttk.Button(bottom, text="Clear form", command=self.clear_form).pack(side="right", padx=(8, 0))
        ttk.Button(bottom, text="Create .eml", command=self.save_eml).pack(side="right")

    def choose_folder(self):
        selected = filedialog.askdirectory(
            title="Choose output folder",
            initialdir=self.output_dir.get() or str(Path.home()),
            mustexist=False,
        )
        if selected:
            self.output_dir.set(selected)

    def add_images(self):
        paths = filedialog.askopenfilenames(
            title="Choose images to embed",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.gif *.webp *.bmp"),
                ("All files", "*.*"),
            ],
        )
        for path in paths:
            if path not in self.images:
                self.images.append(path)
        self.image_label.config(
            text=f"{len(self.images)} inline image(s): " +
                 (", ".join(Path(p).name for p in self.images) or "none")
        )

    def add_attachments(self):
        paths = filedialog.askopenfilenames(title="Choose attachments")
        for path in paths:
            if path not in self.attachments:
                self.attachments.append(path)
        self.attachment_label.config(
            text=f"{len(self.attachments)} attachment(s): " +
                 (", ".join(Path(p).name for p in self.attachments) or "none")
        )

    @staticmethod
    def valid_address_field(value, field_name):
        # Accept comma-separated addresses, including display-name forms.
        addresses = [part.strip() for part in value.split(",") if part.strip()]
        if not addresses:
            return False
        for address in addresses:
            _, parsed = parseaddr(address)
            if not parsed or "@" not in parsed or parsed.startswith("@") or parsed.endswith("@"):
                messagebox.showerror("Invalid address", f"Please check the {field_name} address:\n{address}")
                return False
        return True

    def save_eml(self):
        sender = self.from_var.get().strip()
        to_value = self.to_var.get().strip()
        subject = self.subject_var.get().strip()
        body_text = self.body.get("1.0", "end-1c").strip()

        missing = []
        if not sender:
            missing.append("From")
        if not to_value:
            missing.append("To")
        if not subject:
            missing.append("Subject")
        if not body_text:
            missing.append("Message body")
        if missing:
            messagebox.showwarning(
                "Required fields missing",
                "Please fill in:\n• " + "\n• ".join(missing),
            )
            return

        if not self.valid_address_field(sender, "From"):
            return
        if not self.valid_address_field(to_value, "To"):
            return
        for name, value in (("CC", self.cc_var.get().strip()), ("BCC", self.bcc_var.get().strip())):
            if value and not self.valid_address_field(value, name):
                return

        output = Path(self.output_dir.get()).expanduser()
        try:
            output.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Folder error", f"Could not create output folder:\n{exc}")
            return

        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = to_value
        if self.cc_var.get().strip():
            msg["Cc"] = self.cc_var.get().strip()
        if self.bcc_var.get().strip():
            # Bcc is kept as a header in this local synthetic test file.
            msg["Bcc"] = self.bcc_var.get().strip()
        msg["Subject"] = subject
        msg["X-Generated-Test-Email"] = "true"
        msg["X-Local-Only"] = "true"

        # Plain-text alternative and a simple escaped HTML alternative.
        msg.set_content(body_text)
        html_parts = [f"<div style='font-family:Arial,sans-serif; white-space:pre-wrap'>{escape(body_text)}</div>"]
        for index, path in enumerate(self.images, start=1):
            cid = f"inline-image-{index}"
            html_parts.append(
                f"<p><img src='cid:{cid}' alt='{escape(Path(path).name)}' "
                f"style='max-width:100%;height:auto'></p>"
            )
        html_body = "<html><body>" + "\n".join(html_parts) + "</body></html>"
        msg.add_alternative(html_body, subtype="html")

        # Attach inline images to the HTML alternative using Content-ID.
        html_part = msg.get_payload()[-1]
        for index, path in enumerate(self.images, start=1):
            try:
                data = Path(path).read_bytes()
                mime, _ = mimetypes.guess_type(path)
                if not mime or not mime.startswith("image/"):
                    messagebox.showerror("Unsupported image", f"Cannot determine an image type for:\n{path}")
                    return
                maintype, subtype = mime.split("/", 1)
                html_part.add_related(
                    data,
                    maintype=maintype,
                    subtype=subtype,
                    cid=f"<inline-image-{index}>",
                    filename=Path(path).name,
                    disposition="inline",
                )
            except OSError as exc:
                messagebox.showerror("Image error", f"Could not read image:\n{path}\n\n{exc}")
                return

        for path in self.attachments:
            try:
                data = Path(path).read_bytes()
                mime, _ = mimetypes.guess_type(path)
                if mime:
                    maintype, subtype = mime.split("/", 1)
                else:
                    maintype, subtype = "application", "octet-stream"
                msg.add_attachment(
                    data,
                    maintype=maintype,
                    subtype=subtype,
                    filename=Path(path).name,
                )
            except OSError as exc:
                messagebox.showerror("Attachment error", f"Could not read attachment:\n{path}\n\n{exc}")
                return

        safe_subject = re.sub(r"[^A-Za-z0-9._-]+", "_", subject).strip("._-")
        safe_subject = (safe_subject[:70] or "test_email")
        destination = output / f"{safe_subject}.eml"
        counter = 2
        while destination.exists():
            destination = output / f"{safe_subject}_{counter}.eml"
            counter += 1

        try:
            with destination.open("wb") as file:
                file.write(msg.as_bytes())
        except OSError as exc:
            messagebox.showerror("Save error", f"Could not save the .eml file:\n{exc}")
            return

        messagebox.showinfo("Email created", f"Saved successfully:\n{destination}")

    def clear_form(self):
        self.to_var.set("")
        self.cc_var.set("")
        self.bcc_var.set("")
        self.subject_var.set("")
        self.body.delete("1.0", "end")
        self.images.clear()
        self.attachments.clear()
        self.image_label.config(text="No inline images selected")
        self.attachment_label.config(text="No attachments selected")


def main():
    root = tk.Tk()
    EMLBuilder(root)
    root.mainloop()


if __name__ == "__main__":
    main()
