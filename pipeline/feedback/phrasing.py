"""Rewording the feedback with a small language model that runs on this machine.

The rules decide **what** to say. This decides **how** to say it, and nothing more. It cannot
introduce an observation, change a time, or reach a conclusion about anybody, because it is
never shown the part of the feedback that carries any of those things.

**Why it is built this narrowly.** The first attempt handed the model the whole note, the
observation and the advice together, and asked for a warmer version. Measured on five real
notes, four came back unusable:

- "You leaned forward 0:10-0:25" became "Lean forward 0:10-0:25, then sit back", turning a
  description of the problem into an instruction to do it.
- "Your hands stayed quite still ... a few gestures help" became "your hands stayed quite
  still, which might help", which is the opposite advice.
- "Frequent head movement between 0:00 and 0:07" became "A steady head position shows
  confidence", which both loses the time and claims something about the person that this
  project will not claim.

None of that is a fault in the model. It is a fault in asking a small model to be careful with
facts. So it is not asked to be. The observation, which holds the timestamps and the claim
about what was visible, is passed through untouched and never sent anywhere. Only the advice
sentence is reworded, and even that is checked before it is used.

**Everything here is optional and fails safe.** If the library is missing, the model file is
absent, the model is slow, or the reworded sentence does not pass its checks, the original
wording is kept. Nothing about the feedback depends on the model being there, which is what
lets the application ship without it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Where a model file is looked for, relative to the pipeline folder.
MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

#: How long to let the model spend on one sentence before giving up on it. Rewording is a
#: nicety, and a session should never sit waiting on it.
TIMEOUT_S = 8.0

#: Words that must never appear in feedback, whoever wrote it. The application describes what
#: was visible in a recording. It does not say how somebody felt, what they are like, or how
#: they would fare in an interview, and a reworded sentence that starts doing so is thrown
#: away rather than shown.
FORBIDDEN = re.compile(
    r"\b("
    r"confiden(?:t|ce)|nervous(?:ness)?|anxious|anxiety|stress(?:ed)?|uncomfortabl[ey]|"
    r"personality|character|attitude|charisma|likeab(?:le|ility)|"
    r"hire|hired|hiring|employab(?:le|ility)|candidate'?s? chances|"
    r"impress(?:ion|ive)|professional(?:ism)?|competen(?:t|ce)|"
    r"seem(?:ed|s)? (?:to be )?(?:very )?\w+|appear(?:ed|s)? (?:to be )?(?:very )?\w+|"
    r"demeanou?r|body language says|shows that you"
    r")\b",
    re.IGNORECASE,
)

#: The model writes American English by default and this project is written in British
#: English. Correcting a handful of endings is simpler and safer than trying to instruct a
#: small model into a spelling convention, and it changes wording rather than meaning.
BRITISH = {
    "emphasize": "emphasise",
    "emphasizing": "emphasising",
    "recognize": "recognise",
    "organize": "organise",
    "minimize": "minimise",
    "maximize": "maximise",
    "apologize": "apologise",
    "energize": "energise",
    "behavior": "behaviour",
    "favor": "favour",
    "color": "colour",
    "center": "centre",
    "practicing": "practising",
}

SYSTEM_PROMPT = (
    "You rewrite one sentence of interview coaching advice so it sounds warmer and more "
    "personal. You never add information. You never mention feelings, confidence, nerves, "
    "personality, or how someone would do in an interview. You reply with the rewritten "
    "sentence only, at most 20 words, and nothing else."
)

#: Shown to the model as worked examples. A small model copies a demonstrated pattern far
#: more reliably than it follows a described one, and these two carry the whole house style:
#: second person, gentle, an action rather than a verdict.
EXAMPLES = [
    (
        "Sit back a little and keep your shoulders level.",
        "Try settling back into the chair and letting your shoulders level out.",
    ),
    (
        "Keep your hands visible so natural gestures come through.",
        "Try keeping your hands in shot so your natural gestures come across.",
    ),
]


def british(text: str) -> str:
    """Put the handful of American spellings the model favours back into British English."""

    def swap(match: re.Match) -> str:
        word = match.group(0)
        replacement = BRITISH[word.lower()]
        return replacement.capitalize() if word[0].isupper() else replacement

    if not BRITISH:
        return text
    pattern = re.compile(r"\b(" + "|".join(BRITISH) + r")\b", re.IGNORECASE)
    return pattern.sub(swap, text)


def is_acceptable(original: str, candidate: str) -> tuple[bool, str]:
    """Decide whether a reworded sentence may be used, and say why if not.

    This is the part that makes the whole idea defensible. A prompt is a request; this is the
    thing that actually refuses. Every check below exists because a model can plausibly fail
    it, and the cost of a bad sentence reaching somebody is higher than the benefit of a
    slightly warmer one.

    Returns the verdict and a short reason, so a rejection can be counted and reported rather
    than disappearing silently.
    """
    text = candidate.strip()

    if not text:
        return False, "empty"

    # A rewrite is one sentence of advice. Anything much longer has started explaining,
    # listing or adding, none of which were asked for.
    if len(text.split()) > max(28, len(original.split()) + 10):
        return False, "too long"

    # Small models like to introduce their answer. That is not advice.
    if re.match(r"^(sure|here|certainly|of course|rewritten|answer)\b", text, re.IGNORECASE):
        return False, "preamble"

    if '"' in text or text.startswith("'") or "\n" in text:
        return False, "quoted or multi-line"

    forbidden = FORBIDDEN.search(text)
    if forbidden:
        return False, f"says something about the person: {forbidden.group(0)!r}"

    # No number may appear that was not in the sentence it came from. Times and counts are
    # facts, and the model has no business inventing or altering one.
    introduced = set(re.findall(r"\d+", text)) - set(re.findall(r"\d+", original))
    if introduced:
        return False, f"introduced a number: {sorted(introduced)}"

    if "?" in text:
        return False, "asks a question"

    return True, "ok"


@dataclass
class Rephrased:
    """One sentence, and an honest record of where its wording came from."""

    text: str
    #: "llm" when the model's wording is used, "template" when the original was kept.
    phrasing: str
    #: Why the model's version was not used, when it was not. Empty when it was.
    rejected_because: str = ""


class Rephraser:
    """Rewords advice, when a model is available and its answer passes the checks.

    Loading is deferred until the first sentence, so nothing pays for the model in a run that
    never uses it. If anything at all goes wrong, at load or at generation, the rephraser
    turns itself off and every caller gets the original wording back. It never raises.
    """

    def __init__(self, model_path: str | Path | None = None) -> None:
        self.model_path = Path(model_path) if model_path else _first_model_in(MODELS_DIR)
        self._llm: Any = None
        self._unavailable_because = "" if self.model_path else "no model file is installed"
        #: Counted so a run can report how often the model's wording was refused, which is
        #: the number that says whether this is working or merely running.
        self.used = 0
        self.rejected = 0

    @property
    def available(self) -> bool:
        return not self._unavailable_because

    def _load(self) -> bool:
        if self._llm is not None:
            return True
        if not self.available:
            return False
        try:
            from llama_cpp import Llama

            self._llm = Llama(
                model_path=str(self.model_path),
                n_ctx=1024,
                n_threads=4,
                verbose=False,
            )
            return True
        except Exception as exc:  # noqa: BLE001 — any failure means fall back, never crash
            self._unavailable_because = f"the model could not be loaded: {exc}"
            return False

    def rephrase(self, suggestion: str) -> Rephrased:
        """Reword one piece of advice, or hand back exactly what was given."""
        if not suggestion or not suggestion.strip():
            return Rephrased(suggestion, "template")
        if not self._load():
            return Rephrased(suggestion, "template", self._unavailable_because)

        messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for before, after in EXAMPLES:
            messages.append({"role": "user", "content": before})
            messages.append({"role": "assistant", "content": after})
        messages.append({"role": "user", "content": suggestion})

        try:
            reply = self._llm.create_chat_completion(
                messages=messages, max_tokens=60, temperature=0.2
            )
            candidate = british(reply["choices"][0]["message"]["content"].strip())
        except Exception as exc:  # noqa: BLE001 — a failed rewording is not a failed analysis
            self.rejected += 1
            return Rephrased(suggestion, "template", f"the model failed: {exc}")

        ok, why = is_acceptable(suggestion, candidate)
        if not ok:
            self.rejected += 1
            return Rephrased(suggestion, "template", why)

        self.used += 1
        return Rephrased(candidate, "llm")


def _first_model_in(folder: Path) -> Path | None:
    """Find an installed model, if there is one. Any `.gguf` file in the folder will do."""
    if not folder.is_dir():
        return None
    models = sorted(folder.glob("*.gguf"))
    return models[0] if models else None


def apply_to(events, advice, rephraser: "Rephraser | None") -> dict:
    """Reword the advice in a finished set of findings, and report what happened.

    Only the parts that are advice are touched. An event's `message` and a recommendation's
    `title` are left exactly as the rules wrote them, because those carry the times and the
    claim about what was visible, and those are not the model's to alter.

    Returns a small summary so a run can record how much of its wording came from the model
    and how often the model's wording was refused. That number is worth keeping: it is the
    difference between "a language model was used" and "a language model was used and here is
    how often it had to be overruled".
    """
    if rephraser is None or not rephraser.available:
        return {"used": False, "reworded": 0, "refused": 0, "why": _why_not(rephraser)}

    for event in events:
        result = rephraser.rephrase(event.suggestion)
        event.suggestion = result.text
        event.phrasing = result.phrasing

    for recommendation in advice:
        result = rephraser.rephrase(recommendation.body)
        recommendation.body = result.text
        recommendation.phrasing = result.phrasing

    return {
        "used": True,
        "model": rephraser.model_path.name if rephraser.model_path else None,
        "reworded": rephraser.used,
        "refused": rephraser.rejected,
        "why": "",
    }


def _why_not(rephraser: "Rephraser | None") -> str:
    if rephraser is None:
        return "not switched on"
    return rephraser._unavailable_because or "not available"
