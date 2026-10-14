# Udhaar · उधार

**A local AI back-office for the world's corner shops.** Udhaar, fiado, utang, hutang: the same credit notebook, everywhere. One box: speak or type in Marathi, Hindi, English, Spanish, Filipino or Indonesian.

- **Statements become entries.** *"Patil kaku, don kilo sakhar, 210 udhaar"* is written into the khata.
- **Questions get answers from the shop's own data.** *"Who owes the most?"*, *"how much sugar next week?"*, *"aaj ka hisab"*. Gemma picks the intent; SQL and TabPFN supply the numbers.
- **A morning briefing.** Who to collect from (TabPFN late-payment risk, with reasons), what to order before the next festival (TabPFN forecast), and how yesterday went. Each line has a one-tap action: a Gemma-drafted WhatsApp reminder or a wholesaler order list.

| Piece | Open component | Where it runs |
|---|---|---|
| Speech → text | faster-whisper (`small`) | laptop (CUDA if available, else CPU) |
| Text → ledger entry | **Gemma 3 4B** via Ollama, JSON-schema constrained; rule-based fallback | laptop |
| Reminder drafting | **Gemma 3 4B** | laptop |
| Late-payment risk + restock forecast | **TabPFN** (API: TabPFN-3.5, or local open weights) | API receives only anonymous numbers; local is fully offline |
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

Open http://localhost:8000.

To use the mic from the shop's phone over Wi-Fi, run `python scripts/serve_https.py` and open the `https://…:8443` address it prints. Browsers only allow the microphone over HTTPS.

Remove the demo data once the shop has real entries: `python scripts/make_demo_data.py --wipe`.

### Settings (env vars)
`UDHAAR_CURRENCY` (default `₹`; e.g. `$`, `₱`, `Rp `) · `UDHAAR_MODEL` (default `gemma3:4b`) · `UDHAAR_WHISPER` (`small`; use `medium` for better Marathi if the GPU allows) · `UDHAAR_LANG` (`mr`/`hi` to force a language) · `TABPFN_TOKEN` · `UDHAAR_NO_LOCAL_TABPFN=1`

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

Festival dates live in `app/predict.py → FESTIVALS`; check them each year.
