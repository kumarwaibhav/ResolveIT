"""Question templates from the resolveit-frames data package."""

from __future__ import annotations

import json
from pathlib import Path

from resolveit_core.schemas import UNKNOWN_ANSWER, Slot
from resolveit_core.schemas.api import Locale, OptionView, QuestionView

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "packages/resolveit-frames/data/question_templates.json"


class TemplateBank:
    def __init__(self, path: Path = DEFAULT_PATH) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        self._unknown: dict[str, str] = data["unknown_option"]
        self._by_slot: dict[Slot, dict[str, object]] = {}
        for t in data["templates"]:
            self._by_slot.setdefault(Slot(t["slot"]), t)

    def question(self, slot: Slot, locale: Locale, allowed: tuple[str, ...]) -> QuestionView:
        """Render the slot's question. Options are limited to values the bundle's theta table knows."""
        t = self._by_slot[slot]
        text = t["text"]
        assert isinstance(text, dict)
        options = [OptionView(value=v, label=v.replace("_", " ")) for v in allowed if v != UNKNOWN_ANSWER]
        options.append(OptionView(value=UNKNOWN_ANSWER, label=self._unknown[locale]))
        return QuestionView(slot=slot, template_id=str(t["id"]), text=str(text[locale]), options=options)


__all__ = ["TemplateBank"]
