"""Formats and sends the ranked breakout report to a Telegram chat."""
import os
import requests

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(chat_id, text):
    for i in range(0, len(text), 4000):
        resp = requests.post(
            f"{API}/sendMessage",
            data={"chat_id": chat_id, "text": text[i:i + 4000], "parse_mode": "HTML"},
        )
        resp.raise_for_status()


def format_report(ranked):
    from scoring import verdict

    lines = ["<b>Swing Trade Screen — Ranked</b>\n"]
    for i, s in enumerate(ranked, 1):
        v = verdict(s["score"])
        pivot_pct = s.get("vs_pivot_pct")
        pivot_txt = f"{pivot_pct:+.1f}% vs pivot" if pivot_pct is not None else "pivot n/a"
        status = s.get("status") or ""
        lines.append(
            f"{i}. <b>{s['name']}</b> — {s['score']}/100 [{v}] {status}\n"
            f"   RS {s.get('rs_rating', '?')} | Vol {s.get('breakout_volume', '?')}x | "
            f"{pivot_txt}"
        )
    lines.append(
        "\n<i>Numeric screen only — no news/catalyst check. "
        "Check market regime (Nifty trend/breadth) separately before sizing.</i>"
    )
    return "\n".join(lines)
