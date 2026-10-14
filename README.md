# Udhaar · उधार

![ci](https://github.com/vaidehi-snk/udhaar/actions/workflows/ci.yml/badge.svg)

**A local AI back-office for the world's corner shops.** Udhaar, fiado, utang, hutang: the same credit notebook, everywhere. One box: speak or type in Marathi, Hindi, English, Spanish, Filipino or Indonesian.

- **Statements become entries.** *"Patil kaku, don kilo sakhar, 210 udhaar"* is written into the khata.
- **Questions get answers from the shop's own data.** *"Who owes the most?"*, *"how much sugar next week?"*, *"aaj ka hisab"*. Gemma picks the intent; SQL and TabPFN supply the numbers.
- **It's a small prediction agent.** *"How much more udhaar can I give Shinde Mama?"*, *"what if Gaikwad Sir doesn't pay for 3 weeks?"*, or a compound *"Shinde mama wants more for Diwali, should I? what does he owe?"*. A planner (instant rules, or Gemma for compound questions) picks up to three tools; the tools are SQL and TabPFN. Every answer shows its trace: which tools ran, on which engine, in how many ms.
- **Every entry is price-checked.** TabPFN learns what *this* shop charges per item and quantity, and flags *"₹920 for 2 kg sugar? Usually about ₹92"* with a one-tap fix. That's the most common speech-to-text slip at a counter.
- **A morning briefing.** Who to collect from (TabPFN late-payment risk, with reasons), what to order before the next festival (TabPFN forecast), and how yesterday went. Each line has a one-tap action: a Gemma-drafted WhatsApp reminder or a wholesaler order list.

| Piece | Open component | Where it runs |
|---|---|---|
| Speech → text | faster-whisper (`small`) | laptop (CUDA if available, else CPU) |
| Text → ledger entry | **Gemma 3 4B** via Ollama, JSON-schema constrained; rule-based fallback | laptop |
| Reminder drafting | **Gemma 3 4B** | laptop |
| Late-payment risk, credit limits, what-ifs, price check, restock forecast | **TabPFN** (API: TabPFN-3.5, or local open weights) | API receives only anonymous numbers; local is fully offline |
| Ledger | SQLite file | laptop |

## Run it (Windows / macOS / Linux)

```bash
python -m venv .venv && .venv\Scripts\activate      # source .venv/bin/activate on mac/linux
pip install -r requirements.txt
ollama pull gemma3:4b
set TABPFN_TOKEN=your_key                           # export on mac/linux; from platform.priorlabs.ai
python scripts/make_demo_data.py                    # 13 months of sample history (optional)
uvicorn app.main:app --port 8000
```

Open http://localhost:8000 for the home page, or http://localhost:8000/app for the shop app itself (bookmark that one on the shop laptop).

To use the mic from the shop's phone over Wi-Fi, run `python scripts/serve_https.py` and open the `https://…:8443` address it prints. Browsers only allow the microphone over HTTPS.

Remove the demo data once the shop has real entries: `python scripts/make_demo_data.py --wipe`.

### Settings (env vars)
`SENTRY_DSN` (optional: Sentry AI-agent traces of every question; `pip install sentry-sdk`) · `UDHAAR_CURRENCY` (default `₹`; e.g. `$`, `₱`, `Rp `) · `UDHAAR_MODEL` (default `gemma3:4b`) · `UDHAAR_WHISPER` (`small`; use `medium` for better Marathi if the GPU allows) · `UDHAAR_LANG` (`mr`/`hi` to force a language) · `TABPFN_TOKEN` · `UDHAAR_NO_LOCAL_TABPFN=1`

## Tests and backtest
```bash
pytest -q
python scripts/eval_parser.py     # Gemma vs rules on real-sounding counter lines
python scripts/backtest.py        # TabPFN vs baselines on weeks the model never saw → shown on "How it works"
```

## Live demo
`render.yaml` deploys a read-only demo of the sample shop (`UDHAAR_DEMO=1`). See [DEPLOY.md](DEPLOY.md).

## How the predictions work
- **Udhaar risk:** We take a weekly snapshot of every open khata from the past and record whether at least half the dues were repaid within the next 30 days. That gives TabPFN a few hundred labelled rows with no training step. Features are due amount, days since last payment, credit taken in the last 30 days, repay ratio and usual gap between payments. No names are used.
- **Restock:** This is a direct multi-horizon forecast. For each item and day, the features are day-of-week, salary week, days to the next festival, and 7/28-day averages known at the forecast origin. All items × all days ahead are predicted in **one batched TabPFN call**. The result compares the festival fortnight with a normal fortnight.

- **Credit limit (agent tool):** the fitted risk model re-scores the customer on a ladder of "what if I give ₹X more" in **one batched call**. The limit is the tighter of (a) the last step before their risk crosses 35% (or 60% if they're already on watch, halved), and (b) the most they've ever repaid within 30 days, minus what they owe now. Risk is constrained to never fall as credit grows.
- **What-if (agent tool):** the same model on a shifted snapshot: `days` with no payment and/or `amount` more on udhaar.
- **Price check:** a TabPFN regressor on (item, quantity, unit) → price per unit, from the shop's last 2,000 priced entries. Flagged when the spoken amount is over 2.2× or under 0.45× the expected price (and at least ₹20 off).

CI (`.github/workflows/ci.yml`) runs the tests and posts the parser scores to each run's summary.

Festival dates live in `app/predict.py → FESTIVALS`; check them each year.
