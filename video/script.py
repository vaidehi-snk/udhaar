"""The narration, one line per scene. Edit the words here, then run make_voice.py.

Each scene's on-screen action (in record.py) waits for its line to finish, so the
video re-times itself if you change the text or swap in your own recordings.
"""
SCENES = [
    ("title",     "In Mexico, they call it fiado. In the Philippines, utang. In Indonesia, hutang. And here in India, udhaar."),
    ("notebook",  "It's the same notebook, behind every corner shop counter. Who took what. Who owes how much. Written by hand, in the middle of the rush."),
    ("intro",     "So I built Udhaar. It runs on the shop's own laptop, on open models, with no internet."),
    ("entry",     "The shopkeeper just says it the way they'd write it. Two kilos of sugar for Patil kaku, ninety-two rupees, on credit. It's in the ledger instantly."),
    ("global",    "And it doesn't care which country the counter is in. Doña Rosa's sugar, in Spanish. Aling Nena's rice, in Filipino. Same ledger, same balances."),
    ("slip",      "And if the mic hears nine hundred and twenty instead of ninety-two, TabPFN knows what this shop charges for sugar, and asks before it counts."),
    ("question",  "You can ask it things, too. Who owes the most? The answer comes straight from the shop's own records. The model never makes up a number."),
    ("agent",     "Or ask the hard one. How much more udhaar can I give Shinde Mama? It picks a tool, TabPFN tests every amount, and it shows exactly how it got there."),
    ("briefing",  "Every morning there's a short briefing. Who to collect from, what to order, and how yesterday went."),
    ("risk",      "TabPFN reads each customer's repayment history, flags who is likely to pay late, and tells you why."),
    ("forecast",  "Before Diwali, it forecasts what will run out first, from how this shop sold before past festivals."),
    ("reminder",  "When it's time to ask for the money, Gemma drafts a polite reminder, in the customer's own language."),
    ("hood",      "Speech, the language model and the ledger all stay on this laptop. Only anonymous numbers ever leave, and only if you allow it."),
    ("end",       "Udhaar. The corner shop's notebook, with a little help."),
]

CAPTIONS = {  # shorter on-screen captions (the voice says more)
    "title": "fiado · utang · hutang · udhaar",
    "notebook": "The same notebook, behind every counter",
    "intro": "Open models. The shop's own laptop. No internet.",
    "entry": "Say it the way you'd write it",
    "global": "Spanish · Filipino · Indonesian · Marathi · Hindi · English",
    "slip": "TabPFN checks every price against this shop's own history",
    "agent": "A small agent: Gemma plans, TabPFN computes",
    "question": "Answers come from the ledger, never from the model's imagination",
    "briefing": "A briefing every morning",
    "risk": "TabPFN: who is likely to pay late, and why",
    "forecast": "Festival-aware stock forecast",
    "reminder": "A polite reminder, in their language",
    "hood": "Everything stays on the laptop",
    "end": "",
}
