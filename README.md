# BodyTalk

A privacy-first, **fully-offline** Windows desktop app that gives interview candidates
**timestamped body-language feedback** from a pre-recorded practice video. BEng (Hons) Software
Engineering final-year project. Nothing ever leaves the device.

Pipeline: upload a practice clip → on-device frame extraction → **MediaPipe Holistic** (face 468 /
pose 33 / hands 21×2) → three parallel channel analysers → **confidence-weighted adaptive signal
fusion** (the research novelty) → feedback engine → interactive dashboard → PDF report.

## Two runtimes

| Runtime                          | Used for                                        | Notes                                    |
| -------------------------------- | ----------------------------------------------- | ---------------------------------------- |
| **Node + TypeScript** (Electron) | UI, IPC, SQLite, filesystem, PDF, orchestration | `src/`                                   |
| **Python 3.11/3.12 + MediaPipe** | the AI analysis pipeline                        | `pipeline/`, spawned by the main process |

> ⚠️ **MediaPipe has no wheels for Python 3.14.** Use a pinned **Python 3.11 or 3.12** venv for the
> pipeline (separate from any newer system Python). The `--selftest` path is stdlib-only, so the
> app's bridge/UI can be exercised before MediaPipe is installed.

## Prerequisites

- Node.js ≥ 20 (developed on 24.x), npm
- Python 3.11 or 3.12 (for the real pipeline)
- Windows 10/11. No C++ build tools needed — SQLite runs as `sql.js` (WASM), so `npm install`
  has no native compilation step.

## Setup

```bash
# 1. JS/TS side
npm install

# 2. Python pipeline (use a 3.11/3.12 interpreter)
py -3.11 -m venv pipeline/.venv
pipeline/.venv/Scripts/pip install -r pipeline/requirements.txt
```

## Run / build

```bash
npm run dev            # launch the app with HMR
npm run build          # production build
npm run package        # build + Windows NSIS installer (dist/)
npm run typecheck      # tsc across node + web projects
npm run test           # vitest (TS unit tests)
npm run format         # prettier --write
```

### Verify the pipeline bridge without MediaPipe

```bash
# stdlib only — works on any Python, even 3.14
python pipeline/run.py --selftest --fusion adaptive
python pipeline/run.py --selftest --fusion fixed      # the comparison baseline
pytest                                                # fusion unit tests (tests/pipeline/, in the venv)
```

In the app, **Home → "Run pipeline self-test (dev)"** drives the full
bridge → DB → dashboard path (progress bar, weight-over-time chart, timestamped insights).

## Project structure

```
src/
  main/        Electron main process (backend): window/security, ipc, db (SQLite), fs, pipeline bridge, services
  preload/     contextBridge — the only renderer↔backend door (window.bodytalk)
  renderer/    React + Vite UI (Home/History, Upload, Processing, Dashboard, Report)
  shared/      ipc channel names + cross-tier domain types (mirror the SQLite schema)
pipeline/      Python AI pipeline: run.py · pipeline.py · frames · detection · analysers · fusion · feedback · serialisation
tests/         pdfReport.test.ts (vitest)  ·  tests/pipeline/ (pytest)
fixtures/      test footage (git-ignored)
```

## Architecture rules (non-negotiable)

- **Offline only.** Nothing reaches the network while the app is running. Practice videos are
  personal, and the simplest way to promise none of it leaves the machine is to give it nowhere
  to go.
- **The interface asks, the backend acts.** The interface cannot read files, reach the database
  or start programs. It sends a message and something on the other side decides what to do.
- **Either fusion method can be swapped for the other.** They sit behind one interface, so
  analysing a video both ways changes one object and nothing else. The fixed version is not
  spare code; without it there is nothing to compare against.
- **Keep `visibility` and `weight` for every window.** They are the only record that the
  weighting did anything, and the charts and the comparison are both built from them.
- **Describe what was visible, nothing else.** No claims about how someone felt, what they are
  like, or how they would fare in a real interview. None of that can be told from landmarks.
