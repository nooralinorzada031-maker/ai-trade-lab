# AI Trade Lab — Gold Monitor

A free scheduled monitor for indicative gold prices, OHLC history, EMA20/EMA50, RSI14, ATR14, and optional Telegram notifications. It does not place trades.

## Important limitations

- Uses Yahoo Finance's chart endpoint with ticker `XAUUSD=X`. This endpoint is unofficial and may be delayed, rate-limited, unavailable, or changed without notice.
- Data may differ from your broker's XAUUSD feed. Verify against MT5 before relying on it.
- GitHub scheduled workflows are best-effort, not an exact 24/7 market-data guarantee; jobs may start late. The workflow is set to run every 15 minutes and can also be run manually.
- A public repository means committed market history and code are public. Never put secrets in source files.
- Technical indicators are monitoring data, not financial advice or trade instructions.

## Install into your existing repository

Upload these files to the root of your GitHub repository, preserving paths:

- `.github/workflows/gold-monitor.yml`
- `monitor_gold.py`
- `requirements.txt`
- `data/gold_15m.csv`
- `data/latest_analysis.json`

## Configure Telegram (optional but recommended)

1. In Telegram, open the verified `@BotFather` account, send `/newbot`, and follow its instructions. Copy the bot token privately.
2. Open your new bot and press Start.
3. To get your chat ID, open `https://api.telegram.org/botYOUR_TOKEN/getUpdates` in a browser after sending a message to the bot. Replace `YOUR_TOKEN` privately. Find `message.chat.id` in the response. Do not share the URL or token publicly. If getUpdates is empty, send another message and refresh.
4. In GitHub, open repository **Settings → Secrets and variables → Actions → New repository secret**.
5. Create `TELEGRAM_BOT_TOKEN` with the bot token, and `TELEGRAM_CHAT_ID` with the chat ID.

## Enable and test

1. Open **Settings → Actions → General** and confirm Actions are enabled.
2. Under **Workflow permissions**, the workflow declares `contents: write`; this allows it to commit history updates. If repository policy blocks this, enable read/write workflow permissions.
3. Open the **Actions** tab → **AI Trade Lab Gold Monitor** → **Run workflow**.
4. Open the run and inspect the `Fetch gold data and calculate indicators` log.
5. If successful, `data/gold_15m.csv` and `data/latest_analysis.json` will update in the repository. If Telegram secrets are configured, a message is sent when a new candle is detected.

## Telegram setup privacy

The bot token is a password. Do not put it in a README, issue, commit, or screenshot. If it leaks, revoke it in BotFather and create a new one.
