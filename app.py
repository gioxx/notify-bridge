"""
notify-bridge: Apprise-compatible HTTP endpoint → Resend API email bridge
Compatible with changedetection.io's Apprise notification via json:// schema
"""

import os
import logging
import secrets
import httpx
from flask import Flask, request, jsonify, abort

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ── Config from environment ──────────────────────────────────────────────────
BRIDGE_TOKEN   = os.environ["BRIDGE_TOKEN"]         # required, no default
BRIDGE_PORT    = int(os.environ.get("BRIDGE_PORT", "5001"))  # default 5001 to avoid conflict with changedetection
RESEND_API_KEY = os.environ["RESEND_API_KEY"]        # re_xxxxxxxxxxxx
MAIL_FROM      = os.environ["MAIL_FROM"]             # must be a Resend-verified domain address
MAIL_FROM_NAME = os.environ.get("MAIL_FROM_NAME", "ChangeDetection")
MAIL_TO        = os.environ["MAIL_TO"]               # comma-separated recipients

RESEND_API_URL = "https://api.resend.com/emails"

# Cloudflare is in front of Resend — use a realistic User-Agent
HTTP_HEADERS = {
    "Authorization": f"Bearer {RESEND_API_KEY}",
    "Content-Type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

# httpx client with reasonable timeouts (connect 5s, read 15s)
_client = httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0))


def _get_recipients() -> list[str]:
    return [r.strip() for r in MAIL_TO.split(",") if r.strip()]


def _send_via_resend(subject: str, body_html: str, body_text: str) -> None:
    recipients = _get_recipients()
    from_field = f"{MAIL_FROM_NAME} <{MAIL_FROM}>"

    payload: dict = {
        "from":    from_field,
        "to":      recipients,
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
    """Constant-time comparison to prevent timing attacks."""
    return secrets.compare_digest(token_from_url, BRIDGE_TOKEN)


# ── Apprise json:// compatible endpoint ─────────────────────────────────────
#
# changedetection.io calls Apprise with:
#   json://notify-bridge:5001/<TOKEN>
# which Apprise translates to POST /notify/<TOKEN>
#
# Apprise json:// payload:
# {
#   "title": "...",
#   "body":  "...",     # may be HTML
#   "type":  "info|warning|failure|success"
# }
#
@app.route("/notify/<token>", methods=["POST"])
def notify(token: str):
    if not _verify_token(token):
        log.warning("Rejected request with invalid token from %s", request.remote_addr)
        abort(403)

    data = request.get_json(silent=True) or {}
    log.debug("Received payload: %s", data)

    title     = data.get("title", "ChangeDetection notification")
    body      = data.get("body", "")
    body_text = data.get("body_text", "")   # optional plain-text fallback

    # Detect HTML body
    is_html = "<" in body and ">" in body
    body_html = body if is_html else ""
    if not body_text and not is_html:
        body_text = body

    try:
        _send_via_resend(subject=title, body_html=body_html, body_text=body_text)
        return jsonify({"status": "ok"}), 200
    except Exception as exc:
        log.error("Failed to send email: %s", exc, exc_info=True)
        return jsonify({"status": "error", "detail": str(exc)}), 500


# ── Health check ─────────────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=BRIDGE_PORT)
