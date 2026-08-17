"""Weighting each channel by how clearly the camera could actually see it."""

from __future__ import annotations

from .base import FusionStrategy


class AdaptiveFusion(FusionStrategy):
    """Gives more say to the channels the camera could see well.

    The problem this solves is that visibility changes as a practice video plays.
    Someone might keep their face in shot the whole time but drop their hands
    below the desk halfway through. During that stretch there is no real evidence
    about their gestures, so letting the hand score carry its usual influence
    would mean judging them on something that was never recorded.

    So each channel's weight comes from its own visibility. Divide a channel's
    visibility by the total visibility of all the channels, and that is its share.
    A channel nobody can see gets a share near zero and stops affecting the
    result. The channels that are left automatically take up the slack, because
    dividing by the new total makes the shares add back up to 1.

    Worked through with the hands out of frame:

        face   visibility 0.9
        pose   visibility 0.8
        hands  visibility 0.05

        total  1.75
        face   0.9  / 1.75 = 0.51
        pose   0.8  / 1.75 = 0.46
        hands  0.05 / 1.75 = 0.03

    The hands now count for three percent instead of a third, and the score
    reflects what was actually visible.

    Still to add, once there is real footage to tune against:

      - Smoothing the visibility values across neighbouring windows. Landmark
        detection flickers frame to frame, and without smoothing the weights
        jump around and make the final score look unstable when the person has
        barely moved.
      - A minimum visibility level, below which a channel is dropped completely
        rather than kept at a tiny weight. A channel that is barely detected is
        usually reporting noise, and a small amount of noise is still noise.

    Both are specified in the project design and are not implemented here yet.
    """

    def weights(self, visibility: dict[str, float]) -> dict[str, float]:
        total = sum(visibility.values())
        # Nothing was visible at all, so there is no honest basis for weighting.
        # Return zeros rather than dividing by zero or inventing an even split.
        if total <= 0:
            return {ch: 0.0 for ch in visibility}
        return {ch: v / total for ch, v in visibility.items()}
