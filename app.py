"""
notify-bridge: Apprise-compatible HTTP endpoint -> Resend API email bridge

Compatible with changedetection.io Apprise notifications via json:// schema.
"""

import logging
import os
import secrets
from urllib.parse import unquote

import httpx
from flask import Flask, abort, jsonify, request

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# Configuration from environment
BRIDGE_TOKEN = os.environ["BRIDGE_TOKEN"]
BRIDGE_PORT = int(os.environ.get("BRIDGE_PORT", "5001"))
RESEND_API_KEY = os.environ["RESEND_API_KEY"]
MAIL_FROM = os.environ["MAIL_FROM"]
MAIL_FROM_NAME = os.environ.get("MAIL_FROM_NAME", "ChangeDetection")
MAIL_TO = os.environ["MAIL_TO"]

RESEND_API_URL = "https://api.resend.com/emails"

# Cloudflare is in front of Resend, so use a realistic User-Agent
HTTP_HEADERS = {
    "Authorization": f"Bearer {RESEND_API_KEY}",
    "Content-Type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

# HTTP client with reasonable timeouts
_client = httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0))


def _get_recipients() -> list[str]:
    """Return the recipient list parsed from MAIL_TO."""
    return [recipient.strip() for recipient in MAIL_TO.split(",") if recipient.strip()]


def _send_via_resend(subject: str, body_html: str, body_text: str) -> None:
    """Send the email through Resend."""
    recipients = _get_recipients()
    from_field = f"{MAIL_FROM_NAME} <{MAIL_FROM}>"

    payload: dict = {
        "from": from_field,
        "to": recipients,
        "subject": subject,
    }

    if body_html:
        payload["html"] = body_html

    if body_text:
        payload["text"] = body_text

    if not body_html and not body_text:
        raise ValueError("Both body_html and body_text are empty")

    log.info("Sending email via Resend to %s (subject: %r)", recipients, subject)

    response = _client.post(RESEND_API_URL, json=payload, headers=HTTP_HEADERS)

    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"Resend API error {response.status_code}: {response.text}"
        )

    log.info("Email sent successfully (Resend id: %s)", response.json().get("id"))


def _verify_token(token_from_url: str) -> bool:
    """Use constant-time comparison after normalizing URL encoding."""
    normalized_url_token = unquote(token_from_url).strip()
    normalized_env_token = unquote(BRIDGE_TOKEN).strip()
    return secrets.compare_digest(normalized_url_token, normalized_env_token)


def _extract_message_content(data: dict) -> tuple[str, str, str]:
    """
    Extract title, HTML body and plain text body from an Apprise-like payload.

    Supported payload fields:
    - title
    - body
    - message
    - body_text
    - text
    """
    title = data.get("title", "ChangeDetection notification")

    raw_body = (
        data.get("body")
        or data.get("message")
        or ""
    )

    body_text = (
        data.get("body_text")
        or data.get("text")
        or ""
    )

    is_html = "<" in raw_body and ">" in raw_body
    body_html = raw_body if is_html else ""

    if not body_text and not is_html:
        body_text = raw_body

    return title, body_html, body_text


def _handle_notification(token: str):
    """Shared handler for both supported endpoint shapes."""
    if not _verify_token(token):
        log.warning("Rejected request with invalid token from %s", request.remote_addr)
        abort(403)

    data = request.get_json(silent=True) or {}
    log.info("Received notification payload keys: %s", sorted(data.keys()))
    log.debug("Received payload: %s", data)

    title, body_html, body_text = _extract_message_content(data)

    try:
        _send_via_resend(
            subject=title,
            body_html=body_html,
            body_text=body_text,
        )
        return jsonify({"status": "ok"}), 200
    except Exception as exc:
        log.error("Failed to send email: %s", exc, exc_info=True)
        return jsonify({"status": "error", "detail": str(exc)}), 500


# Support both:
# - /notify/<token>
# - /<token>
#
# This makes the bridge compatible with different json:// path translations.
@app.route("/notify/<token>", methods=["POST"])
@app.route("/<token>", methods=["POST"])
def notify(token: str):
    return _handle_notification(token)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=BRIDGE_PORT)
