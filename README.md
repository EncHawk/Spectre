# Spectre

Pre-launch QA for AI agents: inspect failures, propose fixes, and verify the result.

## Repository

- [`backend/`](backend/README.md): Python API and SDK, Postgres schema, tests, examples, deployment, and backend evidence.
- [`frontend/`](frontend/): Next.js workspace, Google sign-in, project setup, and API key management.
- [`docs.md`](docs.md): architecture and file map.
- [`hackathon.md`](hackathon.md): implementation and verification log.

## Local development

Keep backend credentials in `backend/.env` and Next server credentials in `frontend/.env.local`; both are ignored by Git. Templates live beside each service.

```sh
make setup
make migrate
make serve
# In another terminal:
cd frontend && npm install && npm run dev
```

`make test`, `make lint`, `make demo`, and `make image` delegate to the backend. Database integration tests additionally require `TEST_DATABASE_URL`; normal tests do not load production credentials.

Google OAuth client credentials and `SPECTRE_ALLOWED_EMAIL` must be configured in `frontend/.env.local` for browser sign-in. Use the same `HEALER_SERVER_TOKEN` on both services. The Python service owns `DATABASE_URL` and `OPENAI_API_KEY`; neither belongs in a browser environment variable.

The frontend defaults to the hosted backend at `https://spectreli.onrender.com`. Set `HEALER_API_URL=http://127.0.0.1:8080` to use a local backend instead. An existing deployment environment variable overrides the default; set it to the Render URL on the frontend host.
