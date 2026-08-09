# AI News Agency — Web Dashboard (Task 5.4)

Next.js 14 (App Router + TypeScript) frontend for the FastAPI backend in `../api/`.

## Pages

- `/` — overview: digest stats, quality metrics, API health, live via WebSocket
- `/agents` — per-agent success rate & latency (`/api/agents/performance`)
- `/digests` — recent digest history (`/api/digests`)
- `/ceo` — chat with ALEX (Ask or issue a Command), plus a status-report button
- `/config` — current digest mode / feed count / lookback window, with a daily↔weekly switch

## Run locally

```bash
# 1. Backend (from repo root)
pip install -r api/requirements.txt
uvicorn api.main:app --reload --port 8000

# 2. Frontend (from web/)
cp .env.local.example .env.local   # points at http://localhost:8000
npm install
npm run dev
```

Open http://localhost:3000.

## Deploy

**Frontend (Vercel, recommended for Next.js):**
```bash
npm i -g vercel
vercel                      # first deploy, follow prompts
vercel env add NEXT_PUBLIC_API_URL   # set to your deployed API URL
vercel --prod
```
Netlify works too: `netlify deploy --build` with the Next.js runtime plugin.

**Backend (any host that runs a long-lived process):**
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```
Put this behind a process manager (systemd, pm2, or a platform like Railway/Fly.io/Render).
Set `NEXT_PUBLIC_API_URL` on the frontend to this backend's public URL, and lock down
`allow_origins` in `api/main.py`'s CORS middleware to the deployed frontend origin.
