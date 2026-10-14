---
title: "Udhaar: a local AI back-office for India's corner shops, built on Gemma and TabPFN"
tags: devchallenge, hf26challenge, opensource, ai
---

<!-- Lines marked [FILL] need your real details. Judges weight writing the most, so keep your own voice. Replace anything that doesn't sound like you. -->

*This is a submission for the [Hacktoberfest Open-Source AI Challenge: Week 2 — Side Hustle](https://dev.to/challenges)*

## The notebook behind the counter

Every kirana shop in India has one. It's a long, thin notebook, usually red, full of names like *Patil Kaku* and *Sharma Ji* and numbers that keep growing. That's the **udhaar khata**, the credit book. Half the neighbourhood buys on it and pays at the end of the month… or the month after… or the month after that.

[FILL: 2–3 sentences about the shop near your home in Aurangabad. How long it's been there, who runs it, what you saw when you asked about their khata. Use a real detail, e.g. "he showed me three notebooks, one held together with a rubber band."]

Every app that tries to fix this asks the shopkeeper to *type* during the evening rush with oil on their fingers. It also asks them to upload their customers' debts to someone else's server. So most of them still use the notebook.

## What I built

**Udhaar is an AI back-office for a corner shop that runs on the shop's own laptop.** It has one box. You can speak into it or type into it, in Marathi, Hindi, English or the mix everyone actually speaks.

Say something the way you'd write it in the notebook, and it gets written down:

> *"Patil kaku, don kilo sakhar ani ek litre tel, 210 udhaar"* → ₹210 udhaar for Patil Kaku: 2 kg sugar, 1 l oil.

Ask a question, and it answers from the shop's own records:

> *"Bhosale dada kiti baki?"* → Bhosale Dada owes ₹11,396. Last paid on 9 Sep. Chance of paying late: 99%.
> *"How much sugar next week?"* → About 43 kg (usually 61). In the two weeks before Diwali: 154 kg, +27%.

Every morning it hands the owner a three-line **briefing**:

- who to collect from today, and why;
- what to order before the festival, and how much;
- how yesterday went compared with a usual day.

Each line comes with a one-tap action: **Gemma drafts a polite WhatsApp reminder**, or **a wholesaler order list** built from the forecast.

Every risk score comes with its reasons in plain words, such as *"No payment in 34 days. Usually pays every 43."* A shopkeeper won't trust a number they can't argue with.

[FILL: screenshots of Today, a customer page and the Forecast page, from `docs/`]

{% embed [FILL: 60–90s demo video. Speak one entry, ask one question, show the briefing, tap "Draft reminder"] %}

## Why open models make this a business

I priced Udhaar at **₹149/month** [FILL: or whatever your shopkeeper said]. A kirana shop makes thin margins, and that number only works if the AI costs me nothing per entry. A busy shop logs 150–300 entries a day. Paying per API call would eat the subscription.

Open models change all three of the things that matter here:

- **Cost:** Whisper and Gemma 3 4B run on my everyday laptop, an i5 with an RTX 2050 and 4 GB of VRAM. The marginal cost of an entry is electricity.
- **Privacy:** A khata is a list of who in the neighbourhood owes money. It shouldn't live on a server the shopkeeper has never heard of. With Udhaar the ledger is one SQLite file on the shop's laptop, and speech and parsing never leave it.
- **Works when the internet doesn't:** The shop's connection drops every time it rains. Udhaar doesn't care.

For TabPFN, I use Prior Labs' **TabPFN-3.5 API** for the best accuracy. It only ever sees anonymous numbers like *due amount, days since last payment, day-of-week, days to festival*. No names, no items. If a shop wants zero network, the same code falls back to TabPFN's **open weights running locally**.

## How it works

```
 speak / type ─► faster-whisper ─► Gemma 3 4B (Ollama): entry or question?
                                     │                       │
                         entry (JSON schema)         question → intent (JSON schema)
                                     ▼                       ▼
                                SQLite khata ◄──── SQL + TabPFN compute the answer
                                     │
                     TabPFN classifier → who will pay late
                     TabPFN regressor  → festival-aware order plan
                     Gemma             → Marathi reminder, morning briefing
```

**The model routes, the database answers.** For questions, Gemma only decides *what* is being asked: an intent such as "how much does X owe" or "forecast for item Y", plus the customer, item and period. The number in the answer always comes from a SQL query or a TabPFN prediction. Gemma can misunderstand a question, but it cannot invent a balance. For a tool that handles people's debts, I think that's the only acceptable design.

**Speech → entry.** Gemma gets a short system prompt that explains how a kirana counter talks: *udhaar/khata* = credit, *jama/dile* = paid back, *sakhar* = sugar, *tup* = ghee. It also gets three examples. Ollama's `format` parameter constrains it to a JSON schema, so I never have to regex the model's output. A small rule-based parser sits behind it, so the counter keeps working even if the model is still loading.

I wrote 18 real-sounding counter lines, including Devanagari, half-payments and three items in one breath, and scored both parsers:

| Parser | Fully correct entries | Median latency |
|---|---|---|
| Rules only | 12 / 18 | <1 ms |
| Gemma 3 4B (local) | [FILL from `python scripts/eval_parser.py`] | [FILL] |

[FILL: one sentence on where Gemma won, probably the Devanagari lines and "1200 baki, aaj 400 parat dile", where the rules picked the wrong number.]

**Who will pay late (TabPFN classifier).** There's no labelled dataset for "my neighbours' repayment habits", and a corner shop will never have enough data to train a model. That's exactly where TabPFN shines: it makes predictions from a few hundred rows with **no training step**. I replay the khata and take a snapshot of every open account each week. Each snapshot gets labelled by whether that person repaid at least half their dues within 30 days. TabPFN learns from roughly 700 of these snapshots in seconds and scores today's accounts.

**What to stock (TabPFN regressor).** Kirana demand is all calendar: weekends, the first week of the month when salaries land, and the build-up to festivals. Each row is *(item, day-of-week, salary week, days-to-festival, recent 7- and 28-day averages, horizon)*. I predict every item × every day until Diwali in **one batched call** instead of looping. With the API, that kept the dashboard refresh to [FILL] seconds.

### Does it actually beat a guess?

I hid the future and made each model predict it. For restocking, the "shopkeeper guess" is the usual 4-week average, which is how most owners order today. For late payments, the baseline is the rule every owner already uses: *worry once someone hasn't paid for a month*.

| Window | Usual average | Gradient boosting | TabPFN |
|---|---|---|---|
| Ordinary fortnight | 26% | **23%** | 24% |
| Ganesh Chaturthi build-up | 27% | 22% | **20%** |
| Navratri build-up | 27% | 22% | **21%** |

*Forecast error (WAPE), lower is better.* TabPFN wins exactly where it matters: the festival build-ups, when guessing from the usual average is most wrong. In an ordinary fortnight it's a tie.

| Late-payment model | AUC | Hit rate |
|---|---|---|
| "Not paid in a month" rule | 0.67 | 40% |
| Gradient boosting | 0.81 | 56% |
| TabPFN | **0.82** | **60%** |

These numbers come from 13 months of **synthetic** shop history that I generated to mirror a real kirana: weekends, salary week, festival build-ups, and customers with different repayment habits. I say that plainly because a real shop's khata is exactly the data nobody should publish. [FILL: if your shopkeeper gives you even a week of real entries, mention it here.]

The result is a card that says **"Diwali in 25 days"** with ghee, maida, besan and sugar at the top. That's exactly what [FILL: shopkeeper's name/title] told me they always run out of.

## My first user

[FILL: this is the section that can win. Be specific and honest.]
- Who: [FILL: e.g. "Kaka at the general store two lanes from my society, open since 2009"]
- What happened when he tried it: [FILL: his reaction to speaking an entry, anything it misheard]
- **Would he pay?** [FILL: his exact words, translated. Yes, no or "only if…" are all fine; honest beats perfect]
- What he asked for next: [FILL: e.g. "print a monthly bill", "remind automatically on the 5th", "Hindi for my son"]
- What I changed after: [FILL: one small fix you made because of him]

## Try it

**Live demo:** [FILL: https://udhaar.tech]. This is the sample shop with typed entries. The microphone version runs on the shop's own laptop, by design.

```bash
git clone https://github.com/vaidehi-snk/udhaar && cd udhaar
pip install -r requirements.txt && ollama pull gemma3:4b
python scripts/make_demo_data.py && uvicorn app.main:app
```

`scripts/serve_https.py` puts it on the shop's Wi-Fi so the owner can use their phone as the mic.

## What's next

[FILL: 2–3 bullets from your user's requests.] Plus fine-tuning a small Whisper on real counter audio, because Marathi grocery words are where it still stumbles.

## Built with
Gemma 3 · Ollama · faster-whisper · TabPFN-3.5 (Prior Labs) · FastAPI · SQLite

[FILL: optional: DevRelay embed of your build session]
