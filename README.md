# Atlas operations dashboard

A browser-only vehicle-track dashboard built with React, TypeScript, Vite, Tailwind CSS, shadcn-style UI components, Zustand, MapLibre GL JS, and Recharts. **There is no backend, database, or API-key setup.** Included mock data is enough to run the demo.

## Prerequisites

- Git, to clone the repository once it is published.
- **Node.js 22.22.0** (the reproducible reference version in `.nvmrc`). `package.json` supports Node 22.22+ within the 22.x line.
- **npm 10.9.4** (reference package manager; npm 10.x supported). Use npm, not yarn or pnpm, with the committed `package-lock.json`.
- A modern desktop browser with WebGL enabled. Internet access is needed for npm packages and the OpenFreeMap basemap. No map API key is required. Local vehicle overlays can still render if map tiles are unavailable.
- **Optional:** Python 3.10+ only to regenerate fixtures. Python is not needed to run, build, or test the frontend.

Check versions before installing:

```sh
node --version
npm --version
```

If you already use nvm on macOS/Linux, run `nvm install` then `nvm use` in the project root. With nvm-windows, use `nvm install 22.22.0` then `nvm use 22.22.0`. A version manager is optional; an ordinary Node installation also works. If necessary, select the reference npm version with `npm install --global npm@10.9.4`.

## Fresh setup

Replace `<repository-url>` with the actual URL when the repository has been published. The destination folder below is explicit so the remaining commands work regardless of the remote repository name. Do not type the angle brackets literally.

```sh
git clone <repository-url> Roketsan-Agent
cd Roketsan-Agent
npm ci
npm run dev
```

These commands work in Windows PowerShell, macOS, and Linux terminals. If you received a ZIP instead, extract it and open a terminal in the directory containing `package.json`, then run `npm ci` and `npm run dev`.

Open **http://localhost:5173**. Stop the server with **Ctrl+C**.

`npm ci` installs the exact dependency tree from `package-lock.json`; it does not require existing `node_modules`. Keep both `package.json` and `package-lock.json` in Git. Use `npm install <package>` only when intentionally changing dependencies, and include the resulting lockfile change.

## Environment setup

**No environment variables or `.env` file are required.** There is no `.env.example` to copy and no API URL, GLM key, or secret to supply. A missing `.env` is expected. Local `.env` files are ignored in case configuration is introduced later; they must not be committed.

## Included mock data

Keep the entire `mock_data/` directory in the checkout:

| File | Purpose | Used by the current frontend |
| --- | --- | --- |
| `tracks.csv` | 16 vehicles, 400 GPS records; `track_id,time,lat,lon` | Yes |
| `zones.json` | Base location and eight named zone centers | Yes |
| `image_meta.json` | Synthetic image metadata | No; fixture included |
| `field_reports.json` | Synthetic field reports | No; fixture included |
| `mock_predictions.csv` | Synthetic detection predictions | No; fixture included |
| `ground_truth.json` | Synthetic reference labels | No; fixture included |

`src/services/tracking.ts` imports the CSV/JSON as Vite asset URLs, fetches them, and validates the data. Vite includes required assets in the build, sometimes inlining small JSON files. No manual copy to `public/`, data server, or absolute filesystem path is needed. Keep filenames and capitalization unchanged; imports use forward slashes and work on Windows too.

## Run and check commands

Run all commands from the project root:

| Command | Result |
| --- | --- |
| `npm run dev` | Development server at **http://localhost:5173** |
| `npm run typecheck` | TypeScript checks without emitting files |
| `npm test` | Data, interpolation, metrics, filters, and state unit tests |
| `npm run build` | TypeScript checks and production bundle in `dist/` |
| `npm run preview` | Serve the existing production build at **http://localhost:4173** |
| `npm run test:e2e:install` | Download Chromium for browser tests (once per machine / Playwright update) |
| `npm run test:e2e` | Browser checks; starts/stops its own server at **http://127.0.0.1:5175** |

For a production preview:

```sh
npm run build
npm run preview
```

Do not open `index.html` or `dist/index.html` directly with a `file://` URL. There is no backend command or backend port.

For the full test workflow on a fresh PC:

```sh
npm ci
npm run typecheck
npm test
npm run build
npm run test:e2e:install
npm run test:e2e
```

Playwright browsers are separate from npm packages. On a supported Linux distribution that lacks browser system libraries, run `npx playwright install-deps chromium` (may require administrator privileges), then rerun browser tests. Windows/macOS usually only need the browser download. Screenshots and reports go under ignored `test-results/` and `playwright-report/`, never a machine-specific `/tmp` path. Browser tests that validate basemap requests require network access to OpenFreeMap.

## Optional Python fixture generator

`generating_mock_data.py` is an offline, standard-library-only utility, **not a backend**. `requirements.txt` documents that there are no third-party Python dependencies. The included fixtures mean you can skip this entire section.

To regenerate, run from the project root:

```sh
python3 generating_mock_data.py
```

Windows:

```powershell
py -3 generating_mock_data.py
```

This overwrites all six files in the script's neighboring `mock_data/` directory, independent of your terminal's working directory. It uses seed 42; review generated changes before committing. Use the checked-in fixtures for an unchanged demo dataset. Image metadata does not require real image files for the current frontend.

A virtual environment is not required. If you prefer an isolated Python workflow:

macOS/Linux:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python generating_mock_data.py
deactivate
```

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python generating_mock_data.py
deactivate
```

For Windows Command Prompt, activate with `.venv\Scripts\activate.bat`. If PowerShell blocks activation scripts, activation is optional: run `.\.venv\Scripts\python.exe generating_mock_data.py` directly. Virtual environments and Python caches are ignored by Git.

## Dependency inventory

All direct runtime and development packages are declared in `package.json`; `package-lock.json` records exact direct/transitive versions and integrity hashes. No global Vite, TypeScript, or Python package is required.

### Runtime dependencies

| Package | Declared constraint |
| --- | --- |
| `@radix-ui/react-dialog` | `^1.1.23` |
| `@radix-ui/react-slot` | `^1.2.0` |
| `class-variance-authority` | `^0.7.1` |
| `clsx` | `^2.1.1` |
| `cmdk` | `^1.1.1` |
| `lucide-react` | `^0.468.0` |
| `maplibre-gl` | `^6.11.2` |
| `react` | `^19.1.0` |
| `react-dom` | `^19.1.0` |
| `recharts` | `^3.10.1` |
| `tailwind-merge` | `^3.0.0` |
| `zustand` | `^5.0.0` |

### Development dependencies

| Package | Declared constraint |
| --- | --- |
| `@playwright/test` | `^1.63.0` |
| `@tailwindcss/vite` | `^4.1.0` |
| `@types/geojson` | `^7946.0.16` |
| `@types/node` | `^22.0.0` |
| `@types/react` | `^19.1.0` |
| `@types/react-dom` | `^19.1.0` |
| `@vitejs/plugin-react` | `^4.5.0` |
| `tailwindcss` | `^4.1.0` |
| `typescript` | `~5.8.3` |
| `vite` | `^6.3.0` |
| `vitest` | `^4.1.11` |

## Troubleshooting

- **`vite` / `tsc` not found, or missing modules:** confirm you are in the directory containing `package.json`, then run `npm ci`. Do not install Vite globally.
- **Wrong Node/npm version or `EBADENGINE`:** check `node --version` and `npm --version` in this terminal and select the versions above. Reopen the terminal after changing PATH, then run `npm ci` again.
- **`npm ci` says the lockfile is inconsistent:** restore the matching `package.json` / `package-lock.json` pair from the same revision. For intentional dependency edits, maintainers should regenerate the lockfile with npm 10 and commit both files. Do not delete the lockfile as a fresh-setup workaround.
- **Port already in use:** dev/preview use strict ports instead of silently selecting another one. Stop the process using the port or run `npm run dev -- --port 5174` / `npm run preview -- --port 4174`, then use that printed URL. Browser tests reserve port 5175; stop any conflicting server before testing.
- **Mock data missing or malformed:** restore `mock_data/` from the checkout and confirm file names/case. The CSV header must be `track_id,time,lat,lon`; zones must include the base and zone centers. Use the UI's Retry action after fixing the source. Do not regenerate fixtures just to start the app.
- **Blank map or missing background:** enable browser hardware acceleration/WebGL and allow network requests to `tiles.openfreemap.org`. Tile errors do not mean the local CSV is missing.
- **Playwright executable or library missing:** run `npm run test:e2e:install`; on supported Linux, also install the system libraries as described above.
- **Missing `.env`:** no action needed; this application does not currently read one.
- **Large bundle warning during build:** currently expected from the map/chart libraries; it is an advisory, not a failed build or TypeScript error.

## Project guide

See [workspace behavior and architecture](docs/WORKSPACE.md) for playback, interpolation, filters, selection, follow mode, metrics, and shortcuts. Setup and version instructions in this README are authoritative.

There is no Git remote configured in the supplied workspace yet. No commit or push is part of this setup work. When publishing later, include source, configuration, lockfile, documentation, and all six mock fixtures; exclude dependencies, build outputs, test artifacts, local env files, and virtual environments.
