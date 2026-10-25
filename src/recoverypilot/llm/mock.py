"""Deterministic offline provider: lets the AI layer run in demos and CI with no API key."""

from __future__ import annotations

import json

from recoverypilot.llm.base import LLMProvider


class MockProvider(LLMProvider):
    """Builds a plausible summary from the prompt data without calling any model."""

    name = "mock"

    def complete(self, system: str, user: str) -> str:
        incidents = json.loads(user).get("incidents", [])
        if not incidents:
            return json.dumps({"summary": "No backup incidents need attention.", "notes": {}})
        p1 = [i for i in incidents if i["priority"] == "P1"]
        categories = sorted({i["category"] for i in incidents})
        lead = (
            f"{len(p1)} P1 incident(s) need action first"
            if p1
            else "No P1 incidents; work the queue by score"
        )
        top = incidents[0]
        summary = (
            f"[mock provider] {len(incidents)} backup incident(s) across "
            f"{len({i['client'] for i in incidents})} client(s). {lead}. "
            f"Highest: {top['rule']} on {top['host'] or top['client']} "
            f"({top['category']}, score {top['score']}). "
            f"Categories: {', '.join(categories)}."
        )
        notes = {}
        for i in incidents:
            streak = i.get("consecutive_failures") or 0
            parts = [
                f"Start with the {i['rule']} remediation steps for {i['host'] or i['client']}."
            ]
            if streak > 1:
                parts.append(f"It has failed {streak} runs in a row, so check what changed.")
            notes[i["id"]] = " ".join(parts)
        return json.dumps({"summary": summary, "notes": notes})
