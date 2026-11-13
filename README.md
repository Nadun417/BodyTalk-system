# BodyTalk

BodyTalk is a Windows desktop app that helps people practise for interviews. You upload a practice video you recorded earlier, and the app gives you feedback on your body language with timestamps, so you can see where each thing happened. It works fully offline, so the video and the results stay on your computer.

This is my final-year project for the BEng (Hons) Software Engineering.

## How it works

1. You upload a practice clip.
2. The app extracts frames from the video on your machine.
3. MediaPipe Holistic finds the landmarks: 468 for the face, 33 for the pose and 21 for each hand.
4. Three channel analysers run in parallel on those landmarks.
5. Their results are combined using confidence-weighted adaptive signal fusion.
6. The feedback engine turns the fused results into feedback.
7. You see everything on an interactive dashboard and can export it as a PDF report.

Step 5 is the main research part of the project. There is also a fixed fusion method that I use as the baseline to compare the adaptive one against.

## Tech stack

The project uses two runtimes. The desktop app is Electron with Node and TypeScript (in `src/`). It handles the UI, IPC, the SQLite database, file access and PDF export, and it controls the overall flow. The analysis pipeline is Python 3.11/3.12 with MediaPipe (in `pipeline/`), and the Electron main process starts it as a separate process.

Note: MediaPipe doesn't have wheels for Python 3.14, so use a separate Python 3.11 or 3.12 venv for the pipeline, not your system Python if that one is newer. The `--selftest` option only uses the standard library, so you can test the app's bridge and UI before MediaPipe is installed.

## Requirements

- Node.js 20 or newer (built on 24.x) and npm
- Python 3.11 or 3.12 for the real pipeline
- Windows 10 or 11

You don't need C++ build tools. SQLite runs through `sql.js` (WASM), so `npm install` doesn't compile anything native.

## Setup

```bash
# 1. JS/TS side
npm install

# 2. Python pipeline (use a 3.11/3.12 interpreter)
powershell -ExecutionPolicy Bypass -File pipeline/setup.ps1
```

`setup.ps1` looks for a Python version that the analysis libraries support, creates a venv in `pipeline/.venv` and installs the packages. It's fine to run it again. If everything is already installed, it just checks and tells you, and doesn't download anything a second time.

To set it up manually instead:

```bash
py -3.11 -m venv pipeline/.venv
pipeline/.venv/Scripts/pip install -r pipeline/requirements.txt
```

## Installing the packaged app

The installer includes the analysis code but not Python. Bundling Python would add several hundred MB, and it would also need a matching interpreter version. So after installing, run `setup.ps1` once from the app's `resources/pipeline` folder.

Until you do that, the app still opens and you can still view sessions that were analysed somewhere else, but if you try to analyse a new video it will tell you the analysis software is missing. This setup step is the only time anything gets downloaded. The app itself never uses the internet.

## Running and building

```bash
npm run dev            # launch the app with HMR
npm run build          # production build
npm run package        # build + Windows NSIS installer (dist/)
npm run typecheck      # tsc across node + web projects
npm run test           # vitest (TS unit tests)
npm run format         # prettier --write
```

### Testing the pipeline bridge without MediaPipe

```bash
# stdlib only, works on any Python (even 3.14)
python pipeline/run.py --selftest --fusion adaptive
python pipeline/run.py --selftest --fusion fixed      # the comparison baseline
pytest                                                # fusion unit tests (tests/pipeline/, in the venv)
```

You can also do this inside the app. On the Home screen, choose "Run pipeline self-test (dev)". It goes through the bridge, the database and the dashboard, so you can check the progress bar, the weight-over-time chart and the timestamped insights.

## Project structure

```
src/
  main/        Electron main process (backend): window/security, IPC, db (SQLite), fs, pipeline bridge, services
  preload/     contextBridge, the only way between the renderer and the backend (window.bodytalk)
  renderer/    React + Vite UI (Home/History, Upload, Processing, Dashboard, Report)
  shared/      IPC channel names and domain types used by both sides (these mirror the SQLite schema)
pipeline/      Python AI pipeline: run.py, pipeline.py, frames, detection, analysers, fusion, feedback, serialisation
tests/         pdfReport.test.ts (vitest) and tests/pipeline/ (pytest)
fixtures/      test footage (git-ignored)
```

## Design rules

These are the main rules the code follows.

- The app is offline only. Nothing goes to the network while it's running. Practice videos are personal, and the simplest way to make sure they never leave the computer is to not give the app any way to send them.
- The UI can't read files, access the database or start programs by itself. It sends a request through the preload bridge, and the main process decides what to do with it.
- The adaptive and fixed fusion methods share the same interface, so analysing a video with the other method only means changing one object. Keep the fixed method, because it's the baseline for the comparison.
- Every window keeps its `visibility` and `weight` values. The charts and the comparison are both built from them, and they are the only record of what the weighting actually did.
- Feedback only describes what was visible in the video. It doesn't make claims about how someone felt, what their personality is, or how they would do in a real interview, because none of that can be worked out from landmarks.
