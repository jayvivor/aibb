from typing import Optional, Callable

from aibb.houseguest import DefaultRole
from aibb.events import (
    DefaultGameEvent,
    SpokenMessage,
    WhisperedMessage,
    StartConvoEvent,
    JoinConvoEvent,
    ExitConvoEvent,
    EndConvoEvent,
    Interaction,
    EndInteractionEvent,
    SchemeEvent,
    GatherEvent,
    JoinRoomEvent,
    ExitRoomEvent,
    ExclusiveCrowning,
    AdditiveCrowning,
    DeCrowning,
    NominationEvent,
    EvictionVoteEvent,
    EvictionResultEvent,
    EvictionEvent,
    VetoUseEvent,
    JuryVoteEvent,
    JuryResultEvent,
    Perspective,
)

from explorer.house import ExplorerHouse


# The sim is event-sourced: the house's room/role/convo state is maintained by
# folding events in process_event, so any historical state can be rebuilt by
# replaying history up to a timestamp. The two mutations that happen WITHOUT
# events - setup_new_season seeding the starting room, and setup_new_week
# resetting the weekly roles - are mirrored here.

STARTING_ROOM_KEY = "Living Room"

WEEKLY_RESET_ROLES = [
    DefaultRole.HOH,
    DefaultRole.POV,
    DefaultRole.NOMINEE,
    DefaultRole.DRAWN_FOR_VETO,
    DefaultRole.BLOCKBUSTER,
    DefaultRole.HAVE_NOT,
]


def get_history_items(house: ExplorerHouse) -> list[tuple]:
    # The sim thread appends to history while requests read it; retry the
    # snapshot if an insert lands mid-copy
    for _ in range(5):
        try:
            return list(house.history.items())
        except RuntimeError:
            continue
    return []


def get_actor_name(event: DefaultGameEvent) -> Optional[str]:
    for observer, perspective in event.perspective_map.items():
        if perspective == Perspective.ACTOR:
            return observer.name
    return None


def get_target_names(event: DefaultGameEvent) -> list[str]:
    return [
        observer.name for observer, perspective in event.perspective_map.items()
        if perspective == Perspective.TARGET
    ]


def serialize_event(event: DefaultGameEvent, convo_id: Optional[str]=None) -> dict:
    serialized = {
        "index": event.timestamp.index,
        "type": type(event).__name__,
        "actor": get_actor_name(event),
        "targets": get_target_names(event),
        "location": event.location.name,
        "convo_id": convo_id,
    }
    try:
        serialized["description"] = event.describe()
    except NotImplementedError:
        serialized["description"] = f"[{type(event).__name__}]"

    match event:
        case SpokenMessage() | WhisperedMessage():
            serialized["content"] = event.content
        case ExclusiveCrowning() | AdditiveCrowning() | DeCrowning():
            serialized["prize"] = event.prize.value
        case EvictionVoteEvent() | JuryVoteEvent():
            serialized["choice"] = event.choice.name
        case EvictionResultEvent() | JuryResultEvent():
            serialized["vote_tally"] = {hg.name: votes for hg, votes in event.vote_dict.items()}
        case VetoUseEvent():
            serialized["used_on"] = event.used_on.name if event.used_on else None
            serialized["replacement"] = event.replacement.name if event.replacement else None
        case JoinRoomEvent() | ExitRoomEvent():
            serialized["room"] = event.room.name
        case Interaction():
            serialized["object"] = event.object.name
            serialized["action"] = event.action.value
        case EndInteractionEvent():
            serialized["object"] = event.object.name
        case SchemeEvent():
            serialized["scratchpad"] = event.updated_memory.content
        case _:
            pass

    return serialized


def replay(house: ExplorerHouse, upto: int, keep: Optional[Callable[[DefaultGameEvent], bool]]=None) -> tuple[dict, list[dict]]:
    positions: dict[str, list[str]] = {room.name: [] for room in house.rooms}
    positions[STARTING_ROOM_KEY] = [hg.name for hg in house.cast]
    roles: dict[str, list[str]] = {role.value: [] for role in DefaultRole}
    roles[DefaultRole.ACTIVE.value] = [hg.name for hg in house.cast]
    jury: list[str] = []
    pre_jury: list[str] = []
    pre_jury_size = len(house.cast) - house.jury_size - house.num_finalists

    # Conversation grouping. StartConvoEvent carries no Conversation object, but
    # every join/exit/end does, so groups get keyed two ways: by membership
    # (member_map) and by the Conversation's hash (hash_map), merging when an
    # event proves that two keys name the same conversation.
    convo_count = 0
    groups: dict[str, dict] = {}
    member_map: dict[str, str] = {}
    hash_map: dict[str, str] = {}

    def new_group(room: str) -> str:
        nonlocal convo_count
        convo_count += 1
        group_id = f"convo_{convo_count}"
        groups[group_id] = {"members": [], "room": room, "active": True}
        return group_id

    def drop_member(name: str):
        group_id = member_map.pop(name, None)
        if group_id and name in groups[group_id]["members"]:
            groups[group_id]["members"].remove(name)

    def add_member(group_id: str, name: str):
        drop_member(name)
        if name not in groups[group_id]["members"]:
            groups[group_id]["members"].append(name)
        member_map[name] = group_id

    def merge_groups(keep_id: str, drop_id: str):
        if keep_id == drop_id:
            return
        for name in groups[drop_id]["members"]:
            add_member(keep_id, name)
        groups[drop_id]["active"] = False
        for convo_hash, group_id in hash_map.items():
            if group_id == drop_id:
                hash_map[convo_hash] = keep_id

    def resolve_group(event, member_name: Optional[str]) -> str:
        convo_hash = str(event.convo.hash_id)
        group_id = hash_map.get(convo_hash)
        member_group_id = member_map.get(member_name) if member_name else None
        if group_id and member_group_id:
            merge_groups(group_id, member_group_id)
        group_id = group_id or member_group_id or new_group(event.location.name)
        hash_map[convo_hash] = group_id
        return group_id

    kept_events: list[dict] = []
    last_week = 1

    for timestamp, events in get_history_items(house):
        if timestamp.index > upto:
            break

        # setup_new_week mutates roles silently at week boundaries
        if timestamp.week_number != last_week:
            last_week = timestamp.week_number
            roles[DefaultRole.OUTGOING_HOH.value] = [name for name in roles[DefaultRole.HOH.value]]
            for role in WEEKLY_RESET_ROLES:
                roles[role.value] = []

        for event in events:
            convo_id = None
            match event:
                case GatherEvent():
                    gathered = [name for occupants in positions.values() for name in occupants]
                    for occupants in positions.values():
                        occupants.clear()
                    positions[event.location.name] = gathered
                    # Convos end via the EndConvoEvents that precede a gather;
                    # dropping stragglers here is just a safety net
                    for name in [name for name in member_map]:
                        drop_member(name)
                case JoinRoomEvent():
                    positions[event.room.name].append(event.hg.name)
                case ExitRoomEvent():
                    if event.hg.name in positions[event.room.name]:
                        positions[event.room.name].remove(event.hg.name)
                case ExclusiveCrowning():
                    roles[event.prize.value] = [event.actor.name]
                case AdditiveCrowning():
                    if event.actor.name not in roles[event.prize.value]:
                        roles[event.prize.value].append(event.actor.name)
                case DeCrowning():
                    if event.actor.name in roles[event.prize.value]:
                        roles[event.prize.value].remove(event.actor.name)
                case StartConvoEvent():
                    convo_id = new_group(event.location.name)
                    add_member(convo_id, event.hg.name)
                    for participant in event.participants:
                        add_member(convo_id, participant.name)
                case JoinConvoEvent():
                    convo_id = resolve_group(event, member_name=None)
                    add_member(convo_id, event.hg.name)
                case ExitConvoEvent():
                    convo_id = resolve_group(event, member_name=event.hg.name)
                    drop_member(event.hg.name)
                case EndConvoEvent():
                    convo_id = resolve_group(event, member_name=None)
                    for name in [name for name in groups[convo_id]["members"]]:
                        drop_member(name)
                    groups[convo_id]["active"] = False
                case WhisperedMessage():
                    convo_id = member_map.get(event.speaker.name)
                case EvictionEvent():
                    evicted = event.evicted.name
                    for occupants in positions.values():
                        if evicted in occupants:
                            occupants.remove(evicted)
                    drop_member(evicted)
                    if len(pre_jury) < pre_jury_size:
                        pre_jury.append(evicted)
                    else:
                        jury.append(evicted)
                case _:
                    pass

            if keep and keep(event):
                kept_events.append(serialize_event(event, convo_id=convo_id))

    winners = roles[DefaultRole.WINNER.value]
    state = {
        "positions": positions,
        "roles": {role: holders for role, holders in roles.items() if holders},
        "convos": [group for group in groups.values() if group["active"] and len(group["members"]) > 1],
        "jury": jury,
        "pre_jury": pre_jury,
        "winner": winners[0] if winners else None,
    }
    return state, kept_events


def get_turn(house: ExplorerHouse, index: int) -> dict:
    state, events = replay(house, upto=index, keep=lambda event: event.timestamp.index == index)
    return {"index": index, "state": state, "events": events}


def get_houseguest_history(house: ExplorerHouse, name: str, upto: int, limit: int=500) -> dict:
    def keep(event: DefaultGameEvent) -> bool:
        return any(observer.name == name for observer in event.perspective_map)
    _, events = replay(house, upto=upto, keep=keep)
    return {"total": len(events), "events": events[-limit:]}


def get_room_history(house: ExplorerHouse, name: str, upto: int, limit: int=500) -> dict:
    _, events = replay(house, upto=upto, keep=lambda event: event.location.name == name)
    return {"total": len(events), "events": events[-limit:]}


def get_marks(house: ExplorerHouse) -> list[dict]:
    marks = []
    for timestamp, _ in get_history_items(house):
        if timestamp.turn_number == 1:
            marks.append({
                "index": timestamp.index,
                "week_number": timestamp.week_number,
                "phase_number": timestamp.phase_number,
            })
    return marks


def get_season_info(house: ExplorerHouse) -> dict:
    adjacencies = []
    for room, neighbors in house.room_layout.items():
        for neighbor in neighbors:
            pair = sorted([room.name, neighbor.name])
            if pair not in adjacencies:
                adjacencies.append(pair)
    return {
        "cast": [hg.name for hg in house.cast],
        "rooms": [
            {"name": room.name, "interactables": [interactable.name for interactable in room.interactables]}
            for room in house.rooms
        ],
        "adjacencies": adjacencies,
        "schedule": [
            {"name": week.name, "phases": [phase.name for phase in week.schedule]}
            for week in house.schedule
        ],
        "starting_room": STARTING_ROOM_KEY,
    }