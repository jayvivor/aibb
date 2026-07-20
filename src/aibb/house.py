from __future__ import annotations
from pydantic import Field
from typing import Optional, Iterable

from aibb.base import House
from aibb.competition import DefaultCompetition
from aibb.houseguest import DefaultHouseguest, DefaultRole
from aibb.room import InteractiveRoom
from aibb.week import (
    DefaultWeek, 
    DefaultPhase, 
    CompPhase, 
    OpenPhase, 
    EvictionVotePhase,
    SleepPhase,
    NominationPhase,
    CeremonyPhase,
)
from aibb.move import (
    DefaultMove,
    WhisperMove,
    StartConversationMove,
    JoinConversationMove,
    ExitConversationMove,
    ChangeRoomMove,
    InteractMove, 
    SpeakMove,
    EvictionVoteMove,
    SchemeMove,
    NominationMove,
)
from aibb.turn import DefaultTurn
from aibb.events import (
    Conversation,
    DefaultTimestamp,
    DefaultGameEvent,
    SpokenMessage,
    WhisperedMessage,
    JoinRoomEvent,
    ExitRoomEvent,
    StartConvoEvent,
    JoinConvoEvent,
    ExitConvoEvent,
    EndConvoEvent,
    EvictionVoteEvent,
    EvictionResultEvent,
    Interaction,
    ExclusiveCrowning,
    AdditiveCrowning,
    DeCrowning,
    Perspective,
    EndWeek,
)
from aibb.response import (
    OpenMoveResponse, 
    EvictionVoteMoveResponse, 
    SchemeMoveResponse,
    NominationMoveResponse,
)
from aibb.prompts import BASE_PROMPT_TEMPLATE, MESSAGE_TEMPLATE, RULES


__all__ = [
    "DefaultHouse",
]


class DefaultHouse(House[DefaultHouseguest, InteractiveRoom, DefaultWeek, DefaultTurn]):

    name: str = "Big Brother House"
    room_layout: dict[InteractiveRoom, list[InteractiveRoom]] = Field(default_factory=dict, exclude=True)
    pre_jury: list[DefaultHouseguest] = Field(default_factory=list)
    jury: list[DefaultHouseguest] = Field(default_factory=list)
    jury_size: int = 7
    num_finalists: int = 2
    role_dict: dict[DefaultRole, list[DefaultHouseguest]] = Field(default_factory=dict)
    room_dict: dict[InteractiveRoom, list[DefaultHouseguest]] = Field(default_factory=dict)
    convos: list[Conversation] = Field(default_factory=list)
    history: dict[DefaultTimestamp, list[DefaultGameEvent]] = Field(default_factory=dict)

    # current_week_cache: Optional[DefaultWeek] = Field(default=None, exclude=True)
    # current_phase_cache: Optional[DefaultPhase] = Field(default=None, exclude=True)

    room_registry_cache: Optional[dict[str, InteractiveRoom]] = Field(default=None, exclude=True)
    hg_registry_cache: Optional[dict[str, DefaultHouseguest]] = Field(default=None, exclude=True)

    # Registries
    @property
    def room_registry(self):
        if not self.room_registry_cache:
            self.room_registry_cache = {room.name: room for room in self.rooms}
        return self.room_registry_cache
    
    @property
    def hg_registry(self):
        if not self.hg_registry_cache:
            self.hg_registry_cache = {hg.name: hg for hg in self.cast}
        return self.hg_registry_cache
    

    def describe(self):
        raise NotImplementedError
    

    def filter_cast_by_roles(self, roles: Iterable[DefaultRole]):
        found_hgs: set[DefaultHouseguest] = set()
        for role in roles:
            found_hgs.update(self.role_dict[role])
        return list(found_hgs)
        # return list(set(hg for hg in self.cast if any(role in hg.roles for role in roles)))

    def get_hg_room(self, hg: DefaultHouseguest) -> InteractiveRoom:
        for room, members in self.room_dict.items():
            if hg in members:
                return room
        raise KeyError(f"hg {hg.name} not found in any room.")
    

    def get_hg_conversation(self, hg: DefaultHouseguest) -> Conversation | None:
        for convo in self.convos:
            if hg in convo.active_participants:
                return convo
        return None
    

    def get_base_perspective_map(self, move: DefaultMove, location: InteractiveRoom) -> dict[DefaultHouseguest, Perspective]:
        ## Perspectives
        base_perspective_map: dict[DefaultHouseguest, Perspective] = {}
        ### Actor - simplest
        actor = move.actor
        base_perspective_map.update({actor: Perspective.ACTOR})

        ### Targets - contextual

        ### Witnesses - generally, anyone present in the room
        base_witnesses = [hg for hg in self.room_dict[location] if hg != actor]
        base_perspective_map.update({hg: Perspective.WITNESS for hg in base_witnesses})

        ### Snoopers - generally, anyone in a neighboring room
        neighbors = [room for room in self.rooms if location in self.room_layout[room]]
        base_snoopers = [hg for room in neighbors for hg in self.room_dict[room]]
        base_perspective_map.update({hg: Perspective.SNOOP for hg in base_snoopers})

        return base_perspective_map

    
    def get_prompt(self) -> str:
        ...

    def get_user_message(self) -> str:
        ...


    def process_event(self, event: DefaultGameEvent):
        
        match event:

            # ROLE MANAGEMENT
            case ExclusiveCrowning():
                self.role_dict[event.prize] = [event.actor]
            case AdditiveCrowning():
                self.role_dict[event.prize].extend(event.actors)
                # Just in case - prevent duplicates
                self.role_dict[event.prize] = list(set(self.role_dict[event.prize]))
            case DeCrowning():
                for actor in event.actors:
                    self.role_dict[event.prize].remove(actor)
            
            # ROOM MANAGEMENT
            case JoinRoomEvent():
                self.room_dict
            
    
    def setup_new_week(self):
        self.role_dict.update({DefaultRole.OUTGOING_HOH:[hg for hg in self.role_dict[DefaultRole.HOH]]})
        self.role_dict.update({DefaultRole.HOH:[]})
        self.role_dict.update({DefaultRole.POV:[]})
        self.role_dict.update({DefaultRole.NOMINEE:[]})
        self.role_dict.update({DefaultRole.DRAWN_FOR_VETO:[]})
        self.role_dict.update({DefaultRole.BLOCKBUSTER:[]})
        self.role_dict.update({DefaultRole.HAVE_NOT:[]})


    def setup_new_season(self, starting_room_key: str="Living Room"):
        # Put everyone in the starting room
        self.room_dict = {room:[] for room in self.rooms}
        self.room_dict.update({self.room_registry[starting_room_key]:[hg for hg in self.cast]})
        self.role_dict = {role:[] for role in DefaultRole}
        self.role_dict.update({DefaultRole.ACTIVE:[hg for hg in self.cast]})


    def process_phase(self, phase: DefaultPhase, timestamp: DefaultTimestamp) -> list[DefaultGameEvent]:
        
        events = []

        match phase:
            case CompPhase():
                # Create competition
                disallowed_players = self.filter_cast_by_roles(phase.disallowed_roles)
                allowed_players = self.filter_cast_by_roles(phase.allowed_roles)
                competitors = [hg for hg in allowed_players if hg not in disallowed_players]
                comp = DefaultCompetition(
                    ruleset=phase.comp_ruleset,
                    competitors=competitors,
                )

                # Run competition
                ## TODO: SHOULD get the effort/stats from each hg first instead, THEN run w/ that context
                ## For now, it's purely random results anyway
                results = comp.run_comp()

                # Crown the winner
                ## Assume every active player gets to see the win
                perspective_map = {
                    hg: Perspective.WITNESS
                    for hg in self.role_dict[DefaultRole.ACTIVE]
                }
                perspective_map.update({results.winner:Perspective.ACTOR})

                crown_event = ExclusiveCrowning(
                            timestamp=timestamp,
                            location=self.room_registry["Backyard"],
                            perspective_map=perspective_map,
                            prize=phase.prize,
                        )
            
                events.append(crown_event)
            
            case EvictionVotePhase():
                # Get voters
                active_players = self.filter_cast_by_roles([DefaultRole.ACTIVE])
                noms = self.filter_cast_by_roles([DefaultRole.NOMINEE])
                hoh = self.filter_cast_by_roles([DefaultRole.HOH])

                voters = [hg for hg in active_players if hg not in noms + hoh]
                tiebreaker = [hg for hg in hoh]
                
                vote_responses : list[EvictionVoteMoveResponse] = [
                    hg.get_move(
                        prompt=self.get_prompt(),
                        user_message=self.get_user_message(),
                        response_type=EvictionVoteMoveResponse,
                    ) for hg in voters
                ]  # type: ignore

                vote_moves: list[EvictionVoteMove] = [
                    response.get_move()
                    for response in vote_responses
                ]

                vote_events = []
                
                for move in vote_moves:
                    vote_events.append(EvictionVoteEvent(
                        timestamp=timestamp,
                        location=self.room_registry["Diary Room"],
                        perspective_map={
                            move.actor: Perspective.ACTOR,
                        },
                        choice=move.choice,
                    ))

                # TODO: Ties n whatnot

            case OpenPhase():
                # The logic:
                # First, speak anything that is meant for the room to hear.
                # Second, if anyone leaves a convo or room, invalidate any relevant whispers.
                # Third, if anyone joins a convo, invalidate any 'careful' whispers.
                # Fourth, ensure that all convos are still actually active.
                # Fifth, whisper anything that is meant for the conversationalists to hear.
                # Last, handle any low-priority moves
                responses = {
                    hg: hg.get_move(
                        prompt=self.get_prompt(),
                        user_message=self.get_user_message(),
                        response_type=OpenMoveResponse,
                    ) for hg in self.filter_cast_by_roles([DefaultRole.ACTIVE])
                }
                
                moves = [
                    response.get_move() for response in responses.values()
                ]

                unavailable_hgs: set[DefaultHouseguest] = set()
                
                skippable_moves = []
                round_1_moves = {move for move in moves}
                round_2_moves: set[
                    WhisperMove | StartConversationMove | 
                    JoinConversationMove | ExitConversationMove | ChangeRoomMove] = set()
                for move in round_1_moves: # First, speak anything that is meant for the room to hear.
                    location = self.get_hg_room(move.actor)
                    base_perspective_map = self.get_base_perspective_map(move, location)
                    actor_convo = self.get_hg_conversation(move.actor)

                    match move:
                        case InteractMove():
                            interaction_event = Interaction(
                                timestamp=timestamp,
                                location=location,
                                perspective_map=base_perspective_map,
                                object=move.interactable,
                                action=move.action,
                            )
                            events.append(interaction_event)
                        case SpeakMove():
                            
                            if actor_convo:
                                targets = [p for p in actor_convo.active_participants if move.actor != p]
                                base_perspective_map.update({t: Perspective.TARGET for t in targets})
                            speak_event = SpokenMessage(
                                timestamp=timestamp,
                                location=location,
                                perspective_map=base_perspective_map,
                                content=move.content,
                            )
                            events.append(speak_event)
                        case _:
                            round_2_moves.add(move)

                # Second, if anyone leaves a convo or room, invalidate any relevant whispers.

                whispers: set[WhisperMove] = set()
                whisper_map: dict[DefaultHouseguest, Conversation] = {}
                for whisper in whispers:
                    for conversation in self.convos:
                        if whisper.actor in conversation.active_participants:
                            whisper_map[whisper.actor] = conversation

                joins: list[JoinConversationMove | ChangeRoomMove] = []
                exits: list[ExitConversationMove | ChangeRoomMove] = []

                final_round_moves: set[StartConversationMove] = set()
                for move in round_2_moves:  # Categorize
                    match move:
                        case JoinConversationMove():
                            joins.append(move)
                        case ExitConversationMove():
                            exits.append(move)
                        case ChangeRoomMove():
                            joins.append(move)
                            exits.append(move)
                        case WhisperMove():
                            whispers.add(move)
                        case _:
                            final_round_moves.add(move)


                changed_convos: dict[Conversation, DefaultHouseguest] = {}   

                for exit_move in exits:  # Leave all rooms and convos
                    location = self.get_hg_room(exit_move.actor)
                    base_perspective_map = self.get_base_perspective_map(exit_move, location)
                    actor_convo = self.get_hg_conversation(exit_move.actor)
                    match exit_move:
                        case ExitConversationMove():
                            convo = exit_move.conversation

                            changed_convos[convo] = exit_move.actor
                            convo.active_participants.remove(exit_move.actor)
                            exit_convo_event = ExitConvoEvent(
                                timestamp=timestamp,
                                location=location,
                                perspective_map=base_perspective_map,
                                convo=convo,
                            )
                            events.append(exit_convo_event)
                            
                        case ChangeRoomMove():
                            old_room = self.get_hg_room(exit_move.actor)
                            new_room = exit_move.room

                            unavailable_hgs.add(exit_move.actor)

                            # Both rooms will witness
                            base_perspective_map.update({w: Perspective.WITNESS for w in self.room_dict[new_room]})
                            exit_event = ExitRoomEvent(
                                timestamp=timestamp,
                                location=location,
                                room=old_room,
                                perspective_map=base_perspective_map,
                                )
                            events.append(exit_event)

                            join_event = JoinRoomEvent(
                                timestamp=timestamp, 
                                location=location,
                                room=new_room,
                                perspective_map=base_perspective_map,
                                )
                            events.append(join_event)

                            if actor_convo:
                                changed_convos[actor_convo] = exit_move.actor
                                exit_convo_event = ExitConvoEvent(
                                    timestamp=timestamp,
                                    location=location,
                                    convo=actor_convo,
                                    perspective_map=base_perspective_map,
                                )
                                events.append(exit_convo_event)
                
                for whisper in whispers:
                    whisperer = whisper.actor
                    convo = None
                    for c in self.convos:
                        if whisperer in c.active_participants:
                            convo = c
                            break
                    if convo in changed_convos:
                        # Skip the whisper; someone left
                        skippable_moves.append(whisper)
                

                # Third, if anyone joins a convo, invalidate any 'careful' whispers or start attempts.

                for join_move in joins:
                    location = self.get_hg_room(join_move.actor)
                    base_perspective_map = self.get_base_perspective_map(join_move, location)
                    actor_convo = self.get_hg_conversation(join_move.actor)
                    match join_move:
                        case JoinConversationMove():
                            joiner = join_move.actor
                            convo = join_move.conversation

                            unavailable_hgs.add(joiner)
                            changed_convos[convo] = joiner
                            join_convo_event = JoinConvoEvent(
                                convo=convo,
                                timestamp=timestamp,
                                location=location,
                                perspective_map=base_perspective_map,
                                )
                            events.append(join_convo_event)

                for whisper in whispers:
                    if whisper.allow_join:  # If joining is allowed, don't worry about it
                        continue
                    whisperer = whisper.actor
                    convo = None
                    for c in self.convos:
                        if whisperer in c.active_participants:
                            convo = c
                            break
                    if convo in changed_convos:
                        # Skip the whisper; someone left
                        skippable_moves.append(whisper)

                # Fourth, ensure that all convos are still actually active.

                for convo in changed_convos:
                    if not convo.is_active():
                        end_convo_event = EndConvoEvent(
                            timestamp=timestamp,
                            location=convo.room,
                            convo=convo,
                            perspective_map={
                                witness: Perspective.WITNESS
                                for witness in self.room_dict[convo.room]
                            }
                        )
                        events.append(end_convo_event)

                for whisper in whispers:
                    whisperer = whisper.actor
                    if not whisper_map[whisperer].is_active():
                        skippable_moves.append(whisper)

                # Fifth, whisper anything that is meant for the conversationalists to hear.

                for whisper in skippable_moves:  # Remove the accumulated skipped ones
                    whispers.remove(whisper)
                
                for whisper in whispers:
                    location = self.get_hg_room(whisper.actor)
                    base_perspective_map = self.get_base_perspective_map(whisper, location)
                    actor_convo = self.get_hg_conversation(whisper.actor)
                    if not actor_convo:
                        raise ValueError(f"{whisper.actor.name} tried to whisper, but is not part of a conversation.")

                    # Whispers are too quiet for eavesdroppers to notice
                    for hg, pers in base_perspective_map.items():
                        if pers == Perspective.SNOOP:
                            base_perspective_map.pop(hg)

                    base_perspective_map.update({t: Perspective.TARGET for t in actor_convo.active_participants if t != whisper.actor})

                    whisper_event = WhisperedMessage(
                        content=whisper.content,
                        timestamp=timestamp,
                        location=location,
                        perspective_map=base_perspective_map,
                    )
                    events.append(whisper_event)

                # Last, any unmentioned events

                for move in final_round_moves:
                    location = self.get_hg_room(move.actor)
                    base_perspective_map = self.get_base_perspective_map(move, location)
                    match move:
                        case StartConversationMove():
                            all_participants = [move.actor] + move.participants

                            # Skip anyone who's left the room or joined another convo already
                            if any(p in unavailable_hgs for p in all_participants):
                                continue

                            base_perspective_map.update({t: Perspective.TARGET for t in move.participants})

                            start_convo_event = StartConvoEvent(
                                timestamp=timestamp,
                                location=location,
                                perspective_map=base_perspective_map,
                            )
                            events.append(start_convo_event)

                        case _:
                            raise ValueError("Somehow, there's a move type in the Open phase that hasn't been covered.")
            case SleepPhase():
                for hg in self.role_dict[DefaultRole.ACTIVE]:
                    hg.get_move(
                        prompt=self.get_prompt(),
                        user_message=self.get_user_message(),
                        response_type=SchemeMoveResponse,
                    )
            case NominationPhase():
                for hg in self.role_dict[DefaultRole.HOH]:
                    hg.get_move(
                        prompt=self.get_prompt(),
                        user_message=self.get_user_message(),
                        response_type=NominationMoveResponse,
                    )
            case CeremonyPhase():
                print(f"WARNING: Skipping ceremony '{phase.name}'...")
            case _:
                raise ValueError(f"Phase type '{phase.name}' has not been covered.")
        return events


    def simulate_season(self):
        index = 0
        self.setup_new_season()

        for w_ind, week in enumerate(self.schedule):
            print(f"Running {week.name}...")
            self.setup_new_week()

            for p_ind, phase in enumerate(week.schedule):
                print(f"Running Phase '{phase.name}'...")

                index += 1

                timestamp = DefaultTimestamp(
                    week_number=w_ind+1,
                    turn_number=p_ind+1,
                    index=index,
                )

                events = self.process_phase(phase=phase, timestamp=timestamp)

                # Record and process the events
                self.history[timestamp] = events

                for event in events:
                    self.process_event(event)              
                