import json
import os

def load_replay_events():
    path = os.path.join(os.path.dirname(__file__), "replay", "events.json")
    if not os.path.exists(path):
        raise ValueError("events.json not found")
    with open(path, "r") as f:
        return json.load(f)

def get_replay_event(number):
    events = load_replay_events()
    # 1-indexed
    if type(number) is not int or number < 1 or number > len(events):
        raise ValueError("Invalid replay event number")
    return events[number - 1]
