# Nile Pearl — Frontend (React + Vite)

Three dashboards on one sign-in:

| Role | Pages | API |
|---|---|---|
| Guest | Home, My bookings (cancel, link a booking), Book a room, Requests (+ emergency), Rewards, call with Nour | `/me/*`, `/availability`, `/bookings`, `/requests` |
| Staff | Front desk (check-in, check-out, no-show), Tickets, Live chats | `/staff/*`, `/ws/staff` |
| Admin | Overview, Revenue analysis, Nour (AI agent), Staff & discount requests | `/admin/*` |

## Run it

```bash
cd frontend
npm install
cp .env.example .env        # Windows PowerShell: copy .env.example .env
npm run dev                 # http://localhost:5173
```

### Demo data or the real backend

- `VITE_USE_MOCK=true` (default): runs on built-in demo data taken from `database/seed`
  (hotel "today" = 19 Sep 2026). No Docker or backend needed.
- `VITE_USE_MOCK=false`: calls the FastAPI backend at `VITE_API_URL` (default `http://localhost:8000`).
  Start the database (`cd database && docker compose up -d`) and the API first.
  The API already allows `http://localhost:5173` (CORS).

Restart `npm run dev` after changing `.env`.

### Demo accounts (password `NilePearl@2026`)

| Role | Email |
|---|---|
| Guest | fatma.hassan55@example.com |
| Staff | nada.samir@nilepearlhotel.example |
| Admin | admin@nilepearlhotel.example |

## Where things are

```
src/api/client.js     every API call goes through api(); token in localStorage
src/api/mock.js       demo data with the same shapes as the API
src/auth/             sign-in state, redirects each role to its dashboard
src/components/       sidebar layout, Nour call screen
src/pages/guest|staff|admin/
```

Room and hotel photos are served from the project's `static/` folder.

## For the LLM team

`src/components/NourPanel.jsx` opens a call record (`POST /calls`) and has `connectVoice()`
ready for the live voice (Gemini Live) to plug into.
