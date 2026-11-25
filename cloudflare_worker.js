/**
 * Cloudflare Worker: Telegram Webhook -> GitHub Actions Dispatch
 * 100% Serverless, Gratis, dan Aktif Hanya Saat Tombol Ditekan di Telegram.
 */

export default {
  async fetch(request, env) {
    // Hanya proses request POST dari Telegram
    if (request.method !== "POST") {
      return new Response("Bot Webhook is running!", { status: 200 });
    }

    try {
      const update = await request.json();
      const botToken = env.TELEGRAM_BOT_TOKEN;
      const allowedChatId = env.TELEGRAM_CHAT_ID;
      const githubToken = env.GITHUB_PAT; // Personal Access Token (PAT)
      const githubRepo = env.GITHUB_REPO || "feriwidiyanto25-svg/trading-bot";

      // 1. Tangani Klik Tombol Interaktif (Inline Button)
      if (update.callback_query) {
        const cb = update.callback_query;
        const chatId = cb.from.id.toString();
        const timeframe = cb.data; // "15m", "1h", atau "4h"

        // Keamanan: Cek apakah pengirim adalah pemilik bot
        if (allowedChatId && chatId !== allowedChatId) {
          return new Response("Unauthorized", { status: 200 });
        }

        // A. Notifikasi pop-up kecil di Telegram
        await fetch(`https://api.telegram.org/bot${botToken}/answerCallbackQuery`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            callback_query_id: cb.id,
            text: `Memulai scan ${timeframe}... Mohon tunggu ~25 detik.`
          })
        });

        // B. Kirim pesan konfirmasi di chat
        await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: chatId,
            text: `⏳ *Permintaan Diterima!*\nSedang memindai pasar (*Timeframe ${timeframe}*)...\nLaporan akan langsung dikirim ke sini sebentar lagi.`,
            parse_mode: "Markdown"
          })
        });

        // C. Bangunkan GitHub Actions untuk menjalankan pemindaian
        const ghRes = await fetch(`https://api.github.com/repos/${githubRepo}/actions/workflows/screener.yml/dispatches`, {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${githubToken}`,
            "Accept": "application/vnd.github+json",
            "User-Agent": "Cloudflare-Worker-Crypto-Bot"
          },
          body: JSON.stringify({
            ref: "main",
            inputs: { timeframe: timeframe }
          })
        });

        if (!ghRes.ok) {
          const errText = await ghRes.text();
          await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              chat_id: chatId,
              text: `⚠️ *Gagal memicu GitHub Actions:* \`${errText}\``,
              parse_mode: "Markdown"
            })
          });
        }

        return new Response("OK", { status: 200 });
      }

      // 2. Tangani Pesan Teks (/menu, /start)
      if (update.message && update.message.text) {
        const chatId = update.message.chat.id.toString();

        if (allowedChatId && chatId !== allowedChatId) {
          return new Response("Unauthorized", { status: 200 });
        }

        const text = update.message.text.trim().toLowerCase();

        // A. Perintah Cek 1 Koin Spesifik: /cek <koin> [timeframe]
        if (text.startsWith("/cek") || text.startsWith("/analisa") || text.startsWith("/check")) {
          const parts = update.message.text.trim().split(/\s+/);
          if (parts.length > 1) {
            let targetSym = parts[1].toUpperCase();
            if (targetSym.endsWith("USDT")) {
              targetSym = targetSym.replace("USDT", "");
            }
            const targetTf = (parts.length > 2 && ["15m", "1h", "4h"].includes(parts[2].toLowerCase())) ? parts[2].toLowerCase() : "15m";

            await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                chat_id: chatId,
                text: `🔍 *Memulai Analisis ${targetSym}USDT (Timeframe ${targetTf})...*\nLaporan lengkap akan langsung dikirim ke sini sebentar lagi.`,
                parse_mode: "Markdown"
              })
            });

            await fetch(`https://api.github.com/repos/${githubRepo}/actions/workflows/screener.yml/dispatches`, {
              method: "POST",
              headers: {
                "Authorization": `Bearer ${githubToken}`,
                "Accept": "application/vnd.github+json",
                "User-Agent": "Cloudflare-Worker-Crypto-Bot"
              },
              body: JSON.stringify({
                ref: "main",
                inputs: {
                  timeframe: targetTf,
                  symbol: targetSym
                }
              })
            });

            return new Response("OK", { status: 200 });
          } else {
            await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                chat_id: chatId,
                text: "💡 *Format salah!*\nGunakan: `/cek <koin> [timeframe]`\nContoh: `/cek DOS 15m` atau `/cek BTC 1h`",
                parse_mode: "Markdown"
              })
            });
            return new Response("OK", { status: 200 });
          }
        }

        // B. Perintah Menu / Start
        if (text === "/menu" || text === "/start" || text === "menu" || text === "/help") {
          await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              chat_id: chatId,
              text: (
                "🤖 *[RADAR CRYPTO & INTELIJEN PAUS]*\n\n" +
                "Pilih timeframe trading yang ingin Anda pantau:\n" +
                "• *15 Menit (15m)*: Trading kilat selesai 1–3 jam\n" +
                "• *1 Jam (1h)*: Intraday selesai 3–8 jam\n" +
                "• *4 Jam (4h)*: Swing tenang selesai 1–2 hari\n\n" +
                "💡 *Cek 1 Koin Tertentu:*\n" +
                "Ketik: `/cek <koin> [timeframe]` (Contoh: `/cek DOS 15m`)\n\n" +
                "👇 *Atau klik salah satu tombol di bawah untuk scan seluruh pasar:* "
              ),
              parse_mode: "Markdown",
              reply_markup: {
                inline_keyboard: [
                  [
                    { text: "⚡ Scan 15 Menit (15m)", callback_data: "15m" },
                    { text: "⏱️ Scan 1 Jam (1h)", callback_data: "1h" }
                  ],
                  [
                    { text: "📊 Scan Swing 4 Jam (4h)", callback_data: "4h" }
                  ]
                ]
              }
            })
          });
        }
      }

      return new Response("OK", { status: 200 });
    } catch (e) {
      return new Response("Error: " + e.message, { status: 200 });
    }
  }
};
