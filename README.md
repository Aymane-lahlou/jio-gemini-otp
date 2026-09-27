<div align="center">

# jio-gemini-otp

**Auto get Jio Gemini link via Grizzly SMS — stock waiter, OTP poller, link extractor.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Requests](https://img.shields.io/badge/requests-only-green)](https://pypi.org/project/requests/)
[![Grizzly Docs](https://img.shields.io/badge/docs-grizzlysms-orange)](https://grizzlysms.com/docs)
[![No dotenv needed](https://img.shields.io/badge/.env-builtin-lightgrey)](#setup)

`getNumber` → `check/sendOtp` → `getStatus` poll → `verify` → `serviceactivation.google.com` link

</div>

## ✨ Features

| Feature | Details |
|---|---|
| 🧭 3 modes | Manual / Grizzly AUTO / Grizzly OTP-only |
| ⏳ Stock waiter | `NO_NUMBERS` → poll `getNumber` + `getNumberV2` |
| 🔁 Auto-retry | New number on `NOT_SUBSCRIBED_USER` |
| 💰 Price tiers | `maxPrice`: `0.10` / `0.15` / `0.208` |
| 🔑 Safe keys | `.env` loader built-in, `.env` git-ignored |

## 📦 Requirements

- Python `3.10+`
- `pip install requests` (only dependency)

## 🚀 Setup

```bash
cp .env.example .env
```

Then paste your key in `.env`:

```env
GRIZZLY_API_KEY=xxx
```

> Confirmed codes: service `jio` (= MyJio), country `22` (= India).

## ▶️ Usage

```bash
python jio.py
```

| Mode | Use when | Flow |
|---|---|---|
| `1` Manual | You have SIM | Paste number → paste OTP → link |
| `2` Grizzly AUTO ⭐ | Hands-free | API number → Jio OTP → auto-poll → link |
| `3` OTP only | Bought on site | Paste number + ID → auto-poll → link |

Mode `2` asks for:

```text
service  [jio]        → jio = MyJio, ot = AnyOther workaround
country  [22]         → 22 = India (Jio needs +91)
maxPrice [cheapest]   → 0.208 allows all tiers
numbers  [0=infinite] → how many numbers to try
wait     [30m]        → stock wait, 0 = infinite
retry    [15s]        → poll interval
```

✅ Link saved to `gemini_activation_link.txt`.

## 💰 Price tiers (`jio/22`)

| Tier | Qty (example) | Notes |
|---|---|---|
| `$0.10` | ~128k | Cheapest, lowest Jio hit-rate |
| `$0.15` | ~16k | Middle |
| `$0.208` | ~101k | Top tier, best success |

> Default buys cheapest. Use `maxPrice=0.208` to allow top tier.

## 🧩 Files

| File | Purpose |
|---|---|
| `jio.py` | Jio flow + Grizzly client (`getNumber`, `getStatus`, `setStatus`) |
| `.env.example` | Template (copy to `.env`, never commit `.env`) |

## ⚠️ Disclaimer

For educational use. You are responsible for complying with Jio and Grizzly SMS terms.

I'm not affiliated with Grizzly SMS. Their service is shit — if you find something better, use it. I'm not recommending it.
