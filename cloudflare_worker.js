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
      const botToken = env.TELEGRAM_BOT_TOKEN || env.BOT_TOKEN;
      const allowedChatId = env.TELEGRAM_CHAT_ID || env.CHAT_ID;
      const githubToken = env.GITHUB_PAT || env.GITHUB_TOKEN;
      const githubRepo = env.GITHUB_REPO || "feriwidiyanto25-svg/trading-bot";

      // 1. Tangani Klik Tombol Interaktif (Inline Button)
      if (update.callback_query) {
        const cb = update.callback_query;
        const chatId = cb.from.id.toString();
        const data = cb.data || "scan_4h";

        // Keamanan: Cek apakah pengirim adalah pemilik bot
        if (allowedChatId && chatId !== allowedChatId) {
          return new Response("Unauthorized", { status: 200 });
        }

        let mode = "trend";
        let timeframe = "4h";
        let notifText = "";
        let chatText = "";

        if (data === "pump_15m") {
          mode = "pump";
          timeframe = "15m";
          notifText = "Memulai Radar Pre-Pump 15m... Mohon tunggu ~25 detik.";
          chatText = "🚀 *Permintaan Radar Pre-Pump Diterima!*\nSedang memindai anomali akumulasi Paus & Pre-Pump (*Timeframe 15m*)...\nLaporan akan langsung dikirim ke sini sebentar lagi.";
        } else if (data === "scan_15m" || data === "15m") {
          timeframe = "15m";
          notifText = "Memulai scan Trend 15m... Mohon tunggu ~25 detik.";
          chatText = "⚡ *Permintaan Diterima!*\nSedang memindai pasar (*Trend Konservatif 15 Menit*)...\nLaporan akan langsung dikirim ke sini sebentar lagi.";
        } else if (data === "scan_1h" || data === "1h") {
          timeframe = "1h";
          notifText = "Memulai scan Trend 1h... Mohon tunggu ~25 detik.";
          chatText = "⏱️ *Permintaan Diterima!*\nSedang memindai pasar (*Trend Konservatif 1 Jam*)...\nLaporan akan langsung dikirim ke sini sebentar lagi.";
        } else {
          timeframe = "4h";
          notifText = "Memulai scan Trend 4h... Mohon tunggu ~25 detik.";
          chatText = "🛡️ *Permintaan Diterima!*\nSedang memindai pasar (*Trend Konservatif 4 Jam*)...\nLaporan akan langsung dikirim ke sini sebentar lagi.";
        }

        // A. Notifikasi pop-up kecil di Telegram
        await fetch(`https://api.telegram.org/bot${botToken}/answerCallbackQuery`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            callback_query_id: cb.id,
            text: notifText
          })
        });

        // B. Kirim pesan konfirmasi di chat
        await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: chatId,
            text: chatText,
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
            inputs: {
              timeframe: timeframe,
              mode: mode
            }
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

      // 2. Tangani Pesan Teks (/menu, /pump, /scan, /cek)
      if (update.message && update.message.text) {
        const chatId = update.message.chat.id.toString();

        if (allowedChatId && chatId !== allowedChatId) {
          return new Response("Unauthorized", { status: 200 });
        }

        const text = update.message.text.trim().toLowerCase();

        // A. Perintah Radar Pre-Pump: /pump, /prepump, /hunt
        if (text.startsWith("/pump") || text.startsWith("/prepump") || text.startsWith("/hunt")) {
          await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              chat_id: chatId,
              text: "🚀 *Memulai Radar Pre-Pump (Whale Hunter)...*\n_Memindai anomali volume & akumulasi Paus multi-hari (15m). Laporan akan dikirim ~25 detik lagi._",
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
                timeframe: "15m",
                mode: "pump"
              }
            })
          });

          return new Response("OK", { status: 200 });
        }

        // B. Perintah Scan Trend Pasar: /scan [15m|1h|4h]
        if (text.startsWith("/scan")) {
          const parts = text.split(/\s+/);
          const tf = (parts.length > 1 && ["15m", "1h", "4h"].includes(parts[1])) ? parts[1] : "4h";

          await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              chat_id: chatId,
              text: `🛡️ *Memulai Scan Trend Konservatif (${tf})...*\nLaporan lengkap akan dikirim ~25 detik lagi.`,
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
                timeframe: tf,
                mode: "trend"
              }
            })
          });

          return new Response("OK", { status: 200 });
        }

        // C. Perintah Cek 1 Koin Spesifik: /cek <koin> [timeframe]
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
                  symbol: targetSym,
                  mode: "trend"
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
                text: "💡 *Format salah!*\nGunakan: `/cek <koin> [timeframe]`\nContoh: `/cek SSV 15m` atau `/cek OM 1h`",
                parse_mode: "Markdown"
              })
            });
            return new Response("OK", { status: 200 });
          }
        }

        // D. Perintah Menu / Start
        if (text === "/menu" || text === "/start" || text === "menu" || text === "/help") {
          await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              chat_id: chatId,
              text: (
                "🤖 *[RADAR CRYPTO & INTELIJEN PAUS]*\n\n" +
                "Silakan pilih *Mode Analisis* yang Anda inginkan:\n\n" +
                "🚀 *Mode 2: Radar Pre-Pump (15m)*\n" +
                "• Memburu koin tidur yang diakumulasi Paus & siap meledak (mengabaikan BTC).\n" +
                "• Rekomendasi titik Trigger Buy Stop.\n\n" +
                "🛡️ *Mode 1: Trend Konservatif (15m, 1h, 4h)*\n" +
                "• Mengikuti rezim makro Bitcoin & proteksi modal ketat.\n\n" +
                "💡 *Cek 1 Koin Tertentu:*\n" +
                "Ketik: `/cek <koin> [timeframe]` (Contoh: `/cek SSV 15m` atau `/cek OM 1h`)\n\n" +
                "👇 *Atau klik salah satu tombol di bawah untuk scan seluruh pasar:* "
              ),
              parse_mode: "Markdown",
              reply_markup: {
                inline_keyboard: [
                  [
                    { text: "🚀 Radar Pre-Pump (15m)", callback_data: "pump_15m" },
                    { text: "🛡️ Trend Aman (4 Jam)", callback_data: "scan_4h" }
                  ],
                  [
                    { text: "⚡ Trend Cepat (15 Menit)", callback_data: "scan_15m" },
                    { text: "⏱️ Trend Intraday (1 Jam)", callback_data: "scan_1h" }
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
