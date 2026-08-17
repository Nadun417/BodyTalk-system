# Test footage

Practice-interview clips used for development and the evaluation study. **Video files are
git-ignored** (privacy + repo size) — store them here locally and document provenance/consent.

For the evaluation, two groups of footage are needed:

- **Clean footage** — well-lit, frontal, full upper body in frame.
- **Deliberately degraded footage** — hands out of frame, partial face, low light, off-angle
  camera. This is where adaptive fusion is expected to differentiate from the fixed-weight baseline.

Use self-recorded clips and/or licensed public datasets. Record consent for any footage of others.

---

## Current corpus

Detection rates measured at the default 6 fps analysis rate. `pose` is 100 % on all three, so the
pose channel is well covered; the gap is **hands**.

| Clip                                     | Resolution | Duration | face   | pose  | L hand | R hand |
| ---------------------------------------- | ---------- | -------- | ------ | ----- | ------ | ------ |
| `Medium quality.mp4`                     | 848×478    | 237.5 s  | 43.8 % | 100 % | 66.1 % | 65.1 % |
| `Video Project.mp4`                      | 1280×720   | 72.4 s   | 100 %  | 100 % | 0.0 %  | 0.5 %  |
| `Screen Recording 2026-07-24 115049.mp4` | 580×530    | 91.1 s   | 99.6 % | 100 % | 4.0 %  | 4.0 %  |

Two of these are **naturally hands-degraded** — head-and-shoulders webcam framing where hands are
almost never in shot. That is not a defect: it is free degraded-footage material for the evaluation,
and it shows the "hands leave the frame" scenario occurs in ordinary interview recordings without
needing to be staged. Keep both.

The consequence is that **only `Medium quality.mp4` exercises the hands channel at all**, so the hand
metrics currently have a single clip to calibrate against.

---

## Wanted: one wider-framed clip with hands visible

This is a **framing** requirement, not a camera-quality one. Resolution is not the limiting factor —
the 1280×720 clip above is the highest-resolution and lowest hand-detection clip in the set, because
hands were simply outside the crop. Sitting further back is the whole fix.

**Target:** waist-up framing, hands in shot whenever gesturing, **hands detected ≥ 70 %** of frames.
(`Medium quality.mp4` reaches 66 %, so that is a realistic bar.)

| Property   | Value                                                      |
| ---------- | ---------------------------------------------------------- |
| Format     | MP4 (H.264)                                                |
| Resolution | 720p is ample; ≥ 480p required                             |
| Duration   | 2–3 minutes (60 s is the hard minimum accepted by the app) |
| Subject    | one person, face and upper body clear throughout           |
| Framing    | waist-up — shoulders, torso and hands all inside the frame |
| Lighting   | even, front-lit; avoid strong backlight                    |

### Behaviours to include, and why the durations matter

Hand events only fire when a behaviour is _sustained_, so each one needs a long enough stretch on
tape to be detectable at all:

| Behaviour to perform                            | Minimum stretch needed             |
| ----------------------------------------------- | ---------------------------------- |
| Hands visible but resting still                 | **30 s** (the longest requirement) |
| Natural, moderate gesturing                     | ~30 s                              |
| Large, busy, distracting gesturing              | 10 s                               |
| Small repetitive fidgeting (pen, fingers, cuff) | 5 s                                |
| Fingertips to nose or chin                      | 2 s, a few separate times          |

Record **two takes at the same framing**: one performing the behaviours above, and one "clean" take
where the hands are visible but calm. Thresholds get set so the deliberate take fires and the clean
take does not — a single clip cannot establish both sides of that line.

### Note the timestamps while recording

Keep a rough log as you go (`0:15–0:45 still hands`, `1:10–1:25 heavy gesturing`, …). Detected events
are later compared against these manually recorded times, and the same log serves as the annotation
record for the evaluation chapter. Writing it during the shoot avoids re-watching footage months later.

### Check a candidate before committing to a full take

Ten seconds of footage is enough to confirm the framing works:

```bash
pipeline/.venv/Scripts/python.exe pipeline/run.py --detect-only \
    --video "fixtures/new clip.mp4" --max-frames 60
```

The summary line reports `detectionRatePct`. If `leftHand` / `rightHand` come back under ~50 %, sit
further back and retry before recording the whole thing.

---

## Landmark caches (`fixtures/landmarks/`)

Running `--detect-only` on a clip writes `fixtures/landmarks/<clip>.landmarks.jsonl` — every detected
landmark for every sampled frame. Detection is the slow stage (roughly 0.3–0.4× real time), so it runs
once per clip and everything downstream reads the cache instead, which makes iteration instant.

These files are **git-ignored**: they are large (~5–11 MB per clip) and fully regenerable from the
footage. Each one carries a header recording the source video, both frame rates and the MediaPipe
version that produced it, so a cache file is self-describing months later. Regenerate a cache whenever
the detection stage or the analysis frame rate changes.
