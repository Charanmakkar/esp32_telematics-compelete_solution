# NavSphere dashboard

React + TypeScript + Vite dashboard for the local ESP32 telemetry platform. The current hardware contract has **six ADC1 inputs**: GPIO32, GPIO33, GPIO34, GPIO35, GPIO36, and GPIO39. Output A is GPIO25 and output B is GPIO26.

## Run

Use Node.js 22.12+ (the repository setup script can provide portable Node). From this directory:

```powershell
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. Vite proxies `/api`, `/ws`, `/docs`, `/redoc`, and `/openapi.json` to `http://127.0.0.1:8000`. Set `BACKEND_URL` to use a different development backend. Use the root startup scripts for the integrated workflow.

For LAN preview, explicitly bind the Vite development server with `npm run dev -- --host 0.0.0.0` and configure the backend allowed origins. Production should serve `dist/` through a reverse proxy with TLS. The included Dockerfile and nginx configuration serve the SPA and forward API and WebSocket requests to `backend:8000`.

```powershell
npm test
npm run build
```

The generated `dist/` is a static production build. `npm run preview` previews that build; it is not the production API proxy.

## Behavior

- Cookie-authenticated login with backend role checks. Passwords and session tokens are not written to browser storage; the CSRF token stays in memory. The only stored preference is the display theme.
- The backend development account requires a password change before commands. No development password is embedded in frontend source.
- The overview has six separately mapped channel cards, measured ingestion frequency, backend/MQTT/database health, and independent received/persisted measurements.
- `/analytics/analog-1` through `/analytics/analog-6` support live and historical charts. Historical requests are bounded to 600 points, with whole-range statistics from the backend. Range handles provide zoom and pan. Custom ranges use browser-local time; CSV includes UTC and local timestamps.
- Live browser memory holds at most 600 samples and 50 command records. No telemetry polling is used; WebSocket reconnection uses capped exponential backoff. Dependency status is refreshed every ten seconds; active commands have bounded status polling until a backend terminal result arrives.
- Invalid channels are gaps and unavailable values. Simulator data is explicitly labelled on the overview, analytics, and controls pages.
- Commands remain pending/accepted until the backend records an applied acknowledgement. The controls use backend-confirmed state and show unknown while disconnected.
- Dark and light themes, keyboard focus outlines, reduced-motion behavior, and responsive navigation are included. Inter font files are served locally from the build.

## Configuration

Copy `.env.example` to `.env.local` only when the defaults need changing. `VITE_*` values are public build-time values: never put secrets there. Keep `VITE_API_URL` blank for a same-origin reverse proxy. Set `VITE_WS_URL` only if the WebSocket needs a separate host, including the full `/ws/v1/telemetry` path. Rebuild after changing public build-time settings.

## Implementation references

- [React effect cleanup](https://react.dev/reference/react/useEffect)
- [Vite configuration and development server](https://vite.dev/config/)
- [Recharts responsive containers](https://recharts.github.io/en-US/api/ResponsiveContainer/)
- [Recharts range brush](https://recharts.github.io/en-US/api/Brush/)

See `backend/API_CONTRACT.md` for exact request and event schemas. Frontend tests cover authentication failures, password confirmation, six-channel mapping, received/persisted separation, invalid and disconnected states, command authorization/rejection/pending behavior, history queries, custom-range validation, CSRF, and bounded live transport. Test results are recorded by the root implementation report after execution.

## Verification and manual QA

The frontend production build and 15 automated tests passed during implementation. `npm audit` reported zero known dependency vulnerabilities for the installed lockfile. These checks cover source/type correctness and component behavior; browser visual and responsive verification was not completed in this environment.

Before production use, verify the overview and all six analytics pages at desktop, tablet, and phone widths; keyboard navigation, theme contrast, graph brush zoom/pan, and CSV download; session expiration and logout; and the simulator-to-dashboard telemetry and command acknowledgement paths. Repeat the output check with the real ESP32 and LEDs before connecting loads.
