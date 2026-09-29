"""
Entry point triggered by the GitHub Actions workflow (workflow_dispatch),
which itself is triggered by the Cloudflare Worker relaying a Telegram
document upload.

Env vars (set by the workflow from workflow_dispatch inputs):
  TG_FILE_ID   — Telegram file_id of the uploaded PDF
  TG_CHAT_ID   — Telegram chat to reply to
Env var (repo secret):
  TELEGRAM_BOT_TOKEN
"""
import os
import sys
import csv
import datetime
import requests

sys.path.insert(0, os.path.dirname(__file__))
from parse_pdf import parse_pdf
from scoring import rank_stocks
from notify_telegram import send_message, format_report

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
TMP_DIR = "/tmp/bbs"
HISTORY_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "history.csv")


def download_file(file_id, dest_path):
    resp = requests.get(f"{API}/getFile", params={"file_id": file_id})
    resp.raise_for_status()
    file_path = resp.json()["result"]["file_path"]
    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
    r = requests.get(file_url)
    r.raise_for_status()
    with open(dest_path, "wb") as f:
        f.write(r.content)


def log_history(ranked):
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    is_new = not os.path.exists(HISTORY_PATH)
    ts = datetime.datetime.utcnow().isoformat()
    with open(HISTORY_PATH, "a", newline="") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(["timestamp_utc", "name", "score", "rs_rating", "breakout_volume", "vs_pivot_pct", "status"])
        for s in ranked:
            w.writerow([ts, s["name"], s["score"], s.get("rs_rating"), s.get("breakout_volume"), s.get("vs_pivot_pct"), s.get("status")])


def main():
    file_id = os.environ["TG_FILE_ID"]
    chat_id = os.environ["TG_CHAT_ID"]

    os.makedirs(TMP_DIR, exist_ok=True)
    local_path = os.path.join(TMP_DIR, "incoming.pdf")

    try:
        download_file(file_id, local_path)
        stocks = parse_pdf(local_path)
        if not stocks:
            send_message(chat_id, "Couldn't find any stock cards in that PDF — check the format matches a BananaPatterns breakout export.")
            return
        ranked = rank_stocks(stocks)
        send_message(chat_id, format_report(ranked))
        log_history(ranked)
    except Exception as e:
        send_message(chat_id, f"Error processing PDF: {e}")
        raise


if __name__ == "__main__":
    main()
