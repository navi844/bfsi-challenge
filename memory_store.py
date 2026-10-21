"""A minimal in-memory conversation store, keyed by session_id, so /chat can
hold a multi-turn conversation. THIS FILE HAS NO OBSERVABILITY OF ANY KIND -
if two customers' messages get mixed up, or a session's history grows
without bound, there is currently no way to see that happening short of
printing the whole dict. session.id correlation (Step 7, stretch goal) is
what makes a multi-turn conversation findable as ONE connected story in
Jaeger instead of several disconnected traces."""
from dataclasses import dataclass, field

MAX_TURNS_DEFAULT = 8


@dataclass
class Session:
    session_id: str
    turns: list = field(default_factory=list)

    def append(self, role: str, content: str):
        self.turns.append({"role": role, "content": content})

    def truncate(self, max_turns: int = MAX_TURNS_DEFAULT):
        if len(self.turns) > max_turns:
            self.turns = self.turns[-max_turns:]


class MemoryStore:
    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def get_or_create(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            self._sessions[session_id] = Session(session_id=session_id)
        return self._sessions[session_id]

    def inspect(self, session_id: str) -> dict:
        s = self._sessions.get(session_id)
        if s is None:
            return {"found": False}
        return {"found": True, "session_id": s.session_id, "turn_count": len(s.turns), "turns": s.turns}

    def reset(self, session_id: str):
        self._sessions.pop(session_id, None)


store = MemoryStore()
