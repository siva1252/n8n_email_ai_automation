from __future__ import annotations

import re
from datetime import datetime
from email.utils import parseaddr
from html import unescape
from typing import Any


URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
TAG_RE = re.compile(r"<[^>]+>")


def html_to_text(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"(?i)<br\s*/?>", "\n", html)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = TAG_RE.sub(" ", text)
    return unescape(re.sub(r"\s+", " ", text)).strip()


def extract_email(value: str) -> str:
    if isinstance(value, dict):
        value = value.get("address") or value.get("email") or value.get("text") or value.get("value") or ""
    _, addr = parseaddr(str(value or ""))
    return (addr or str(value or "")).strip()


def extract_urls(text: str) -> list[str]:
    return list(dict.fromkeys(URL_RE.findall(text or "")))


def parse_iso_datetime(value: Any):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def normalize_gmail_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize n8n Gmail Trigger / message resource into a stable ingest dict."""
    if not isinstance(data, dict):
        return {
            "gmail_message_id": None,
            "thread_id": "",
            "subject": "(no subject)",
            "body": "",
            "body_text": "",
            "body_html": "",
            "from_email": "",
            "to_email": "",
            "reply_to": "",
            "headers": {},
            "labels": [],
            "attachments": [],
            "urls": [],
            "direction": "INCOMING",
            "brand_name": "",
            "sent_at": None,
            "received_at": None,
            "idempotency_key": "",
            "skip_ai": False,
            "correlation_id": "",
        }
    nested = data.get("body")
    if isinstance(nested, dict) and not data.get("thread_id") and not data.get("threadId"):
        merged = {**data, **nested}
        data = merged
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
    headers_list = payload.get("headers") or data.get("headers") or []
    headers = {}
    if isinstance(headers_list, list):
        for item in headers_list:
            if isinstance(item, dict) and item.get("name"):
                headers[item["name"]] = item.get("value") or ""
    elif isinstance(headers_list, dict):
        headers = {str(k): str(v) for k, v in headers_list.items()}

    def header(*names: str) -> str:
        lower = {k.lower(): v for k, v in headers.items()}
        for name in names:
            if name.lower() in lower:
                return lower[name.lower()]
        return ""

    body_text = data.get("body_text") or data.get("textPlain") or data.get("text") or data.get("body") or ""
    body_html = data.get("body_html") or data.get("textHtml") or data.get("html") or ""
    if not body_text and body_html:
        body_text = html_to_text(body_html)

    attachments = data.get("attachments") or data.get("attachment_metadata") or []
    if isinstance(attachments, dict):
        attachments = [attachments]
    attachment_meta = []
    for item in attachments:
        if isinstance(item, str):
            attachment_meta.append({"filename": item})
        elif isinstance(item, dict):
            attachment_meta.append(
                {
                    "filename": item.get("filename") or item.get("name") or "",
                    "mimeType": item.get("mimeType") or item.get("mime_type") or "",
                    "size": item.get("size"),
                    "attachmentId": item.get("attachmentId") or item.get("id"),
                }
            )

    labels = data.get("labels") or data.get("labelIds") or []
    if isinstance(labels, str):
        labels = [labels]
    clean_labels = []
    for item in labels:
        if isinstance(item, dict):
            clean_labels.append(str(item.get("id") or item.get("name") or ""))
        else:
            clean_labels.append(str(item))
    labels = [x for x in clean_labels if x]

    from_email = extract_email(data.get("from_email") or data.get("from") or header("From"))
    to_email = extract_email(data.get("to_email") or data.get("to") or header("To"))
    reply_to = extract_email(data.get("reply_to") or header("Reply-To"))
    subject = data.get("subject") or header("Subject") or "(no subject)"
    thread_id = data.get("thread_id") or data.get("threadId") or ""
    message_id = data.get("gmail_message_id") or data.get("id") or data.get("messageId") or header("Message-ID")
    urls = data.get("urls") or extract_urls(f"{body_text}\n{body_html}")

    return {
        "gmail_message_id": str(message_id or "").strip() or None,
        "thread_id": str(thread_id or "").strip(),
        "subject": subject,
        "body": body_text,
        "body_text": body_text,
        "body_html": body_html,
        "from_email": from_email,
        "to_email": to_email,
        "reply_to": reply_to,
        "headers": headers,
        "labels": list(labels),
        "attachments": attachment_meta,
        "urls": urls,
        "direction": (data.get("direction") or "INCOMING").upper(),
        "brand_name": data.get("brand_name") or "",
        "sent_at": parse_iso_datetime(data.get("sent_at") or data.get("internalDate") or header("Date")),
        "received_at": parse_iso_datetime(data.get("received_at") or data.get("internalDate")),
        "idempotency_key": data.get("idempotency_key") or "",
        "skip_ai": bool(data.get("skip_ai")),
        "correlation_id": data.get("correlation_id") or thread_id or "",
    }
