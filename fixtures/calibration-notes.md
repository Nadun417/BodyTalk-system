# Calibration segment notes

Manual ground-truth labels for the calibration takes. Each range is the period during which the
behaviour was actually being performed, read off the recordings rather than the shooting plan.

Timings are accurate to about **one or two seconds**. That is deliberate: the analyser works in
one-second windows and events require a behaviour to be sustained for several seconds, so
millisecond precision would add nothing. Any analysis that reads these ranges should trim a
second or two off each end, so that frames caught mid-transition do not get counted as either
behaviour.

These are calibration labels. They are not an evaluation ground truth, and the clips they describe
must not be used to test thresholds that were set from them.

## calib-posture.mp4

| Behaviour            | Range     | Notes                                                          |
| -------------------- | --------- | -------------------------------------------------------------- |
| Slouched forward     | 0:00-0:45 | Hands still; upper body deliberately slouched forward.         |
| Side lean            | 0:45-1:31 | Lean clearly to one side, one shoulder lower than the other.   |
| Rocking side to side | 1:31-2:05 | Slow left, centre, right, centre upper-body sway; hands still. |

## calib-restless.mp4

| Behaviour           | Range     | Notes                                                          |
| ------------------- | --------- | -------------------------------------------------------------- |
| Head looking away   | 0:02-0:22 | Sustained looking away from the camera.                        |
| Head movement       | 0:22-0:44 | Noticeable repeated head movement.                             |
| Fidgeting           | 0:44-1:00 | Small repeated movement using a pen or fingers.                |
| Face touches        | 1:00-1:22 | Four or five touches, each lasting about two to three seconds. |
| Hands outside frame | 1:22-1:44 | Both hands deliberately kept outside the visible frame.        |

## calib-still.mp4, calib-animated.mp4, calib-baseline.mp4

No segment boundaries recorded yet.

`calib-baseline.mp4` does not need any: the whole clip is one continuous behaviour, which is the
point of it.

The other two do have internal structure, and the missing boundaries matter for the hands channel:

- `calib-still.mp4` was recorded as a held-neutral face followed by motionless hands. The face half
  is what set the flat-expression reference, and that worked because the whole clip is low-movement
  either way.
- `calib-animated.mp4` was recorded as expressive speech, then natural gesturing, then deliberately
  large gesturing. **Gesture activity is scored against a preferred band rather than a simple
  better-or-worse scale, so both the natural and the excessive stretches are needed as separate
  references.** Without boundaries the two cannot be told apart, and the band cannot be set.
