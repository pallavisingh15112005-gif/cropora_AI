# Cropora AI

Kisan ke liye fasal ka mandi bhav batane wali website. Data data.gov.in (Agmarknet) se roz aata hai.

## Files

- `index.html`: chat screen. `data/prices.json` se live bhav padhta hai.
- `login-page.html`, `project.html`: demo pages.
- `data/fetch_mandi.py`: government API se bhav laata hai aur `data/prices.json` likhta hai.
- `.github/workflows/update-prices.yml`: roz subah GitHub Actions se fetch chalata hai aur file commit karta hai.

## Online setup (GitHub Pages)

1. GitHub par nayi **public** repository banao, jaise `cropora-ai` (ya jo naam aap chaho).
2. Is folder ki sari files repository mein upload karo (`index.html`, `data/`, `.github/`, etc.).
3. **Secret add karo:** repo → Settings → Secrets and variables → Actions → New repository secret.
   - Name: `DATA_GOV_API_KEY`
   - Value: data.gov.in se li hui API key (chat mein mat dalna)
4. **Pages on karo:** Settings → Pages → Source: "Deploy from a branch", Branch: `main`, folder: `/ (root)`.
5. **Pehli baar fetch chalao:** Actions tab → "Update mandi prices" → Run workflow.
   Ye `data/prices.json` bana dega aur commit karega.
6. Website ka link Pages settings mein dikhega, jaise `https://USERNAME.github.io/REPO-NAAM/`.

Ab workflow roz apne aap chalega, aur site ko naya data milta rahega.

## Dhyan dene wali baatein

- Ye demo ke liye hai. Login check browser mein hota hai, asli security nahi hai.
- Agmarknet data roz ek baar update hota hai, isliye "real time" ka matlab "aaj ka latest" hai.
- Agar data.gov.in API abhi enable na ho, to Actions fail hoga. Pehle resource ka API approve hona chahiye.
