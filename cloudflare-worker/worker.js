/**
 * Relays a Telegram webhook (document upload) into a GitHub Actions
 * workflow_dispatch call. Holds no scoring/parsing logic itself — that
 * all lives in the repo, in src/run.py.
 *
 * Required Worker secrets (set in the Cloudflare dashboard, not here):
 *   TELEGRAM_BOT_TOKEN
 *   GITHUB_TOKEN          — PAT with repo + workflow scopes
 *   GITHUB_REPOSITORY     — e.g. "G1BS/banana-breakouts-scanner"
 *
 * Point Telegram's webhook at this Worker's URL after deploying:
 *   https://api.telegram.org/bot<TOKEN>/setWebhook?url=<WORKER_URL>
 */

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("OK", { status: 200 });
    }

    let update;
    try {
      update = await request.json();
    } catch (e) {
      return new Response("Bad request", { status: 400 });
    }

    const message = update.message;
    if (!message) {
      return new Response("OK", { status: 200 }); // ignore non-message updates
    }

    const chatId = message.chat && message.chat.id;
    const doc = message.document;

    // Handle /start or /help with a quick reply, no GitHub trigger needed
    if (message.text && ["/start", "/help"].includes(message.text.trim().toLowerCase())) {
      await sendTelegramMessage(env, chatId, "Send me a BananaPatterns breakout-screen PDF and I'll score and rank every stock in it.");
      return new Response("OK", { status: 200 });
    }

    if (!doc || !doc.file_name || !doc.file_name.toLowerCase().endsWith(".pdf")) {
      if (chatId) {
        await sendTelegramMessage(env, chatId, "Send the breakout screen as a PDF file (not a photo).");
      }
      return new Response("OK", { status: 200 });
    }

    const [owner, repo] = env.GITHUB_REPOSITORY.split("/");
    const dispatchResp = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/actions/workflows/score.yml/dispatches`,
      {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
          "Accept": "application/vnd.github+json",
          "User-Agent": "banana-breakouts-scanner-worker",
        },
        body: JSON.stringify({
          ref: "main",
          inputs: {
            file_id: doc.file_id,
            chat_id: String(chatId),
          },
        }),
      }
    );

    if (!dispatchResp.ok) {
      const errText = await dispatchResp.text();
      console.log("GitHub dispatch failed:", dispatchResp.status, errText);
      if (chatId) {
        await sendTelegramMessage(env, chatId, "Couldn't start the scoring run — check the Worker logs.");
      }
    } else {
      if (chatId) {
        await sendTelegramMessage(env, chatId, "Got it — scoring now, reply coming shortly.");
      }
    }

    return new Response("OK", { status: 200 });
  },
};

async function sendTelegramMessage(env, chatId, text) {
  await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text }),
  });
}
