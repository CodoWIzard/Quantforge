"""Manual pause and emergency kill (§24, §35).

Two distinct states, deliberately:

- **pause**  - stop opening new positions, keep managing existing ones
- **kill**   - cancel working orders and block all new order intents

Kill must be reachable without the API being healthy. It is demonstrated explicitly in
the final internship demo (§45 step 7).
"""

from __future__ import annotations


class KillSwitch:
    def pause(self, deployment_id: str, actor: str) -> None:
        raise NotImplementedError("Week 15-16: paper execution")

    def kill(self, deployment_id: str, actor: str) -> None:
        raise NotImplementedError("Week 15-16: paper execution")

    def is_halted(self, deployment_id: str) -> bool:
        raise NotImplementedError("Week 15-16: paper execution")
