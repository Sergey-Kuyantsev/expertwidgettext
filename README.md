# expertwidgettext

Text-only FastAPI backend for the «Эксперт Новострой» chat widget (Yandex AI Studio).

## Timeweb App Platform

1. Connect this repository.
2. Set environment variables from `.env.example` (put the real `YANDEX_API_KEY` in the panel).
3. Default start: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## Endpoints

- `GET /api/health`
- `POST /api/welcome` — `{ "sessionId": "..." }`
- `POST /api/chat` — `{ "sessionId": "...", "message": "..." }`
- `DELETE /api/chat/{session_id}`

In the Tilda widget set:

```js
var BACKEND_URL = "https://YOUR-TIMEWEB-HOST";
```

No trailing slash.
