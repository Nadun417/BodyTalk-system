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

## Wanted: a five-take calibration shoot

**These are calibration clips, not evaluation clips.** Their only job is to fix the numbers inside the
metrics — where "flat expression" ends and "animated" begins, and so on. The evaluation corpus is a
separate, later collection of realistic interview attempts. Do not mix the two: footage used to _set_ a
threshold cannot also be used to _test_ it.

### Why more footage is needed at all

Running the face and pose analysers over the three existing clips showed most metrics pinned at one end
of their range:

- **Every pose metric saturates.** On the two well-framed clips three quarters of all windows score
  exactly 100. Typical decent posture already sits past the "good" mark, so the metric cannot tell good
  from excellent and hands the fusion stage nothing to work with.
- **Face liveliness saturates too**, in the same direction — every window on every clip scores 100.
- **Hands are barely measurable.** Only one clip has hands in frame at all.

A threshold cannot be fixed from footage that only shows one end of the behaviour. Each metric needs to
be seen doing the thing _and_ not doing the thing, under otherwise identical conditions.

### The one rule that makes this work

**Change one thing at a time, and keep everything else identical.** Same camera, same position, same
distance, same lighting, same clothing, same background, one sitting. If posture and hand movement both
change between two takes, neither can be attributed. Slouching _while_ fidgeting produces a clip that
calibrates nothing.

### Framing, the same for all five takes

Resolution is not the limiting factor — the highest-resolution clip in the current set has the _worst_
hand detection, because the hands were simply outside the crop. Sitting further back is the whole fix.

| Property   | Value                                                                   |
| ---------- | ----------------------------------------------------------------------- |
| Format     | MP4 (H.264)                                                             |
| Resolution | 720p is ample; ≥ 480p required                                          |
| Framing    | waist-up — shoulders, torso and both hands inside the frame             |
| Duration   | 90–120 s each (60 s is the hard minimum the app accepts)                |
| Subject    | one person, face and upper body clear throughout                        |
| Lighting   | even, front-lit; avoid strong backlight                                 |
| Target     | **hands detected ≥ 70 %** of frames (the best clip so far manages 66 %) |

### The five takes

Roughly ten minutes of recording in total. Talk through anything — a rehearsed interview answer is ideal,
because natural speech drives the mouth and eyebrow movement the face metrics read.

| #   | File name            | What to do                                                                                                                                                                                                                                 | Sets the reference for                                                                                                                                                               |
| --- | -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | `calib-baseline.mp4` | Sit and answer as you genuinely would in a real interview. Do not perform good posture — behave normally.                                                                                                                                  | The **"good" end of every metric at once.** The most important take: the thresholds are currently too lenient, and this is what says where ordinary decent behaviour actually falls. |
| 2   | `calib-still.mp4`    | Hold your face deliberately neutral and unmoving for **45 s**. Then rest your hands in shot, completely still, for another **45 s**. Stay upright throughout.                                                                              | Flat expression (the one value that cannot be inferred from animated footage) and hands-present-but-motionless.                                                                      |
| 3   | `calib-animated.mp4` | Talk expressively for **45 s** — eyebrows, mouth, the odd smile. Then gesture naturally for **30 s**, then deliberately big and busy for **20 s**.                                                                                         | The animated end of expression, plus the natural and excessive ends of gesturing.                                                                                                    |
| 4   | `calib-posture.mp4`  | **45 s** slouched forward. Then **45 s** leaning to one side, one shoulder clearly lower. Then **30 s** rocking or shifting side to side. Keep hands still and visible so only posture varies.                                             | All three pose measurements at their bad end.                                                                                                                                        |
| 5   | `calib-restless.mp4` | **20 s** head turned away from the camera. **20 s** moving your head about a lot. **20 s** fidgeting with a pen or your fingers. Then touch your face 4–5 times, holding **2–3 s** each. Finally **20 s** with hands dropped out of frame. | Looking away, head movement, fidgeting, hand-to-face, and hands leaving the frame.                                                                                                   |

Durations are roughly double the minimum each behaviour needs to register, which leaves margin for a clean
interval to annotate and enough windows to see a distribution rather than a couple of readings.

### Keep a timestamp log

Write down roughly when each behaviour starts and stops as you record, into
`fixtures/calibration-notes.md`:

```
calib-posture.mp4
  0:00-0:45  slouched forward
  0:45-1:30  leaning left, right shoulder lower
  1:30-2:00  rocking side to side
```

Detected events get compared against these times, and the same log is the annotation record the
evaluation chapter needs. Written during the shoot it takes two minutes; reconstructed in December it
means watching everything again.

### Check the framing before recording all five

Ten seconds is enough to confirm the hands are in shot:

```bash
pipeline/.venv/Scripts/python.exe pipeline/run.py --detect-only \
    --video "fixtures/calib-baseline.mp4" --max-frames 60
```

The summary line reports `detectionRatePct`. If `leftHand` / `rightHand` come back under ~50 %, sit
further back and retry — before spending ten minutes on takes at a framing that will not work.

---

## Landmark caches (`fixtures/landmarks/`)

Running `--detect-only` on a clip writes `fixtures/landmarks/<clip>.landmarks.jsonl` — every detected
landmark for every sampled frame. Detection is the slow stage (roughly 0.3–0.4× real time), so it runs
once per clip and everything downstream reads the cache instead, which makes iteration instant.

These files are **git-ignored**: they are large (~5–11 MB per clip) and fully regenerable from the
footage. Each one carries a header recording the source video, both frame rates and the MediaPipe
version that produced it, so a cache file is self-describing months later. Regenerate a cache whenever
the detection stage or the analysis frame rate changes.
