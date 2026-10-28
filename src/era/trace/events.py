import json
from era.models.entities import DecisionEvent


def render_events(events: list[DecisionEvent]) -> str:
    return "\n".join(json.dumps(
        {"event_type": event.event_type, **event.details},
        sort_keys=True,
    ) for event in events)
