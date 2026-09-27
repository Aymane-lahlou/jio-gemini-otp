# jio-gemini-otp

Auto get Jio Gemini activation link via Grizzly SMS — auto-retries `jio/22` stock, polls OTP, verifies and extracts the `serviceactivation.google.com` link.

Docs: https://grizzlysms.com/docs

## Features

- Manual mode (paste number + OTP)
- Grizzly AUTO mode (API gets number + auto OTP → Gemini link)
- Grizzly OTP-only mode (paste number + activation ID, auto OTP)
- Waits for stock (`NO_NUMBERS` → poll `getNumber` / `getNumberV2`)
- Auto-retries numbers on `NOT_SUBSCRIBED_USER`
- Price-tier support via `maxPrice` (`jio/22`: `0.10` / `0.15` / `0.208`)

## Requirements

- Python 3.10+
- `pip install requests`

## Setup

```bash
cp .env.example .env
# edit .env and paste your key:
# GRIZZLY_API_KEY=xxx
```

Confirmed codes via Grizzly API:

- Service: `{"code":"jio","name":"MyJio"}`
- Country: `{"id":22,"eng":"India"}`

## Usage

```bash
python jio.py
```

Modes:

1. Manual (paste number, paste OTP)
2. Grizzly AUTO (API gets number + auto OTP → Gemini link)
3. Grizzly OTP only (paste number + ID, auto OTP → Gemini link)

Mode 2 prompts:

- `service` (default `jio`, `ot` = AnyOther workaround)
- `country` (default `22` = India, Jio needs +91)
- `maxPrice` (default cheapest; use `0.208` for top tier)
- numbers to try (`0` = infinite), wait minutes (`0` = infinite), retry seconds

Link is saved to `gemini_activation_link.txt`.

## Files

- `jio.py` — Jio flow + Grizzly client (`getNumber`, `getStatus`, `setStatus`)
- `.env.example` — copy to `.env` with your key (never commit `.env`)

## Disclaimer

For educational use. You are responsible for complying with Jio and Grizzly SMS terms.

I'm not affiliated with Grizzly SMS. Their service is shit — if you find something better, use it. I'm not recommending it.
