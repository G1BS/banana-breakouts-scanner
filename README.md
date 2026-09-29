# banana-breakouts-scanner

Telegram → Cloudflare Worker → GitHub Actions. Send a BananaPatterns
breakout PDF to the bot, get a scored/ranked reply.

## Remaining manual steps
1. Add repo secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (done below via API once you confirm).
2. Deploy `cloudflare-worker/worker.js` in Cloudflare dashboard (Workers → paste code).
3. Set Worker secrets: `TELEGRAM_BOT_TOKEN`, `GITHUB_TOKEN` (PAT, repo+workflow scope), `GITHUB_REPOSITORY=G1BS/banana-breakouts-scanner`.
4. Point Telegram webhook at Worker URL:
   `https://api.telegram.org/bot<TOKEN>/setWebhook?url=<WORKER_URL>`
5. Test: send the PDF to the bot.

## Scoring
Numeric-only (RS, volume, CIR, extension, base freshness, overhead supply, R:R proxy). No news/catalyst check. See `src/scoring.py`.
