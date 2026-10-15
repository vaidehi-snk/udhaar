---
title: "The world's corner shops still run on a credit notebook. I gave it Gemma, TabPFN and no internet."
tags: devchallenge, hf26challenge, opensource, ai
---

<!-- Lines marked [FILL] need your real details. Judges weight writing the most, so keep your own voice. Replace anything that doesn't sound like you. -->

*This is a submission for the [Hacktoberfest Open-Source AI Challenge: Week 2 — Side Hustle](https://dev.to/challenges)*

## The notebook behind the counter

In Mexico it's called *fiado*. In a Philippine sari-sari store it's *utang*, written on a *listahan*. In an Indonesian warung it's *hutang* or *bon*. In India it's *udhaar*, kept in a *khata*. Different words, same notebook: the corner shop lets the neighbourhood take goods now and pay later, and writes it down by hand.

Every kirana shop in India has one. It's a long, thin notebook, usually red, full of names like *Patil Kaku* and *Sharma Ji* and numbers that keep growing. That's the **udhaar khata**, the credit book. Half the neighbourhood buys on it and pays at the end of the month… or the month after… or the month after that.

[FILL: 2–3 sentences about the shop near your home in Aurangabad. How long it's been there, who runs it, what you saw when you asked about their khata. Use a real detail, e.g. "he showed me three notebooks, one held together with a rubber band."]

Every app that tries to fix this asks the shopkeeper to *type* during the evening rush with oil on their fingers. It also asks them to upload their customers' debts to someone else's server. So most of them still use the notebook.

## What I built

**Udhaar is an AI back-office for a corner shop that runs on the shop's own laptop.** It has one box. You can speak into it or type into it in Marathi, Hindi, English, Spanish, Filipino or Indonesian, or the mix people actually speak at a counter.

> *"Doña Rosa, dos kilos de azúcar y un aceite, apúntalo, 96 pesos"*
> *"Aling Nena, isang kilong bigas at dalawang itlog, 85 utang"*
> *"Pak Budi ngutang beras 2 kilo dan minyak goreng 1 liter, 48.000"*

All three become the same kind of entry in the same ledger. I built and tested it with a real shop in Aurangabad, India [FILL once you've done the visit], but nothing in it is Indian-only.

Say something the way you'd write it in the notebook, and it gets written down:

> *"Patil kaku, don kilo sakhar ani ek litre tel, 210 udhaar"* → ₹210 udhaar for Patil Kaku: 2 kg sugar, 1 l oil.

Ask a question, and it answers from the shop's own records:

> *"Bhosale dada kiti baki?"* → Bhosale Dada owes ₹11,396. Last paid on 9 Sep. Chance of paying late: 99%.
> *"How much sugar next week?"* → About 43 kg (usually 61). In the two weeks before Diwali: 154 kg, +27%.

And it answers the question every shopkeeper actually agonises over, which no notebook can:

> *"How much more udhaar can I give Shinde Mama?"* → Safe to give up to ₹4,750 more. The most he has ever paid back in a month is ₹7,402. [FILL: use the numbers your own run shows]
> *"Bhosale dada ko aur udhaar de sakte?"* → Collect first. He owes ₹11,396 and is 99% likely to pay late.
> *"What if Gaikwad Sir doesn't pay for 3 weeks?"* → His chance of paying late goes from X% to Y%.

Every entry also gets a quiet **price check**. If the mic hears *"920"* for two kilos of sugar, Udhaar asks: *"₹920 for 2 kg sugar? This shop usually charges about ₹92."* One tap fixes it. In a credit book, a wrong extra zero is someone's neighbour being asked for ₹828 they never borrowed.

Every morning it hands the owner a three-line **briefing**:

- who to collect from today, and why;
- what to order before the festival, and how much;
- how yesterday went compared with a usual day.

Each line comes with a one-tap action: **Gemma drafts a polite WhatsApp reminder**, or **a wholesaler order list** built from the forecast.

Every risk score comes with its reasons in plain words, such as *"No payment in 34 days. Usually pays every 43."* A shopkeeper won't trust a number they can't argue with.

[FILL: screenshots of Today, a customer page and the Forecast page, from `docs/`]

{% embed [FILL: the demo video from `python video/record.py`, uploaded to YouTube] %}

## Who pays, and why open models are what make it a business

**Who pays:** the owner of a corner shop with 50–300 customers on credit. I priced it at **₹149/month** [FILL: or what your shopkeeper said]: less than one customer's monthly sugar. The sample shop has ₹37,000 out on udhaar. If the briefing gets one late account collected a week sooner, or stops one extra zero, the month is paid for.

That price only works if the AI costs me nothing per entry. A busy counter logs 150–300 lines a day, and every line goes through speech-to-text, a language model and a price check. So:

- **Cost.** Whisper and Gemma 3 4B run on my everyday laptop: an i5 with an RTX 2050 and 4 GB of VRAM. An entry costs electricity. With a per-call API, the AI bill would grow with every customer, and a ₹149 subscription would be underwater at a busy shop.
- **Privacy.** A khata is a list of which neighbours owe money. It shouldn't live on a server the shopkeeper has never heard of. The ledger is one SQLite file on the shop's laptop, and speech and parsing never leave it.
- **It works when the internet doesn't.** The shop's connection drops every time it rains. Udhaar doesn't notice.

### Where open actually beat closed

The reason I didn't expect: **because Gemma is free to run, I can run it twice.** Every entry is written instantly by fast rules, then Gemma re-reads the same line in the background and quietly corrects it if it disagrees. With a paid API I'd never design that, because I'd be paying to re-check every entry. With a local model, a second opinion on every line costs nothing, and it's what makes the counter both fast *and* accurate.

The second: **I could measure and swap.** I ran the same eval on Gemma 3 1B and 4B on my own GPU, saw the 1B was worse than my regex rules, and made the trade-off myself (below). I also constrain Gemma's output with a JSON schema through Ollama, so it can never return anything but a valid entry.

Where closed would win, honestly: a frontier API would probably parse my held-out Spanish/Filipino/Indonesian lines better, and faster than my laptop does. For the predictions I *do* use Prior Labs' hosted **TabPFN-3.5**, because it's more accurate. It only ever sees anonymous numbers like *due amount, days since last payment, day-of-week, days to festival*: no names, no items. A shop that wants zero network can switch to TabPFN's **open weights running locally** with the same code.

## How it works

```
 speak / type ─► faster-whisper ─► entry or question?
                                      │                         │
                        entry: rules now, Gemma re-reads    question: plan (rules, or Gemma
                        in the background (JSON schema)     for compound ones) → 1–3 tools
                                      │                         │
                        TabPFN price check ("₹920?")        tools: SQL ledger · TabPFN risk ·
                                      ▼                     credit limit · what-if · forecast
                                 SQLite khata ◄─────────────────┘   (every number comes from here)

        Gemma → WhatsApp reminder in the customer's language · morning briefing · wholesaler order
```

**The model routes, the database answers.** For questions, Gemma only decides *what* is being asked: an intent such as "how much does X owe" or "forecast for item Y", plus the customer, item and period. The number in the answer always comes from a SQL query or a TabPFN prediction. Gemma can misunderstand a question, but it cannot invent a balance. For a tool that handles people's debts, I think that's the only acceptable design.

**Speech → entry.** Gemma gets a short system prompt that explains how a kirana counter talks: *udhaar/khata* = credit, *jama/dile* = paid back, *sakhar* = sugar, *tup* = ghee. It also gets three examples. Ollama's `format` parameter constrains it to a JSON schema, so I never have to regex the model's output. A small rule-based parser sits behind it, so the counter keeps working even if the model is still loading.

I wrote 18 real-sounding counter lines, including Devanagari, half-payments and three items in one breath, and scored both parsers:

| Parser | Fully correct entries | Median latency |
|---|---|---|
| Rules only | 12 / 18 | <1 ms |
| Gemma 3 4B (local) | **15 / 18** | ~6 s |
| Gemma 3 1B (local, fits the GPU) | 9 / 18 | ~3.5 s |

Gemma got the type of entry, the customer and the amount right on all 18 lines; the rules managed 15, 14 and 16. Gemma's three misses were all in the item list, which is the least costly mistake: the money is still right and the shopkeeper can fix an item with one tap.

That left me with a real problem: my laptop's GPU has 4 GB, Gemma 3 4B needs about 3.5 GB plus room to think, so half of it spills onto the CPU and every entry takes ~6 seconds. Nobody waits 6 seconds per line in the evening rush. The 1B model fits the GPU completely, but it was *worse* than my regex rules.

**Outside India.** I wrote 15 counter lines each in the style of a Mexican tiendita, a sari-sari store and a warung, and tuned the rule parser on them until it got all 15. That number is meaningless on its own, so I then wrote 9 *new* lines I never tuned against:

| Lines | Rules | Gemma 3 4B |
|---|---|---|
| India (Marathi / Hindi / English), 18 | 12 | 15 |
| Spanish / Filipino / Indonesian, held out, 9 | 5 | **7** |

Getting the rules to work in four languages taught me how many collisions there are: *don* is "two" in Marathi but a title in Spanish ("Don Pepe"), and *andi* is "eggs" in Marathi but a common Indonesian name ("Mas Andi"). Thousands are written "48.000" in Indonesia and spoken as "50 ribu". Those are exactly the cases the held-out lines catch, and where a language model earns its place.

So Udhaar uses both. **The rules write the entry instantly** (under a millisecond), and the shopkeeper can move on to the next customer. **Gemma re-reads the same line in the background** and, if it understood it differently, quietly corrects the entry a few seconds later, with a small "Corrected by gemma3:4b" note. The counter gets the speed of the rules and the accuracy of the model. Questions work the same way: the rules answer the common phrasings instantly, and Gemma is only called for the long tail.

**Who will pay late (TabPFN classifier).** There's no labelled dataset for "my neighbours' repayment habits", and a corner shop will never have enough data to train a model. That's exactly where TabPFN shines: it makes predictions from a few hundred rows with **no training step**. I replay the khata and take a snapshot of every open account each week. Each snapshot gets labelled by whether that person repaid at least half their dues within 30 days. TabPFN learns from roughly 700 of these snapshots in seconds and scores today's accounts.

**What to stock (TabPFN regressor).** Kirana demand is all calendar: weekends, the first week of the month when salaries land, and the build-up to festivals. Each row is *(item, day-of-week, salary week, days-to-festival, recent 7- and 28-day averages, horizon)*. I predict every item × every day until Diwali in **one batched call** instead of looping. With the API, that kept the dashboard refresh to [FILL] seconds.

### TabPFN inside a small prediction agent

Questions go through a tiny agent loop: **plan, then call tools.** The planner is the instant rules for one-line questions, and Gemma for compound or advice-style ones (*"Shinde mama wants more for Diwali, should I? what does he owe?"* → `customer_due` + `credit_limit`). Gemma only picks the tools; it never writes a number. The tools are SQL and TabPFN:

- **`credit_limit`**: the fitted risk model re-scores the customer on a ladder of *"what if I give ₹X more"*, all rungs in **one batched TabPFN call**. The limit is the tighter of two things: the last rung before their late-payment risk crosses 35%, and the most they have ever repaid within 30 days. A small prior keeps the ladder honest: giving someone *more* credit never makes them *safer*, so the curve is not allowed to dip.
- **`what_if`**: the same model on a shifted snapshot: *21 more days with no payment*, or *₹2,000 more on udhaar*.
- **`price_check`**: a TabPFN regressor learns price-per-unit from the shop's own last 2,000 entries (item, quantity, unit) and flags an amount that's more than 2.2× or under 0.45× what it expects. This is TabPFN as an anomaly detector, on the anomaly that matters most at a counter.

Every answer has a **"How it got this"** trace under it: `plan · rules · 1 ms → credit limit (Shinde Mama) · TabPFN-3.5 · [FILL] ms`. A shopkeeper won't trust a number they can't argue with, and neither would I. [FILL if you set up Sentry: "The same spans go to Sentry's AI agent view:" + screenshot of one trace]

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
- **Gemma 3 4B** (Ollama, local): entry parsing, the agent's planner, reminders in six languages
- **TabPFN-3.5** (Prior Labs): late-payment risk, credit limits, what-ifs, price checks, festival forecast
- **faster-whisper** (local) · FastAPI · SQLite
- **Render** hosts the live demo's agent front end, deployed from `render.yaml`; **[FILL: udhaar.tech]** points at it
- **GitHub Actions** runs the tests and re-scores the parser on every push, posting the table to the run summary
- [FILL if used: **Sentry** AI-agent tracing for every question]

Code: [github.com/vaidehi-snk/udhaar](https://github.com/vaidehi-snk/udhaar) (MIT licensed)

[FILL: optional: DevRelay embed of your build session]
