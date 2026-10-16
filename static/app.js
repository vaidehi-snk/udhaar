/* Udhaar front end. No build step and no CDN, so it works with the internet off. */
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/* ---------------- words ---------------- */
const T = {
  en: {
    "nav.today": "Today", "nav.customers": "Customers", "nav.forecast": "Forecast", "nav.hood": "Under the hood",
    "cust.kicker": "Credit accounts", "fc.kicker": "Stock plan · TabPFN", "hood.kicker": "Open models, one laptop",
    kpi: { out: "Outstanding", outF: n => `across ${n} accounts`, coll: "Collected · 7 days", collF: p => p == null ? "" : `${p >= 0 ? "▲" : "▼"} ${Math.abs(p)}% vs last week`,
           cash: "Cash sales · yesterday", cashF: p => p == null ? "" : `${p >= 0 ? "▲" : "▼"} ${Math.abs(p)}% vs a usual day`, fest: "Next festival", festF: (d, i) => `in ${d} days · stock ${i}`, noFest: "No festival soon", late: "Likely late", lateF: a => `${a} at risk` },
    engineSub: h => h.model_ready ? "Gemma, Whisper, SQLite on this laptop" : "Rules mode · start Ollama for Gemma",
    shopMeta: (c, n) => `${c} · ${n} accounts`, modelChip: h => h.model_ready ? `${h.model} · local` : "rules mode",
    demo: "<b>Live demo</b> with a sample shop's 13 months of history. Type to try it. On the shop's own laptop you can also speak.",
    "cmd.go": "Enter", "brief.title": "Today's briefing", "recent.title": "Recent entries", "bal.title": "Udhaar balances",
    "cust.search": "Search customers", "cust.risk": "Risk", "cust.due": "Due", "cust.name": "Name",
    "fc.order": "Draft wholesaler order", "fc.daily": "Forecast per day", "fc.usual": "Usual day",
    "hood.title": "What runs where", "hood.sub": "Every model is open. Everything except optional anonymous numbers stays on the shop's laptop.",
    "hood.stays": "Never leaves the laptop", "hood.leaves": "Can leave, only if you allow it", "hood.bt": "Tested on weeks the models never saw", "hood.weeks": "Week by week",
    "w.cash": "Cash sales", "w.credit": "Udhaar given", "w.paid": "Collected",
    "dlg.close": "Close", "dlg.copy": "Copy", "dlg.wa": "Send on WhatsApp",
    hello: h => h < 12 ? "Good morning." : h < 17 ? "Good afternoon." : "Good evening.",
    sub: (due, n) => `${due} is out on udhaar across ${n} customers.`,
    ph: ["Patil kaku, 2 kilo sakhar, 92 udhaar", "Who owes the most?", "How much more udhaar can I give Shinde Mama?", "Doña Rosa, dos kilos de azúcar, 96 fiado", "How much sugar next week?", "What if Gaikwad Sir doesn't pay for 3 weeks?", "Aling Nena, isang kilong bigas, 85 utang", "Bu Sri bayar 50 ribu", "Aaj ka hisab"],
    hintsK: "Try", hints: ["Patil kaku 2 kilo sakhar 92 udhaar", "Doña Rosa, dos kilos de azúcar, 96 fiado", "Aling Nena isang kilong bigas 85 utang", "Pak Budi ngutang beras 2 kilo 30 ribu", "Who owes the most?", "How much more udhaar can I give Shinde Mama?", "What if Gaikwad Sir doesn't pay for 3 weeks?", "How much sugar next week?", "What should I order?"],
    listening: "Listening… tap again to stop", tooShort: "That was too short. Tap, speak, then tap again.", working: "Working…",
    kind: { credit: "Udhaar", sale: "Cash sale", payment: "Paid back" }, band: { high: "Likely late", watch: "Watch", ok: "Reliable" },
    priceOdd: (a, item, q, e) => `${a} for ${q} ${item}? This shop usually charges about ${e}.`, priceFix: e => `Change to ${e}`, priceKeep: "It's right", priceOk: "Price looks usual ✓", fixed: "Fixed",
    trace: "How it got this", plan: "plan", limitT: "Can I give more udhaar?", limitLbl: v => `limit ${v}`, ladderCap: "chance of paying late, if you give this much more",
    walkin: "Walk-in", written: "Written to the khata", checking: "Gemma checking…", corrected: e => `Corrected by ${e}`, confirmed: e => `Checked by ${e} ✓`, undo: "Undo", removed: "Removed",
    by: (e, ms) => `${e === "rules" ? "rules fallback" : e} · ${ms}`,
    remind: "Draft reminder", order: "Draft order", openCust: "Open",
    briefKind: { collect: "Collect", order: "Order", day: "Yesterday" },
    entries: n => `${n} shown`, accounts: n => `${n} accounts`,
    noVoice: "This online demo has no microphone. Type instead; on the shop's laptop you can speak.", micBlocked: "The browser blocked the microphone. Open Udhaar on localhost or with serve_https.py.",
    owes: "owes", lastPaid: d => `last paid ${d} days ago`, chance: "chance they pay back less than half within 30 days",
    why: "Why", whyNote: "The signals TabPFN used, compared with this shop's other customers.",
    since: (d, g) => `No payment in ${d} days. Usually pays every ${g}.`, sinceOk: (d, g) => `Paid ${d} days ago. Usually pays every ${g}.`,
    ratioBad: p => `Has paid back ${p}% of all udhaar taken.`, ratioOk: p => `Has paid back ${p}% of all udhaar taken.`,
    recentBad: a => `Took ${a} on udhaar in the last 30 days, more than most.`, dueBad: x => `Owes ${x}× a typical balance.`,
    facts: ["Udhaar taken", "Paid back", "Entries"], balance: "Balance over time", history: "Entries",
    noCust: "No udhaar accounts yet. They appear when someone takes goods on credit.",
    fcTitle: (f, d) => f ? `${f} is ${d} days away` : "The next 7 days",
    fcSub: f => f ? "TabPFN compares the two weeks before the festival with a normal fortnight, using this shop's past festivals." : "No festival close by. This is a normal week's forecast.",
    fcCols: f => f ? ["Item", "Normal 2 wks", "Festival 2 wks", "Change", "Order extra"] : ["Item", "Usual week", "Next 7 days", "Change", "Order extra"],
    fcNote: (e, n, s) => `${e} · ${n} training rows · ${s}`, itemTitle: i => `${i}, day by day`,
    reminderFor: n => `Reminder for ${n}`, reminderSub: "Drafted by Gemma on this laptop. Edit before sending.",
    orderT: "Order for the wholesaler", orderSub: "From the forecast. Edit quantities before sending.", copied: "Copied",
    gemmaWriting: "Writing…",
    stages: [["Speak or type", "Marathi, Hindi, English, Spanish, Filipino, Indonesian, or a mix"], ["Whisper", "faster-whisper turns speech into text"], ["Gemma 3", "Re-reads every entry; plans which tools answer a question"], ["SQLite", "The khata. Every number comes from here"], ["TabPFN", "Late-payment risk, credit limits, what-ifs, price checks, festival forecast"]],
    where: { local: "on the laptop", off: "not running", cloud: "API, numbers only", rules: "rules fallback", base: "baseline model" },
    stays: ["<b>The voice recording.</b> Transcribed locally, then deleted.", "<b>Names, phone numbers, amounts.</b> One file: <code>data/udhaar.db</code>.", "<b>Understanding sentences.</b> Gemma runs in Ollama. No internet needed."],
    leaves: ["<b>Anonymous numbers for TabPFN-3.5:</b> amounts, day counts, weekdays. No names, no items.", "<b>Nothing at all</b> if you install TabPFN's open weights locally.", "<b>Reminders and orders</b> are sent by the shopkeeper, from their own WhatsApp."],
    bt: { win: "Window", naive: "Usual average", hgb: "Gradient boosting", tab: "TabPFN", wape: "Forecast error (WAPE), lower is better.", model: "Late-payment model", rule: "“Unpaid for a month” rule", auc: "AUC", hit: "Hit rate", cap: n => `Scored on 14-day snapshots over 6 months, n = ${n}.`, demo: "Sample shop data.", none: "Run python scripts/backtest.py to fill this in." },
    localText: h => h.model_ready ? "Local AI on" : "Local · rules mode",
  },
  mr: {
    "nav.today": "आज", "nav.customers": "ग्राहक", "nav.forecast": "अंदाज", "nav.hood": "आत काय चालते",
    "cust.kicker": "उधार खाती", "fc.kicker": "माल नियोजन · TabPFN", "hood.kicker": "Open models, एक लॅपटॉप",
    kpi: { out: "एकूण बाकी", outF: n => `${n} खात्यांवर`, coll: "वसूल · 7 दिवस", collF: p => p == null ? "" : `${p >= 0 ? "▲" : "▼"} ${Math.abs(p)}% मागच्या आठवड्यापेक्षा`,
           cash: "रोख विक्री · काल", cashF: p => p == null ? "" : `${p >= 0 ? "▲" : "▼"} ${Math.abs(p)}% नेहमीपेक्षा`, fest: "पुढचा सण", festF: (d, i) => `${d} दिवसांत · ${i} भरा`, noFest: "जवळ सण नाही", late: "उशीर शक्य", lateF: a => `${a} धोक्यात` },
    engineSub: h => h.model_ready ? "Gemma, Whisper, SQLite या लॅपटॉपवर" : "नियम पद्धत · Gemma साठी Ollama सुरू करा",
    shopMeta: (c, n) => `${c} · ${n} खाती`, modelChip: h => h.model_ready ? `${h.model} · स्थानिक` : "नियम पद्धत",
    demo: "<b>थेट डेमो</b>: नमुना दुकानाचा 13 महिन्यांचा इतिहास. टाइप करून पाहा. दुकानाच्या लॅपटॉपवर बोलूनही वापरता येते.",
    "cmd.go": "लिहा", "brief.title": "आजचा आढावा", "recent.title": "शेवटच्या नोंदी", "bal.title": "उधारी",
    "cust.search": "ग्राहक शोधा", "cust.risk": "धोका", "cust.due": "बाकी", "cust.name": "नाव",
    "fc.order": "होलसेल ऑर्डर तयार करा", "fc.daily": "रोजचा अंदाज", "fc.usual": "नेहमीचा दिवस",
    "hood.title": "काय कुठे चालते", "hood.sub": "सर्व मॉडेल्स open आहेत. ऐच्छिक निनावी आकडे सोडले तर सर्व काही दुकानाच्या लॅपटॉपवरच राहते.",
    "hood.stays": "लॅपटॉपबाहेर कधीच जात नाही", "hood.leaves": "परवानगी दिली तरच बाहेर जाते", "hood.bt": "मॉडेल्सनी न पाहिलेल्या आठवड्यांवर चाचणी", "hood.weeks": "आठवड्यानुसार",
    "w.cash": "रोख विक्री", "w.credit": "उधार दिले", "w.paid": "वसूल",
    "dlg.close": "बंद", "dlg.copy": "कॉपी", "dlg.wa": "WhatsApp वर पाठवा",
    hello: h => h < 12 ? "सुप्रभात." : h < 17 ? "नमस्कार." : "शुभ संध्याकाळ.",
    sub: (due, n) => `${n} ग्राहकांकडे एकूण ${due} उधार बाकी.`,
    ph: ["Patil kaku, 2 kilo sakhar, 92 udhaar", "कोणाकडे सर्वात जास्त बाकी?", "Doña Rosa, dos kilos de azúcar, 96 fiado", "Pudhchya athavdyat kiti sakhar?", "Aling Nena, isang kilong bigas, 85 utang", "Aaj ka hisab"],
    hintsK: "उदा.", hints: ["Patil kaku 2 kilo sakhar 92 udhaar", "Kon jast baki?", "Shinde mama la ajun kiti udhaar deu?", "Pudhchya athavdyat kiti sakhar?", "Kay mangvaycha?", "Aaj ka hisab"],
    listening: "ऐकत आहे… थांबवण्यासाठी पुन्हा टॅप करा", tooShort: "खूपच लहान. टॅप करा, बोला, मग पुन्हा टॅप करा.", working: "करत आहे…",
    kind: { credit: "उधार", sale: "रोख", payment: "जमा" }, band: { high: "उशीर शक्य", watch: "लक्ष ठेवा", ok: "भरवशाचे" },
    priceOdd: (a, item, q, e) => `${q} ${item} साठी ${a}? हे दुकान सहसा सुमारे ${e} घेते.`, priceFix: e => `${e} करा`, priceKeep: "बरोबर आहे", priceOk: "किंमत नेहमीसारखी ✓", fixed: "दुरुस्त केले",
    trace: "हे उत्तर कसे आले", plan: "योजना", limitT: "अजून उधार देऊ का?", limitLbl: v => `मर्यादा ${v}`, ladderCap: "इतके अजून उधार दिले तर उशिरा भरण्याची शक्यता",
    walkin: "रोख ग्राहक", written: "खात्यात लिहिले", checking: "Gemma तपासत आहे…", corrected: e => `${e} ने दुरुस्त केले`, confirmed: e => `${e} ने तपासले ✓`, undo: "मागे घ्या", removed: "काढले",
    by: (e, ms) => `${e === "rules" ? "नियम पद्धत" : e} · ${ms}`,
    remind: "आठवण तयार करा", order: "ऑर्डर तयार करा", openCust: "उघडा",
    briefKind: { collect: "वसुली", order: "ऑर्डर", day: "काल" },
    entries: n => `${n} नोंदी`, accounts: n => `${n} खाती`,
    noVoice: "या ऑनलाइन डेमोमध्ये माइक नाही. टाइप करा; दुकानाच्या लॅपटॉपवर बोलता येते.", micBlocked: "ब्राउझरने माइक अडवला. localhost किंवा serve_https.py ने उघडा.",
    owes: "बाकी", lastPaid: d => `शेवटचे ${d} दिवसांपूर्वी भरले`, chance: "३० दिवसांत अर्ध्यापेक्षा कमी भरण्याची शक्यता",
    why: "का?", whyNote: "TabPFN ने वापरलेले संकेत, दुकानाच्या इतर ग्राहकांशी तुलना करून.",
    since: (d, g) => `${d} दिवस काही भरले नाही. सहसा दर ${g} दिवसांनी भरतात.`, sinceOk: (d, g) => `${d} दिवसांपूर्वी भरले. सहसा दर ${g} दिवसांनी.`,
    ratioBad: p => `घेतलेल्या उधारीपैकी ${p}% परत केले.`, ratioOk: p => `घेतलेल्या उधारीपैकी ${p}% परत केले.`,
    recentBad: a => `गेल्या ३० दिवसांत ${a} उधार, बहुतेकांपेक्षा जास्त.`, dueBad: x => `सामान्य बाकीच्या ${x} पट.`,
    facts: ["एकूण उधार", "परत केले", "नोंदी"], balance: "बाकी कशी बदलली", history: "नोंदी",
    noCust: "अजून उधार खाती नाहीत.",
    fcTitle: (f, d) => f ? `${f} ला ${d} दिवस` : "पुढचे ७ दिवस",
    fcSub: f => f ? "मागच्या सणांवरून TabPFN सणाआधीच्या दोन आठवड्यांची नेहमीच्या पंधरवड्याशी तुलना करते." : "जवळ सण नाही. हा नेहमीच्या आठवड्याचा अंदाज आहे.",
    fcCols: f => f ? ["माल", "नेहमी २ आठवडे", "सण २ आठवडे", "फरक", "जास्त मागवा"] : ["माल", "नेहमीचा आठवडा", "पुढचे ७ दिवस", "फरक", "जास्त मागवा"],
    fcNote: (e, n, s) => `${e} · ${n} ओळी · ${s}`, itemTitle: i => `${i}, रोजचा अंदाज`,
    reminderFor: n => `${n} यांना आठवण`, reminderSub: "Gemma ने या लॅपटॉपवर लिहिले. पाठवण्यापूर्वी बदला.",
    orderT: "होलसेलरसाठी ऑर्डर", orderSub: "अंदाजावरून. पाठवण्यापूर्वी आकडे तपासा.", copied: "कॉपी केले",
    gemmaWriting: "लिहित आहे…",
    stages: [["बोला किंवा लिहा", "मराठी, हिंदी, इंग्रजी, स्पॅनिश, फिलिपिनो, इंडोनेशियन किंवा मिसळून"], ["Whisper", "आवाजाचा मजकूर करते"], ["Gemma 3", "प्रत्येक नोंद पुन्हा तपासते; प्रश्नासाठी कोणती साधने वापरायची ते ठरवते"], ["SQLite", "खाते. प्रत्येक आकडा इथूनच"], ["TabPFN", "उशिरा भरणी, उधार मर्यादा, किंमत तपासणी, सणाचा अंदाज"]],
    where: { local: "लॅपटॉपवर", off: "बंद", cloud: "API, फक्त आकडे", rules: "नियम पद्धत", base: "साधे मॉडेल" },
    stays: ["<b>आवाजाचे रेकॉर्डिंग.</b> इथेच मजकूर होऊन पुसले जाते.", "<b>नावे, फोन नंबर, रक्कम.</b> एकच फाइल: <code>data/udhaar.db</code>.", "<b>वाक्य समजणे.</b> Gemma Ollama मध्ये चालते. इंटरनेट लागत नाही."],
    leaves: ["<b>TabPFN-3.5 साठी निनावी आकडे:</b> रक्कम, दिवस, वार. नावे नाहीत, माल नाही.", "<b>काहीच नाही</b>, जर TabPFN चे open weights लॅपटॉपवर लावले.", "<b>आठवण आणि ऑर्डर</b> दुकानदार स्वतःच्या WhatsApp वरून पाठवतात."],
    bt: { win: "कालावधी", naive: "नेहमीची सरासरी", hgb: "Gradient boosting", tab: "TabPFN", wape: "अंदाजातील चूक (WAPE), कमी तितके चांगले.", model: "उशिरा भरणी मॉडेल", rule: "“महिनाभर भरले नाही” नियम", auc: "AUC", hit: "अचूकता", cap: n => `६ महिन्यांतील दर १४ दिवसांच्या नोंदींवर, n = ${n}.`, demo: "नमुना दुकानाच्या नोंदी.", none: "python scripts/backtest.py चालवा." },
    localText: h => h.model_ready ? "स्थानिक AI चालू" : "स्थानिक · नियम पद्धत",
  },
};
let lang = (() => { try { return localStorage.getItem("udhaar.lang") || "en"; } catch { return "en"; } })();
const L = () => T[lang];
const tr = k => T[lang][k] ?? T.en[k] ?? k;
const loc = () => (lang === "mr" ? "mr-IN-u-nu-latn" : "en-IN");
let CUR = "₹";
const inr = n => CUR + Math.round(n || 0).toLocaleString("en-IN");
const num = n => Math.round(n || 0).toLocaleString("en-IN");
const ITEM_MR = { sugar: "साखर", oil: "तेल", rice: "तांदूळ", atta: "आटा", "toor dal": "तूर डाळ", milk: "दूध", onion: "कांदा", potato: "बटाटा", tea: "चहा पत्ती", noodles: "नूडल्स", soap: "साबण", biscuits: "बिस्किटे", ghee: "तूप", besan: "बेसन", rava: "रवा", maida: "मैदा", eggs: "अंडी", salt: "मीठ" };
const itemName = i => (lang === "mr" ? ITEM_MR[i] || i : i);
const FEST = { "2025-09-22": ["Navratri", "नवरात्र"], "2025-10-21": ["Diwali", "दिवाळी"], "2026-03-19": ["Gudi Padwa", "गुढीपाडवा"], "2026-09-14": ["Ganesh Chaturthi", "गणेश चतुर्थी"], "2026-10-11": ["Navratri", "नवरात्र"], "2026-11-08": ["Diwali", "दिवाळी"] };
const festName = d => (FEST[d] || ["The festival", "सण"])[lang === "mr" ? 1 : 0];
const UNIT = { milk: "l", oil: "l", eggs: "dz", noodles: "pkt", biscuits: "pkt", tea: "pkt", soap: "pc" };
const unit = i => UNIT[i] || "kg";
const shortDate = iso => new Date(iso).toLocaleDateString(loc(), { day: "numeric", month: "short" });

const AV = ["#F7C35F", "#FF8F6B", "#3DD6A3", "#7CB4FF", "#C69CFF", "#FF7FB0", "#5ED3E8"];
const initials = n => (n || "?").replace(/^(do[nñ]a?|se[nñ]ora?|aling|mang|kuya|ate|tita|tito|bu|ibu|pak|bapak|mbak|mas)\s+/i, "").split(/\s+/).slice(0, 2).map(w => w[0] || "").join("").toUpperCase();
const avatar = n => { let h = 0; for (const c of n || "") h = (h * 31 + c.charCodeAt(0)) >>> 0; return `<span class="av" style="background:${AV[h % AV.length]}">${esc(initials(n) || "·")}</span>`; };
/* numbers count up once, on first paint */
function countUp(el, to, fmt) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) { el.textContent = fmt(to); return; }
  const t0 = performance.now(), d = 700;
  const step = t => { const k = Math.min(1, (t - t0) / d), e = 1 - Math.pow(1 - k, 3); el.textContent = fmt(to * e); if (k < 1) requestAnimationFrame(step); };
  requestAnimationFrame(step);
}

/* ---------------- plumbing ---------------- */
const S = { health: null, ledger: null, ins: null, brief: null, summary: null, bt: null, sel: null, cust: null, item: null, sort: "risk" };
async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}
const post = (p, b) => api(p, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(b) });
function toast(msg, action) {
  const el = $("#toast"); el.innerHTML = `<span>${esc(msg)}</span>`;
  if (action) { const b = document.createElement("button"); b.textContent = action.label; b.onclick = action.fn; el.append(b); }
  el.classList.add("show"); clearTimeout(toast.t); toast.t = setTimeout(() => el.classList.remove("show"), action ? 6000 : 2400);
}

/* ---------------- nav + language ---------------- */
let current = "today";
function go(view) {
  current = view;
  $$("nav.tabs button").forEach(b => b.dataset.view === view ? b.setAttribute("aria-current", "page") : b.removeAttribute("aria-current"));
  $$(".view").forEach(v => v.classList.toggle("active", v.id === "v-" + view));
  if (view === "customers" && !S.sel) pickFirst();
  if (view === "hood") (S.bt ? renderHood() : loadHood());
  window.scrollTo(0, 0);
  try { history.replaceState(null, "", "#" + view); } catch {}
}
$$("nav.tabs button").forEach(b => b.onclick = () => go(b.dataset.view));
$("#localBtn").onclick = () => go("hood");
$$(".lang button").forEach(b => b.onclick = async () => {
  lang = b.dataset.lang; try { localStorage.setItem("udhaar.lang", lang); } catch {}
  applyLang(); S.brief = await api(`/api/brief?lang=${lang}`).catch(() => S.brief); renderBrief();
});
function applyLang() {
  document.documentElement.lang = lang;
  $$("[data-i18n]").forEach(el => { el.innerHTML = tr(el.dataset.i18n); });
  $$("[data-i18n-ph]").forEach(el => { el.placeholder = tr(el.dataset.i18nPh); });
  $$(".lang button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.lang === lang)));
  $("#hello").textContent = L().hello(new Date().getHours());
  $("#today").textContent = new Date().toLocaleDateString(loc(), { weekday: "long", day: "numeric", month: "long" });
  $("#q").placeholder = L().ph[0];
  $("#hints").innerHTML = `<span class="k">${L().hintsK}</span>` + L().hints.map(h => `<button type="button">${esc(h)}</button>`).join("");
  $$("#hints button").forEach(b => b.onclick = () => { $("#q").value = b.textContent; submit(); });
  renderAll();
}

/* rotating placeholder: shows both jobs of the box */
let phI = 0;
setInterval(() => { if (document.activeElement !== $("#q") && !$("#q").value) { phI = (phI + 1) % L().ph.length; $("#q").placeholder = L().ph[phI]; } }, 3200);

/* ---------------- the command box ---------------- */
$("#cmd").onsubmit = e => { e.preventDefault(); submit(); };
async function submit() {
  const text = $("#q").value.trim(); if (!text) return;
  $("#goBtn").disabled = true; $("#cmdWrap").classList.add("thinking");
  try { show(await post("/api/ask", { text, lang })); $("#q").value = ""; }
  catch (e) { $("#reply").innerHTML = ""; toast(e.message); }
  finally { $("#goBtn").disabled = false; $("#cmdWrap").classList.remove("thinking"); }
}
/* Mic: record raw samples and send 16 kHz mono WAV. Whisper reads WAV directly, so no
   audio-decoding library is needed on the laptop (that's where most setups break). */
let rec = null;
function wav16k(chunks, rate) {
  const n = chunks.reduce((a, c) => a + c.length, 0), all = new Float32Array(n);
  let o = 0; for (const c of chunks) { all.set(c, o); o += c.length; }
  const ratio = rate / 16000, len = Math.floor(n / ratio), pcm = new Int16Array(len);
  for (let i = 0; i < len; i++) {                       // simple averaging downsample
    const a = Math.floor(i * ratio), b = Math.min(n, Math.floor((i + 1) * ratio)); let sum = 0;
    for (let j = a; j < b; j++) sum += all[j];
    const v = Math.max(-1, Math.min(1, sum / Math.max(1, b - a))); pcm[i] = v < 0 ? v * 0x8000 : v * 0x7fff;
  }
  const buf = new ArrayBuffer(44 + pcm.length * 2), d = new DataView(buf), str = (p, t) => [...t].forEach((ch, i) => d.setUint8(p + i, ch.charCodeAt(0)));
  str(0, "RIFF"); d.setUint32(4, 36 + pcm.length * 2, true); str(8, "WAVE"); str(12, "fmt ");
  d.setUint32(16, 16, true); d.setUint16(20, 1, true); d.setUint16(22, 1, true); d.setUint32(24, 16000, true);
  d.setUint32(28, 32000, true); d.setUint16(32, 2, true); d.setUint16(34, 16, true); str(36, "data"); d.setUint32(40, pcm.length * 2, true);
  new Int16Array(buf, 44).set(pcm);
  return new Blob([buf], { type: "audio/wav" });
}
async function stopMic() {
  const r = rec; rec = null; if (!r) return;
  r.node.disconnect(); r.src.disconnect(); r.stream.getTracks().forEach(t => t.stop()); await r.ctx.close();
  $("#mic").classList.remove("rec"); $("#cmdWrap").classList.remove("listening");
  if (r.chunks.reduce((a, c) => a + c.length, 0) < r.rate * 0.4) { toast(L().tooShort); return; }
  $("#cmdWrap").classList.add("thinking");
  const fd = new FormData(); fd.append("audio", wav16k(r.chunks, r.rate), "clip.wav");
  try { show(await api(`/api/voice?lang=${lang}`, { method: "POST", body: fd })); } catch (e) { $("#reply").innerHTML = ""; toast(e.message); }
  finally { $("#cmdWrap").classList.remove("thinking"); }
}
$("#mic").onclick = async () => {
  if (S.health && S.health.demo) { toast(L().noVoice); $("#q").focus(); return; }   // hosted demo: no mic
  if (rec) { stopMic(); return; }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const src = ctx.createMediaStreamSource(stream), node = ctx.createScriptProcessor(4096, 1, 1), chunks = [];
    node.onaudioprocess = e => chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
    src.connect(node); node.connect(ctx.destination);
    rec = { stream, ctx, src, node, chunks, rate: ctx.sampleRate };
    $("#mic").classList.add("rec"); $("#cmdWrap").classList.add("listening"); $("#q").placeholder = L().listening;
    setTimeout(() => { if (rec && rec.ctx === ctx) stopMic(); }, 20000);   // safety stop after 20 s
  } catch { toast(L().micBlocked); }
};

function show(r, note = "") {
  const meta = r.mode === "entry" ? (note || L().by(r.parsed._engine, (r.parsed._ms / 1000).toFixed(1) + "s") + (r.refining ? " · " + L().checking : "")) : L().by(r.engine === "rules" ? "instant" : r.engine, (r.ms / 1000).toFixed(1) + "s");
  const stt = r.stt_ms ? ` · whisper ${(r.stt_ms / 1000).toFixed(1)}s` : "";
  let body;
  if (r.mode === "entry") {
    const p = r.parsed;
    const items = (p.items || []).map(i => `<span class="chip-s">${esc(itemName(i.name))}${i.qty != null ? " · " + i.qty + (i.unit ? " " + esc(i.unit) : "") : ""}</span>`).join("");
    body = `<div class="entry-line">${avatar(p.customer || L().walkin)}<b>${esc(p.customer || L().walkin)}</b><span class="tag ${p.kind}">${L().kind[p.kind]}</span>${items}<span class="big tnum">${p.total != null ? inr(p.total) : ""}</span></div>
      <div class="acts"><button class="btn link" id="undoBtn">${L().undo}</button></div>`;
  } else {
    const rows = (r.rows || []).map(row => `<tr>${row.map(c => `<td>${esc(c)}</td>`).join("")}</tr>`).join("");
    const acts = (r.actions || []).map((a, i) => `<button class="btn" data-act="${i}">${a.type === "remind" ? L().remind : L().order}</button>`).join("")
      + (r.customer_id ? `<button class="btn link" data-open="${r.customer_id}">${L().openCust} →</button>` : "");
    const head = r.head && rows ? `<thead><tr>${r.head.map(h => `<th>${esc(h)}</th>`).join("")}</tr></thead>` : "";
    body = `<div class="a">${esc(r.answer)}</div>${r.curve && (r.limit || r.curve[0][1] < 0.6) ? ladder(r.curve, r.limit, ((r.trace || []).find(t => t.step === "credit_limit") || {}).engine) : ""}${rows && !r.curve ? `<table>${head}<tbody>${rows}</tbody></table>` : ""}${acts ? `<div class="acts">${acts}</div>` : ""}${traceHtml(r.trace)}`;
  }
  $("#reply").innerHTML = `<div class="reply${note ? " flash" : ""}"><div class="q"><span>${esc(r.text)}</span><span class="${note ? "fix" : ""}">${meta}${stt}</span></div>${body}</div>`;
  if (r.mode === "entry") {
    if (!note) toast(L().written);
    if (r.refine && !note) pollRefine(r);
    $("#undoBtn").onclick = async () => { await Promise.all(r.ids.map(id => api(`/api/entries/${id}`, { method: "DELETE" }))); $("#reply").innerHTML = ""; toast(L().removed); refresh(); };
    refresh();
  } else {
    $$("#reply [data-act]").forEach(b => b.onclick = () => act(r.actions[+b.dataset.act]));
    $$("#reply [data-open]").forEach(b => b.onclick = () => openCust(+b.dataset.open));
  }
}
/* The agent's trace: which tools ran, on which engine, how long each took. */
function engineShort(e) { return !e ? "" : /TabPFN-3\.5/.test(e) ? "TabPFN-3.5" : /TabPFN/.test(e) ? "TabPFN (local)" : /fallback|boosting/.test(e) ? "baseline model" : e; }
function traceHtml(t) {
  if (!t || !t.length) return "";
  const steps = t.map(s => {
    const fmt = (k, v) => k === "days" ? `${v} ${lang === "mr" ? "दिवस" : "days"}` : k === "amount" ? inr(v) : String(v);
    const args = s.args ? Object.entries(s.args).filter(([, v]) => v !== "" && v != null).map(([k, v]) => esc(fmt(k, v))).join(", ") : "";
    const name = s.step === "plan" ? L().plan : esc(s.step.replace(/_/g, " "));
    return `<li><span class="tn">${name}${args ? `<i>(${args})</i>` : ""}</span><span class="te">${esc(engineShort(s.engine === "rules" ? "rules" : s.engine))} · ${s.ms} ms</span></li>`;
  }).join("");
  return `<details class="trace"><summary>${L().trace} · ${t.length - 1} ${t.length - 1 === 1 ? "tool" : "tools"}</summary><ol>${steps}</ol></details>`;
}
/* Credit-limit ladder: TabPFN's late-payment risk as more udhaar is given. */
function ladder(curve, limit, engine) {
  const mx = Math.max(...curve.map(c => c[0])) || 1, X = g => g / mx * 100, Y = p => 100 - p * 100;
  const d = curve.map((c, i) => `${i ? "L" : "M"}${X(c[0]).toFixed(2)} ${Y(c[1]).toFixed(2)}`).join("");
  const band = (v, cls) => `<div class="lv ${cls}" style="top:${Y(v)}%"><span>${v * 100}%</span></div>`;
  const lim = limit != null && limit > 0 ? `<div class="lim" style="left:${X(Math.min(limit, mx))}%"><span>${L().limitLbl(inr(limit))}</span></div>` : "";
  const ticks = [0, .5, 1].map(f => `<span style="left:${f * 100}%">+${inr(Math.round(mx * f / 50) * 50)}</span>`).join("");
  return `<div class="ladder"><div class="plot">${band(0.6, "hi")}${band(0.35, "wa")}${lim}
    <svg viewBox="0 0 100 100" preserveAspectRatio="none"><path d="${d}L100 100L0 100Z" class="fill"/><path d="${d}" class="ln"/></svg></div>
    <div class="ax">${ticks}</div><div class="cap">${esc(engineShort(engine) || "TabPFN")}: ${L().ladderCap}</div></div>`;
}
/* After every entry: TabPFN checks the price, then Gemma re-reads the line and quietly fixes it if needed. */
async function pollRefine(r) {
  const job = r.refine, t0 = Date.now(); let priced = false;
  while (Date.now() - t0 < 30000) {
    await new Promise(res => setTimeout(res, 700));
    let j; try { j = await api(`/api/refine/${job}`); } catch { return; }
    if (!$("#reply .reply") || r._gone) return;
    if (j.checked && !priced) { priced = true; priceNote(r, j.check); }
    if (j.status !== "done") continue;
    if (j.changed) { show({ ...r, parsed: { ...j.parsed, _engine: j.engine }, ids: j.ids, refine: null, refining: false }, L().corrected(j.engine)); priceNote({ ...r, ids: j.ids, parsed: j.parsed }, j.check); refresh(); }
    else { const m = $("#reply .q span:last-child"); if (m) { m.textContent = j.engine !== "rules" ? L().confirmed(j.engine) : m.textContent.replace(" · " + L().checking, ""); if (j.engine !== "rules") m.className = "ok"; } }
    return;
  }
}
function priceNote(r, c) {
  const box = $("#reply .reply"); if (!box || !c) return;
  box.querySelector(".price")?.remove();
  const el = document.createElement("div");
  if (!c.odd) { el.className = "price ok"; el.textContent = `${L().priceOk} · ${engineShort(c.engine)}`; box.appendChild(el); return; }
  el.className = "price odd";
  const unit = ((r.parsed.items || []).find(i => i.name === c.item) || {}).unit || "";
  el.innerHTML = `<span>${esc(L().priceOdd(inr(c.amount), itemName(c.item), c.qty + (unit ? " " + unit : ""), inr(c.expected)))} <i>${esc(engineShort(c.engine))}</i></span>
    <span class="acts"><button class="btn primary" id="pfix">${L().priceFix(inr(c.expected))}</button><button class="btn link" id="pkeep">${L().priceKeep}</button></span>`;
  box.appendChild(el);
  $("#pkeep").onclick = () => el.remove();
  $("#pfix").onclick = async () => {
    const p = JSON.parse(JSON.stringify(r.parsed)); delete p._engine; delete p._ms;
    const it = (p.items || []).find(i => i.name === c.item);
    if (it && it.amount) { p.total = (p.total || 0) - it.amount + c.expected; it.amount = c.expected; } else p.total = c.expected;
    await Promise.all(r.ids.map(id => api(`/api/entries/${id}`, { method: "DELETE" })));
    const s = await post("/api/entries", { parsed: p, raw_text: r.text });
    r.ids = s.ids; r.parsed = { ...p, _engine: r.parsed._engine, _ms: r.parsed._ms };
    const big = $("#reply .big"); if (big) big.textContent = inr(p.total);
    el.className = "price ok"; el.textContent = L().fixed + " ✓"; toast(L().fixed); refresh();
  };
}
function act(a) { if (!a) return; a.type === "remind" ? remind(a.customer, a.due) : draftOrder(); }

/* ---------------- briefing + lists ---------------- */
const BICON = {
  collect: '<svg viewBox="0 0 24 24"><path d="M12 3v18M16.5 7.5c0-1.9-2-3-4.5-3s-4.5 1.1-4.5 3 2 2.6 4.5 3.2 4.5 1.3 4.5 3.3-2 3.3-4.5 3.3-4.5-1.2-4.5-3"/></svg>',
  order: '<svg viewBox="0 0 24 24"><path d="M4 5h2l2 11h10l2-8H7"/><circle cx="10" cy="20" r="1.3"/><circle cx="17" cy="20" r="1.3"/></svg>',
  day: '<svg viewBox="0 0 24 24"><path d="M3 20h18"/><path d="M6 16V11M11 16V7M16 16v-4M21 16V9"/></svg>',
};
function renderBrief() {
  const B = S.brief; if (!B) return;
  $("#brief").innerHTML = B.cards.map((c, i) => `<article class="card">
      <div class="bk ${c.kind}"><span class="ico">${BICON[c.kind]}</span>${L().briefKind[c.kind]}</div>
      <div class="t">${esc(c.title)}</div><div class="b">${esc(c.body)}</div>
      ${c.names ? `<div class="names">${c.names.map(n => `<button data-name="${esc(n)}">${esc(n)}</button>`).join("")}</div>` : ""}
      <div class="act">${c.action ? `<button class="btn ${i === 0 ? "primary" : ""}" data-card="${i}">${c.action.type === "remind" ? L().remind : L().order}</button>` : ""}</div>
    </article>`).join("");
  $$("#brief [data-card]").forEach(b => b.onclick = () => act(B.cards[+b.dataset.card].action));
  $$("#brief [data-name]").forEach(b => b.onclick = () => { const x = (S.ledger?.balances || []).find(y => y.name === b.dataset.name); if (x) openCust(x.id); });
  $("#briefMeta").textContent = new Date().toLocaleDateString(loc(), { day: "numeric", month: "short" });
  renderKpis();
}
function spark(vals, color) {
  if (!vals || vals.length < 2) return "";
  const w = 120, h = 40, max = Math.max(...vals) || 1, min = Math.min(...vals);
  const X = i => i / (vals.length - 1) * w, Y = v => h - 3 - (v - min) / ((max - min) || 1) * (h - 8);
  const d = vals.map((v, i) => `${i ? "L" : "M"}${X(i).toFixed(1)} ${Y(v).toFixed(1)}`).join("");
  return `<svg class="sparkline" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><path d="${d}L${w} ${h}L0 ${h}Z" fill="${color}" opacity=".12" stroke="none"/><path d="${d}" stroke="${color}" stroke-width="1.6"/></svg>`;
}
let kpiPainted = false;
function renderKpis() {
  const B = S.brief, R = S.ins?.restock, W = S.summary?.weeks || [], K = L().kpi; if (!B) return;
  const coll = W.map(w => w.payment), last = coll.at(-1), prev = coll.at(-2);
  const collPct = prev ? Math.round((last / prev - 1) * 100) : null;
  const day = B.cards.find(c => c.kind === "day"), dayPct = day ? +(day.body.match(/^([+-]?\d+)%/) || [])[1] : NaN;
  const cashVals = W.map(w => w.sale), risk = (S.ins?.risk?.customers || []).filter(c => c.band === "high");
  const fest = R?.next_festival && R.items?.[0]?.festival_14d != null;
  const cards = [
    { lbl: K.out, ico: '<svg viewBox="0 0 24 24"><path d="M4 7h16v12H4z"/><path d="M4 7l2-3h12l2 3M9 12h6"/></svg>', v: B.total_due, fmt: inr, foot: K.outF(B.accounts), sp: spark(W.map(w => w.credit), "var(--risk)") },
    { lbl: K.coll, ico: '<svg viewBox="0 0 24 24"><path d="M12 19V5M6 11l6-6 6 6"/></svg>', v: last || 0, fmt: inr, foot: `<span class="${collPct >= 0 ? "up" : "dn"}">${K.collF(collPct)}</span>`, sp: spark(coll, "var(--accent)") },
    { lbl: K.late, ico: '<svg viewBox="0 0 24 24"><path d="M12 4 2.5 20h19z"/><path d="M12 10v4M12 17h.01"/></svg>', v: risk.length, fmt: num, foot: K.lateF(inr(risk.reduce((a, c) => a + c.due, 0))), sp: spark(cashVals, "var(--ink-3)") },
    fest ? { hot: true, lbl: K.fest, ico: '<svg viewBox="0 0 24 24"><path d="M12 3c2.5 3.2 2.5 5.6 0 7.5-2.5-1.9-2.5-4.3 0-7.5z"/><path d="M4 14c2 5.3 14 5.3 16 0z"/></svg>', v: R.days_to_festival, fmt: v => `${festName(R.next_festival)} · ${num(v)}d`, foot: K.festF(R.days_to_festival, R.items.slice(0, 3).map(i => itemName(i.item)).join(", ")) }
         : { lbl: K.fest, ico: "", v: 0, fmt: () => "—", foot: K.noFest },
  ];
  $("#kpis").innerHTML = cards.map(c => `<div class="kpi${c.hot ? " hot" : ""}"><div class="lbl">${c.ico}${c.lbl}</div><div class="val">${c.fmt(c.v)}</div><div class="foot">${c.foot}</div>${c.sp || ""}</div>`).join("");
  if (!kpiPainted) { $$("#kpis .val").forEach((el, i) => cards[i].v && countUp(el, cards[i].v, cards[i].fmt)); kpiPainted = true; }
  // header chips
  const h = S.health || {};
  $("#headChips").innerHTML = (fest ? `<span class="chip fest">✦ <b>${festName(R.next_festival)}</b> ${R.days_to_festival}d</span>` : "")
    + `<span class="chip"><i class="dot ${h.model_ready ? "on" : "off"}"></i>${L().modelChip(h)}</span>`;
}
let seenIds = new Set();
function renderRecent() {
  const rows = (S.ledger?.recent || []).slice(0, 8);
  const fresh = seenIds.size ? new Set(rows.filter(e => !seenIds.has(e.id)).map(e => e.id)) : new Set();
  rows.forEach(e => seenIds.add(e.id));
  $("#recentMeta").textContent = rows[0] ? shortDate(rows[0].ts) : "";
  $("#recent").innerHTML = rows.map(e => `<li class="${fresh.has(e.id) ? "new" : ""}">
      ${avatar(e.customer || L().walkin)}
      <span><span class="nm">${esc(e.customer || L().walkin)}</span> <span class="tag ${e.kind}">${L().kind[e.kind]}</span><br>
        <span class="what"><span class="time tnum">${esc(e.ts.slice(11, 16))}</span>${e.item ? esc((e.qty != null ? +e.qty + " " + (e.unit || "") + " " : "") + itemName(e.item)) : ""}</span></span>
      <span class="amt ${e.kind}">${e.kind === "payment" ? "+" : ""}${e.amount ? inr(e.amount) : "—"}<button class="x" data-del="${e.id}" aria-label="Remove">✕</button></span></li>`).join("") || `<li class="empty">—</li>`;
  $$("#recent [data-del]").forEach(b => b.onclick = async () => { await api(`/api/entries/${b.dataset.del}`, { method: "DELETE" }); toast(L().removed); refresh(); });
}
const riskMap = () => Object.fromEntries((S.ins?.risk?.customers || []).map(c => [c.customer, c]));
function sortedPeople(q = "") {
  const rm = riskMap();
  let list = (S.ledger?.balances || []).map(b => ({ ...b, r: rm[b.name] }));
  if (q) list = list.filter(b => b.name.toLowerCase().includes(q.toLowerCase()));
  const by = { risk: (a, b) => (b.r?.risk ?? -1) - (a.r?.risk ?? -1) || b.due - a.due, due: (a, b) => b.due - a.due, name: (a, b) => a.name.localeCompare(b.name) };
  return list.sort(by[S.sort]);
}
function renderBal() {
  const list = sortedPeople().slice(0, 9);
  $("#balMeta").textContent = S.ledger ? L().accounts(S.ledger.balances.length) : "";
  $("#bal").innerHTML = list.map(b => `<li data-id="${b.id}">${avatar(b.name)}<span class="nm">${esc(b.name)}</span>
      <span>${b.r ? `<span class="pill ${b.r.band}">${L().band[b.r.band]}</span>` : ""}</span><span class="amt tnum">${inr(b.due)}</span></li>`).join("") || `<li class="empty">${L().noCust}</li>`;
  $$("#bal [data-id]").forEach(li => li.onclick = () => openCust(+li.dataset.id));
}

/* ---------------- customers ---------------- */
function renderPeople() {
  const list = sortedPeople($("#search").value.trim());
  $("#people").innerHTML = list.map(b => `<li><button data-id="${b.id}" ${S.sel === b.id ? 'aria-current="true"' : ""}>
      ${avatar(b.name)}<span class="pn">${esc(b.name)}</span><span class="pd">${inr(b.due)}</span>
      <span class="rd" style="background:${b.r ? { high: "var(--risk)", watch: "var(--warn)", ok: "var(--accent)" }[b.r.band] : "var(--line-2)"}"></span></button></li>`).join("") || `<li class="empty">${L().noCust}</li>`;
  $$("#people [data-id]").forEach(b => b.onclick = () => openCust(+b.dataset.id, false));
}
$("#search").oninput = renderPeople;
$$(".seg button").forEach(b => b.onclick = () => { S.sort = b.dataset.sort; $$(".seg button").forEach(x => x.setAttribute("aria-pressed", String(x === b))); renderPeople(); });
function pickFirst() { const p = sortedPeople()[0]; p ? openCust(p.id, false) : renderDetail(); }
async function openCust(id, sw = true) {
  if (sw) go("customers");
  S.sel = id; renderPeople();
  $("#detail").innerHTML = `<div class="skel"></div><div class="skel"></div>`;
  let c; try { c = await api(`/api/customer/${id}`); } catch { c = null; }
  if (S.sel !== id) return;                      // a later click won the race
  S.cust = c; renderDetail();
}
const median = a => { const s = [...a].sort((x, y) => x - y); return s.length ? s[s.length >> 1] : 0; };
function reasons(r) {
  const all = (S.ins?.risk?.customers || []).map(c => c.features), f = r.features, out = [], gap = Math.round(f.avg_pay_gap);
  out.push(f.days_since_payment > gap * 1.15 ? ["bad", L().since(f.days_since_payment, gap)] : ["good", L().sinceOk(f.days_since_payment, gap)]);
  const p = Math.round(f.repay_ratio * 100); out.push(p < 75 ? ["bad", L().ratioBad(p)] : ["good", L().ratioOk(p)]);
  const m1 = median(all.map(x => x.credit_amt_30d)); if (m1 && f.credit_amt_30d > m1 * 1.5) out.push(["bad", L().recentBad(inr(f.credit_amt_30d))]);
  const m2 = median(all.map(x => x.due)); if (m2 && f.due > m2 * 2) out.push(["bad", L().dueBad((f.due / m2).toFixed(1))]);
  return out;
}
function line({ pts, w = 640, h = 200, color = "var(--ink)", fmt = inr, xl = [], base = null, mark = null, area = true }) {
  if (pts.length < 2) return "";
  const P = { l: 60, r: 8, t: 10, b: 26 }, ys = pts.concat(base != null ? [base] : []), max = Math.max(...ys) * 1.1 || 1;
  const X = i => P.l + i / (pts.length - 1) * (w - P.l - P.r), Y = v => P.t + (1 - v / max) * (h - P.t - P.b);
  const d = pts.map((v, i) => `${i ? "L" : "M"}${X(i).toFixed(1)} ${Y(v).toFixed(1)}`).join("");
  let s = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img">`;
  [0, .5, 1].forEach(f => { const v = f * max; s += `<line x1="${P.l}" x2="${w - P.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--line)"/><text x="${P.l - 8}" y="${Y(v) + 4}" text-anchor="end">${fmt(v)}</text>`; });
  xl.forEach(([i, t]) => { s += `<text x="${X(i)}" y="${h - 6}" text-anchor="${i === 0 ? "start" : i === pts.length - 1 ? "end" : "middle"}">${esc(t)}</text>`; });
  if (base != null) s += `<line x1="${P.l}" x2="${w - P.r}" y1="${Y(base)}" y2="${Y(base)}" stroke="var(--ink-3)" stroke-dasharray="4 3"/>`;
  if (mark) s += `<line x1="${X(mark[0])}" x2="${X(mark[0])}" y1="${P.t}" y2="${h - P.b}" stroke="var(--line-2)"/><text x="${X(mark[0]) - 6}" y="${P.t + 12}" text-anchor="end" style="fill:var(--ink-2)">${esc(mark[1])}</text>`;
  if (area) s += `<path d="${d}L${X(pts.length - 1)} ${Y(0)}L${X(0)} ${Y(0)}Z" fill="${color}" opacity=".06"/>`;
  s += `<path d="${d}" fill="none" stroke="${color}" stroke-width="1.75" stroke-linejoin="round"/><circle cx="${X(pts.length - 1)}" cy="${Y(pts.at(-1))}" r="3.5" fill="${color}"/>`;
  return s + "</svg>";
}
function ring(p, col) {
  const R = 50, C = 2 * Math.PI * R;
  return `<div class="ring"><svg viewBox="0 0 118 118"><circle class="trk" cx="59" cy="59" r="${R}"/><circle class="val" cx="59" cy="59" r="${R}" stroke="${col}" stroke-dasharray="${C}" stroke-dashoffset="${C}" data-off="${C * (1 - p)}"/></svg><b style="color:${col}">${Math.round(p * 100)}%</b></div>`;
}
function renderDetail() {
  const c = S.cust;
  if (!c) { $("#detail").innerHTML = `<div class="empty">${L().noCust}</div>`; return; }
  const r = c.risk, col = r ? { high: "var(--risk)", watch: "var(--warn)", ok: "var(--accent)" }[r.band] : "var(--ink)";
  const pts = c.series.map(p => p.balance), n = pts.length;
  const xl = n > 2 ? [[0, shortDate(c.series[0].ts)], [n - 1, shortDate(c.series[n - 1].ts)]] : [];
  $("#detail").innerHTML = `
    <div class="d-head"><div class="d-id">${avatar(c.name)}<div><h1>${esc(c.name)}</h1><div class="sub">${r ? `<span class="pill ${r.band}">${L().band[r.band]}</span><span class="muted">${L().lastPaid(r.days_since_payment)}</span>` : ""}</div></div></div>
      <div class="d-due"><span>${L().owes}</span><b>${inr(c.due)}</b></div></div>
    ${r ? `<div class="risk"><div>${ring(r.risk, col)}<span>${L().chance}</span></div>
      <div class="why"><h3>${L().why}</h3><ul>${reasons(r).map(([k, s]) => `<li class="${k}">${esc(s)}</li>`).join("")}</ul><div class="note">${L().whyNote}</div></div></div>` : ""}
    <div class="facts"><div>${L().facts[0]}<b>${inr(c.credit_total)}</b></div><div>${L().facts[1]}<b>${inr(c.paid_total)}</b></div><div>${L().facts[2]}<b>${num(c.n_entries)}</b></div></div>
    ${c.due > 0 ? `<div class="sect lim-sect"><h2>${L().limitT}</h2><div id="limSlot"><div class="skel"></div></div></div>` : ""}
    ${c.due > 0 ? `<div class="d-actions"><button class="btn primary" id="remBtn"><svg viewBox="0 0 24 24"><path d="M4 20l1.3-4A8 8 0 1 1 8 18.7z"/></svg>${L().remind}</button></div>` : ""}
    <div class="sect"><h2>${L().balance}</h2>${line({ pts, xl, color: col })}</div>
    <div class="sect"><h2>${L().history}</h2><ul class="hist">${c.entries.slice(0, 12).map(e => `<li>
      <span class="time">${shortDate(e.ts)}</span><span class="what">${e.item ? esc((e.qty != null ? +e.qty + " " + (e.unit || "") + " " : "") + itemName(e.item)) : L().kind[e.kind]}</span>
      <span class="amt ${e.kind}">${e.kind === "payment" ? "+" : ""}${inr(e.amount)}</span></li>`).join("")}</ul></div>`;
  requestAnimationFrame(() => requestAnimationFrame(() => $$("#detail .ring .val").forEach(el => el.style.strokeDashoffset = el.dataset.off)));
  const rb = $("#remBtn"); if (rb) rb.onclick = () => remind(c.name, c.due);
  if (c.due > 0) api(`/api/limit/${c.id}?lang=${lang}`).then(l => {
    const slot = $("#limSlot"); if (!slot || S.cust !== c) return;
    const flat = !l.curve || (!l.limit && l.curve[0][1] >= 0.6);   // "collect first": the ladder adds nothing
    slot.innerHTML = !flat ? `<p class="lim-a">${esc(l.answer)}</p>${ladder(l.curve, l.limit, l.engine)}` : `<p class="lim-a">${esc(l.answer || "")}</p>`;
  }).catch(() => { const slot = $("#limSlot"); if (slot) slot.closest(".sect").remove(); });
}

/* ---------------- forecast ---------------- */
function renderForecast() {
  const R = S.ins?.restock; if (!R?.items?.length) return;
  const fest = R.items[0].festival_14d != null && R.next_festival;
  $("#fcTitle").textContent = L().fcTitle(fest ? festName(R.next_festival) : null, R.days_to_festival);
  $("#fcSub").textContent = L().fcSub(fest);
  $("#fcHead").innerHTML = L().fcCols(fest).map(c => `<th>${c}</th>`).join("");
  $("#fcBody").innerHTML = R.items.map(i => {
    const f = fest ? i.festival_14d : i.next_7d, n = fest ? i.normal_14d : i.normal_7d, p = fest ? i.festival_change_pct : i.week_change_pct, x = Math.max(0, Math.ceil(f - n));
    return `<tr data-item="${esc(i.item)}" aria-selected="${S.item === i.item}" tabindex="0"><td class="item">${esc(itemName(i.item))}</td>
      <td class="tnum">${num(n)} ${unit(i.item)}</td><td class="tnum">${num(f)} ${unit(i.item)}</td>
      <td><span class="barcell"><i style="width:${Math.max(4, Math.min(60, Math.abs(p || 0) * 1.4))}px;${p > 0 ? "" : "background:var(--line-2)"}"></i><span class="${p > 0 ? "up" : "down"}">${p > 0 ? "+" : ""}${p ?? 0}%</span></span></td><td class="tnum">${x ? "+" + num(x) + " " + unit(i.item) : "—"}</td></tr>`;
  }).join("");
  $$("#fcBody tr").forEach(t => { t.onclick = () => { S.item = t.dataset.item; renderForecast(); }; t.onkeydown = e => e.key === "Enter" && t.click(); });
  $("#fcNote").textContent = L().fcNote(R.engine, num(R.train_rows), (S.ins.ms / 1000).toFixed(1) + "s");
  const it = R.items.find(i => i.item === S.item) || R.items[0]; S.item = it.item;
  const start = new Date(R.from), n = it.daily.length;
  const fi = R.next_festival ? Math.round((new Date(R.next_festival) - start) / 864e5) : null;
  $("#itemTitle").textContent = L().itemTitle(itemName(it.item));
  $("#itemChart").innerHTML = line({ pts: it.daily, w: 520, h: 240, color: "var(--brand)", fmt: v => num(v) + " " + unit(it.item),
    xl: [[0, shortDate(R.from)], [n - 1, shortDate(new Date(start.getTime() + (n - 1) * 864e5).toISOString())]],
    base: fest ? it.normal_14d / 14 : it.normal_7d / 7, mark: fi != null && fi < n ? [fi, festName(R.next_festival)] : null });
}

/* ---------------- dialogs ---------------- */
const dlg = $("#dlg");
$("#dlgClose").onclick = () => dlg.close();
$("#dlgCopy").onclick = async () => { try { await navigator.clipboard.writeText($("#dlgText").value); toast(L().copied); } catch {} };
const syncWa = () => { $("#dlgWa").href = "https://wa.me/?text=" + encodeURIComponent($("#dlgText").value); };
$("#dlgText").oninput = syncWa;
let remindFor = null;
async function remind(name, due, language) {
  remindFor = { name, due };
  const sel = $("#dlgLang"); sel.hidden = false;
  if (!language) { language = /\b(do[nñ]a?|se[nñ]ora?)\b/i.test(name) ? "spanish" : /\b(aling|mang|kuya|ate|tita|tito)\b/i.test(name) ? "filipino" : /\b(bu|ibu|pak|bapak|mbak|mas)\b/i.test(name) ? "indonesian" : (lang === "mr" ? "marathi" : "english"); }
  sel.value = language;
  $("#dlgTitle").textContent = L().reminderFor(name); $("#dlgSub").textContent = L().reminderSub; $("#dlgText").value = L().gemmaWriting;
  if (!dlg.open) dlg.showModal();
  try { $("#dlgText").value = (await post("/api/reminder", { customer: name, due, language })).text; } catch (e) { toast(e.message); }
  syncWa();
}
$("#dlgLang").onchange = e => remindFor && remind(remindFor.name, remindFor.due, e.target.value);
async function draftOrder() {
  remindFor = null; $("#dlgLang").hidden = true;
  $("#dlgTitle").textContent = L().orderT; $("#dlgSub").textContent = L().orderSub; $("#dlgText").value = "…"; dlg.showModal();
  try { $("#dlgText").value = (await api(`/api/order?lang=${lang}`)).text; } catch (e) { toast(e.message); }
  syncWa();
}
$("#orderBtn").onclick = draftOrder;

/* ---------------- under the hood ---------------- */
async function loadHood() { try { [S.summary, S.bt] = await Promise.all([api("/api/summary"), api("/api/backtest")]); } catch {} renderHood(); }
function renderHood() {
  const h = S.health || {}, W = L().where;
  const st = [["on", W.local], [h.whisper ? "on" : "off", h.whisper ? W.local : W.off], [h.model_ready ? "on" : "off", h.model_ready ? W.local : W.rules], ["on", W.local],
    /API/.test(h.tabpfn || "") ? ["cloud", W.cloud] : /local/.test(h.tabpfn || "") ? ["on", W.local] : ["off", W.base]];
  $("#steps").innerHTML = L().stages.map(([t, d], i) => `<div class="step"><div class="w"><i class="dot ${st[i][0]}"></i>${st[i][1]}</div><h3>${t}</h3><p>${d}</p></div>`).join("");
  $("#stays").innerHTML = L().stays.map(s => `<li>${s}</li>`).join("");
  $("#leaves").innerHTML = L().leaves.map(s => `<li>${s}</li>`).join("");
  const B = S.bt, bt = L().bt, pct = v => (v == null ? "—" : Math.round(v * 100) + "%");
  if (B?.available) {
    const tab = B.methods.includes("auto");
    const rows = B.restock.map(r => { const v = [r.naive, r.baseline, tab ? r.auto : null], b = Math.min(...v.filter(x => x != null));
      return `<tr><td>${esc(r.window)}</td>${v.map(x => `<td class="tnum ${x === b ? "best" : ""}">${pct(x)}</td>`).join("")}</tr>`; }).join("");
    const rk = B.risk, ms = [["rule", bt.rule], ["baseline", bt.hgb], ["auto", bt.tab]].filter(([m]) => rk[m]), ba = Math.max(...ms.map(([m]) => rk[m].auc));
    $("#bt").innerHTML = `<table class="t static"><thead><tr><th>${bt.win}</th><th>${bt.naive}</th><th>${bt.hgb}</th><th>${bt.tab}</th></tr></thead><tbody>${rows}</tbody><caption>${bt.wape} ${B.data === "demo" ? bt.demo : ""}</caption></table>
      <table class="t static" style="margin-top:28px"><thead><tr><th>${bt.model}</th><th>${bt.auc}</th><th>${bt.hit}</th></tr></thead><tbody>
      ${ms.map(([m, l]) => `<tr><td>${l}</td><td class="tnum ${rk[m].auc === ba ? "best" : ""}">${rk[m].auc.toFixed(2)}</td><td class="tnum">${pct(rk[m].precision_at_k)}</td></tr>`).join("")}</tbody><caption>${bt.cap(rk.n)}</caption></table>`;
  } else $("#bt").innerHTML = `<div class="empty">${bt.none}</div>`;
  const Wk = S.summary?.weeks || [];
  if (Wk.length) {
    const w = 520, hh = 220, P = { l: 60, r: 4, t: 10, b: 26 }, keys = [["sale", "var(--ink-2)"], ["credit", "var(--risk)"], ["payment", "var(--accent)"]];
    const max = Math.max(...Wk.flatMap(x => keys.map(([k]) => x[k]))) * 1.08, gw = (w - P.l - P.r) / Wk.length, bw = Math.min(10, gw / 4.5);
    const Y = v => P.t + (1 - v / max) * (hh - P.t - P.b);
    let s = `<svg class="chart" viewBox="0 0 ${w} ${hh}" role="img">`;
    [0, .5, 1].forEach(f => { const v = f * max; s += `<line x1="${P.l}" x2="${w - P.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--line)"/><text x="${P.l - 8}" y="${Y(v) + 4}" text-anchor="end">${inr(v)}</text>`; });
    Wk.forEach((x, i) => { const gx = P.l + i * gw + gw / 2 - bw * 1.5 - 2;
      keys.forEach(([k, c], j) => { s += `<rect x="${gx + j * (bw + 2)}" y="${Y(x[k])}" width="${bw}" height="${Math.max(0, Y(0) - Y(x[k]))}" rx="1.5" fill="${c}"><title>${inr(x[k])}</title></rect>`; });
      if (i % 3 === 0) s += `<text x="${P.l + i * gw + gw / 2}" y="${hh - 6}" text-anchor="middle">${shortDate(x.week)}</text>`; });
    $("#weeks").innerHTML = s + "</svg>";
  }
}

/* ---------------- status + load ---------------- */
function renderStatus() {
  const h = S.health; if (!h) return;
  $("#localDot").className = "dot " + (h.model_ready ? "on" : "off");
  $("#localText").textContent = L().localText(h);
  $("#demo").hidden = !h.demo;
  if (h.currency) CUR = h.currency;
  $("#engineSub").textContent = L().engineSub(h);
  if (h.shop) $("#shopName").textContent = h.shop;
  $("#shopMeta").textContent = L().shopMeta(h.city || "", S.ledger?.balances?.length ?? "–");
}
function renderAll() {
  renderStatus(); renderBrief(); renderRecent(); renderBal(); renderPeople(); renderForecast();
  if (S.cust) renderDetail();
  if (current === "hood" || S.summary) renderHood();
}
async function refresh() {
  S.ledger = await api("/api/ledger"); renderRecent(); renderBal(); renderPeople();
  try { S.ins = await api("/api/insights"); } catch {}
  try { [S.brief, S.summary] = await Promise.all([api(`/api/brief?lang=${lang}`), api("/api/summary")]); } catch {}
  renderStatus(); renderBrief(); renderBal(); renderPeople(); renderForecast();
  if (current === "customers") S.sel ? openCust(S.sel, false) : pickFirst();
}
(async function init() {
  applyLang();
  try { S.health = await api("/api/health"); } catch {}
  renderStatus();
  const start = (location.hash || "#today").slice(1);
  if (["customers", "forecast", "hood"].includes(start)) go(start);
  await refresh();
})();
