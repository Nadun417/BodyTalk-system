"""The check that stands between a language model and the person reading the feedback.

Most of these are written from things a real model actually produced. When the whole note was
handed over for rewording, a 1.5-billion-parameter model turned "You leaned forward 0:10-0:25"
into "Lean forward 0:10-0:25", turned "a few gestures help" into "staying still might help",
and announced that a steady head "shows confidence". Those are not imagined failure modes.

The design answer was to stop showing it the facts at all: the observation, which carries the
timestamps and the claim about what was seen, never goes to the model. Only the advice
sentence does. These tests cover the second line of defence, which is refusing the answer when
it comes back wrong anyway.
"""

from __future__ import annotations

import pytest

from feedback.phrasing import Rephraser, british, is_acceptable

ADVICE = "Keep your hands visible so natural gestures come through."


class TestWhatMayBeShown:
    """Nothing reaches the user without passing every one of these."""

    def test_a_faithful_rewording_is_allowed(self):
        ok, why = is_acceptable(ADVICE, "Try keeping your hands in shot so your gestures come across.")
        assert ok, why

    def test_nothing_may_be_said_about_the_person(self):
        # The exact shape the model produced unprompted.
        ok, why = is_acceptable("A steadier head position comes across as composed.",
                                "A steady head position shows confidence.")
        assert not ok
        assert "about the person" in why

    @pytest.mark.parametrize(
        "banned",
        [
            "This will help you seem calmer to an interviewer.",
            "It makes a more professional impression.",
            "Your nervousness shows here.",
            "This affects your chances of being hired.",
            "A steady head position shows a composed demeanour.",
        ],
    )
    def test_the_whole_forbidden_vocabulary_is_refused(self, banned):
        ok, _ = is_acceptable(ADVICE, banned)
        assert not ok

    def test_a_number_that_was_not_there_before_is_refused(self):
        """Times and counts are facts. The model has no business inventing one."""
        ok, why = is_acceptable(ADVICE, "Keep your hands visible for the first 30 seconds.")
        assert not ok
        assert "number" in why

    def test_a_number_that_was_already_there_is_fine(self):
        ok, why = is_acceptable(
            "Hold that for 3 seconds.", "Try holding that for 3 seconds."
        )
        assert ok, why

    def test_an_answer_that_starts_explaining_itself_is_refused(self):
        ok, why = is_acceptable(ADVICE, "Sure! Here is a warmer version of that sentence.")
        assert not ok
        assert why == "preamble"

    def test_an_answer_that_rambles_is_refused(self):
        ok, why = is_acceptable(ADVICE, " ".join(["words"] * 40))
        assert not ok
        assert why == "too long"

    def test_an_empty_answer_is_refused(self):
        assert is_acceptable(ADVICE, "   ")[0] is False

    def test_a_question_is_refused(self):
        assert is_acceptable(ADVICE, "Have you tried keeping your hands in shot?")[0] is False

    def test_quotes_and_extra_lines_are_refused(self):
        assert is_acceptable(ADVICE, '"Try keeping your hands in shot."')[0] is False
        assert is_acceptable(ADVICE, "Try this.\nAnd also this.")[0] is False


class TestSpelling:
    """The model writes American English and this project does not."""

    def test_american_endings_are_corrected(self):
        assert british("A few gestures emphasize your points.") == (
            "A few gestures emphasise your points."
        )

    def test_capitals_survive_the_correction(self):
        assert british("Emphasize the point.") == "Emphasise the point."

    def test_ordinary_words_are_left_alone(self):
        sentence = "Try keeping your hands in shot."
        assert british(sentence) == sentence


class TestWhenThereIsNoModel:
    """The application ships without a model, so this is the ordinary case, not the edge one."""

    def test_the_original_wording_is_returned_unchanged(self, tmp_path):
        rephraser = Rephraser(model_path=tmp_path / "not-a-real-model.gguf")
        result = rephraser.rephrase(ADVICE)
        assert result.text == ADVICE
        assert result.phrasing == "template"

    def test_it_says_why_rather_than_failing_silently(self, tmp_path):
        rephraser = Rephraser(model_path=tmp_path / "not-a-real-model.gguf")
        assert rephraser.rephrase(ADVICE).rejected_because

    def test_nothing_raises(self, tmp_path):
        """A missing model must never be able to stop an analysis finishing."""
        rephraser = Rephraser(model_path=tmp_path / "not-a-real-model.gguf")
        for text in ["", "   ", ADVICE, "Sit back a little."]:
            assert rephraser.rephrase(text).text == text

    def test_empty_advice_is_left_alone(self, tmp_path):
        assert Rephraser(model_path=tmp_path / "x.gguf").rephrase("").text == ""
