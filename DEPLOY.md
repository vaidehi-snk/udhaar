# Put the live demo online (Render + your .tech domain)

The hosted demo is for judges. It uses the sample shop and typed entries, with TabPFN predictions. Real shops run Udhaar on their own laptop.

## 1. Push to GitHub
```powershell
cd E:\OneDrive\Desktop\udhaar
git init
git add .
git commit -m "Udhaar: voice khata for kirana shops"
gh repo create udhaar --public --source . --push      # or create the repo on github.com and push
```
`data/` is in `.gitignore`, so your local khata never goes to GitHub.

## 2. Deploy on Render
1. Go to render.com → **New** → **Blueprint** → pick the `udhaar` repo. It reads `render.yaml`.
2. When it asks for `TABPFN_TOKEN`, paste your Prior Labs key.
3. Wait for the build (about 3–5 min). Open the `https://udhaar-demo.onrender.com` link it gives you.

On the free plan the app sleeps after 15 minutes idle, and the first visit takes about 30–50 s to wake it. Open it yourself just before you publish the post.

## 3. Point your .tech domain at it
1. Claim the domain at hacktoberfest.com/my/promos (e.g. `udhaar.tech`).
2. In Render: your service → **Settings** → **Custom Domains** → **Add** → `udhaar.tech` and `www.udhaar.tech`. Render shows the DNS records it wants.
3. In the get.tech control panel → **DNS Management**, add exactly those records:
   - `www` → **CNAME** → `udhaar-demo.onrender.com`
   - root `@` → the **A** record IP that Render shows
4. Wait 5–30 minutes, then click **Verify** in Render. HTTPS is set up automatically.

## 4. Show your real backtest on the demo
After running `python scripts/backtest.py` with your TabPFN key on your laptop:
```powershell
copy data\backtest.json static\backtest.json
git add static\backtest.json; git commit -m "TabPFN backtest results"; git push
```
Render redeploys by itself.
