from __future__ import annotations
import random
from pydantic import Field
from typing import Optional, Iterable
from json import dumps

import time
from concurrent.futures import ThreadPoolExecutor

from aibb.base import House, Registry
from aibb.log import get_logger
from aibb.request import DefaultRequest
from aibb.competition import DefaultCompetition, CompScore
from aibb.houseguest import DefaultHouseguest, DefaultRole
from aibb.room import InteractiveRoom
from aibb.interaction import Interactable
from aibb.week import (
    DefaultWeek, 
    DefaultPhase, 
    CompPhase, 
    OpenPhase, 
    EvictionVotePhase,
    SleepPhase,
    NominationPhase,
    CeremonyPhase,
    VetoPhase,
    JuryVotePhase,
    VetoDrawPhase,
    FinalThreeEvictionPhase,
    PhaseStatus,
)
from aibb.move import (
    DefaultMove,
    WhisperMove,
    StartConversationMove,
    JoinConversationMove,
    ExitConversationMove,
    ChangeRoomMove,
    InteractMove, 
    EndInteractionMove,
    SpeakMove,
    EvictionVoteMove,
    JuryVoteMove,
    EffortMove,
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
    GatherEvent,
    JoinRoomEvent,
    ExitRoomEvent,
    StartConvoEvent,
    JoinConvoEvent,
    ExitConvoEvent,
    EndConvoEvent,
    EvictionVoteEvent,
    EvictionResultEvent,
    EvictionEvent,
    JuryVoteEvent,
    JuryResultEvent,
    NominationEvent,
    VetoUseEvent,
    Interaction,
    EndInteractionEvent,
    SchemeEvent,
    EndWeek,
    ExclusiveCrowning,
    AdditiveCrowning,
    DeCrowning,
    Perspective,
)
from aibb.response import (
    DefaultMoveResponse,
    OpenMoveResponse, 
    EvictionVoteMoveResponse, 
    SchemeMoveResponse,
    NominationMoveResponse,
    EffortMoveResponse,
    VetoMoveResponse,
    ReplacementNomineeMoveResponse,
    VetoDrawChoiceMoveResponse,
    JuryVoteMoveResponse,
)
from aibb.prompts import BASE_PROMPT_TEMPLATE, MESSAGE_TEMPLATE, RULES, RESPONSE_FORMAT
from aibb.utils import listed


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
    
    @property
    def convo_registry(self):
        return {hg.name: convo for convo in self.convos for hg in convo.active_participants}

    @property
    def interactable_registry(self):
        return {interactable.name: interactable for room in self.rooms for interactable in room.interactables}
    
    @property
    def registry(self) -> Registry:
        return {
            DefaultHouseguest.Ref: self.hg_registry,
            InteractiveRoom.Ref: self.room_registry,
            Conversation.Ref: self.convo_registry,
            Interactable.Ref: self.interactable_registry,
        }
    

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
    

    def get_base_perspective_map(self, move: DefaultMove, location: InteractiveRoom, include_snoops: bool=False) -> dict[DefaultHouseguest, Perspective]:
        ## Perspectives
        base_perspective_map: dict[DefaultHouseguest, Perspective] = {}
        ### Actor - simplest
        actor = move.actor
        base_perspective_map.update({actor: Perspective.ACTOR})

        ### Targets - contextual

        ### Witnesses - generally, anyone present in the room
        base_witnesses = [hg for hg in self.room_dict[location] if hg != actor]
        base_perspective_map.update({hg: Perspective.WITNESS for hg in base_witnesses})

        ### Snoopers - anyone in a neighboring room. Only loud events carry snoopers.
        if include_snoops:
            neighbors = [room for room in self.rooms if location in self.room_layout[room]]
            base_snoopers = [hg for room in neighbors for hg in self.room_dict[room]]
            base_perspective_map.update({hg: Perspective.SNOOP for hg in base_snoopers})

        return base_perspective_map

    
    def get_batch_moves(self, request_dict: dict[DefaultHouseguest, DefaultRequest], poll_interval: float=0.01) -> list[DefaultMove]:
        logger = get_logger()

        logger.debug(f"Handing off a batch of {len(request_dict)} request(s)")
        executor = ThreadPoolExecutor(max_workers=len(request_dict))
        futures = {
            executor.submit(hg.get_move, **request.kwargs): hg
            for hg, request in request_dict.items()
        }
        responses: dict[DefaultHouseguest, DefaultMoveResponse] = {}
        pending = dict(futures)
        try:
            while pending:
                done_now = [future for future in pending if future.done()]
                if not done_now:
                    time.sleep(poll_interval)  # the Windows-interruptible wait
                    continue
                for future in done_now:
                    hg = pending.pop(future)
                    try:
                        responses[hg] = future.result()
                    except Exception as error:
                        logger.error(f"Request for {hg.name} failed: {error!r}")
                        executor.shutdown(wait=False, cancel_futures=True)
                        raise
                    logger.debug(f"Response received for {hg.name} ({hg.model_id})")
        except KeyboardInterrupt:
            logger.error(f"Interrupted by user; abandoning batch with {len(pending)} request(s) still pending")
            executor.shutdown(wait=False, cancel_futures=True)
            raise
        executor.shutdown()
        logger.debug("Batch complete")
        return [responses[hg].get_move(request.registry) for hg, request in request_dict.items()]

    def get_gather_events(self, timestamp: DefaultTimestamp, location: InteractiveRoom) -> list[DefaultGameEvent]:
        gathered = [hg for members in self.room_dict.values() for hg in members]
        if all(hg in self.room_dict[location] for hg in gathered):
            return []
        events: list[DefaultGameEvent] = []
        for convo in self.convos:
            events.append(EndConvoEvent(
                timestamp=timestamp,
                location=convo.room,
                convo=convo,
                perspective_map={
                    witness: Perspective.WITNESS
                    for witness in self.room_dict[convo.room]
                },
            ))
        events.append(GatherEvent(
            timestamp=timestamp,
            location=location,
            perspective_map={hg: Perspective.WITNESS for hg in gathered},
        ))
        return events

    def get_prompt(self, week: DefaultWeek, phase: DefaultPhase, timestamp: DefaultTimestamp, hg: DefaultHouseguest, registry: Registry, response_type: type[DefaultMoveResponse]) -> str:
        day = 1 + len([p for p in week.schedule[:timestamp.phase_number - 1] if isinstance(p, SleepPhase)])
        time_info = f"It is Day {day} of {week.name}."
        match phase:
            case OpenPhase():
                turns_left = phase.num_turns - timestamp.turn_number + 1
                time_info += f" There are {turns_left} turns left in this Open phase, including this one."
            case _:
                pass
        schema = dumps(response_type.get_schema(hg=hg, registry=registry), indent=2)
        return BASE_PROMPT_TEMPLATE.format(
            rules=RULES,
            response_format=RESPONSE_FORMAT.format(schema=schema),
            schedule=week.schedule_info,
            phase_info=phase.info,
            time_info=time_info,
        )

    def get_noisy_rooms(self, room: InteractiveRoom) -> list[InteractiveRoom]:
        if not self.history:
            return []
        last_events = next(reversed(self.history.values()))
        noisy = []
        for event in last_events:
            match event:
                case SpokenMessage():
                    if event.location in self.room_layout[room] and event.location not in noisy:
                        noisy.append(event.location)
                case _:
                    pass
        return noisy

    def get_user_message(self, hg: DefaultHouseguest, options: str) -> str:
        status_lines = []
        in_house = any(hg in members for members in self.room_dict.values())
        if in_house:
            hg_room = self.get_hg_room(hg)
            status_lines.append(f"You are in the {hg_room.name}.")

            company = [other for other in self.room_dict[hg_room] if other != hg]
            if company:
                status_lines.append(f"Also here: {listed([other.name for other in company])}.")
            else:
                status_lines.append("You are alone.")

            actor_convo = self.get_hg_conversation(hg)
            if actor_convo:
                status_lines.append(f"You are in a conversation with {listed([p.name for p in actor_convo.active_participants if p != hg])}.")
            for convo in self.convos:
                if convo.room == hg_room and convo != actor_convo:
                    status_lines.append(f"{listed([p.name for p in convo.active_participants])} are having a conversation.")

            for room in self.get_noisy_rooms(hg_room):
                status_lines.append(f"You hear voices coming from the {room.name}.")
        else:
            status_lines.append("You have been evicted from the house.")

        for role, holders in self.role_dict.items():
            if holders:
                status_lines.append(f"{role.value}: {listed([holder.name for holder in holders])}")
        if self.jury:
            status_lines.append(f"Jury: {listed([juror.name for juror in self.jury])}")
        if self.pre_jury:
            status_lines.append(f"Evicted before jury: {listed([evictee.name for evictee in self.pre_jury])}")

        memory_lines = [event.narrate(hg) for event in hg.history]
        if hg.memory_limit is not None:
            memory_lines = memory_lines[-hg.memory_limit:]
        memory = "\n".join(memory_lines) if memory_lines else "Nothing of note has happened yet."

        return MESSAGE_TEMPLATE.format(
            scratchpad=hg.memory.describe() or "You have not used this yet.",
            status="\n".join(status_lines),
            memory=memory,
            options=options,
        )


    def process_event(self, event: DefaultGameEvent):

        for observer in event.perspective_map:
            observer.history.append(event)

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
                self.room_dict[event.room].append(event.hg)
            case ExitRoomEvent():
                self.room_dict[event.room].remove(event.hg)

            # CONVO MANAGEMENT
            case StartConvoEvent():
                self.convos.append(Conversation(
                    active_participants=[event.hg] + [p for p in event.participants],
                    room=event.location,
                ))
            case JoinConvoEvent():
                event.convo.active_participants.append(event.hg)
            case ExitConvoEvent():
                # Participant removal happens during move resolution (same-turn is_active checks)
                pass
            case EndConvoEvent():
                self.convos.remove(event.convo)

            case GatherEvent():
                for room in self.rooms:
                    for interactable in room.interactables:
                        for interacting_hgs in interactable.interactors.values():
                            for hg in [hg for hg in interacting_hgs if hg in event.witnesses]:
                                interacting_hgs.remove(hg)
                for room, members in self.room_dict.items():
                    self.room_dict[room] = [hg for hg in members if hg not in event.witnesses]
                self.room_dict[event.location].extend(event.witnesses)

            # INTERACTION MANAGEMENT
            case Interaction():
                if event.hg not in event.object.interactors[event.action]:
                    event.object.interactors[event.action].append(event.hg)
            case EndInteractionEvent():
                for interacting_hgs in event.object.interactors.values():
                    if event.hg in interacting_hgs:
                        interacting_hgs.remove(event.hg)

            # HOUSEGUEST MANAGEMENT
            case SchemeEvent():
                event.hg.memory = event.updated_memory
                event.hg.history = []

            # ELIMINATION MANAGEMENT
            case EvictionEvent():
                if len(self.pre_jury) < len(self.cast) - self.jury_size - self.num_finalists:
                    self.pre_jury.append(event.evicted)
                else:
                    self.jury.append(event.evicted)
                self.room_dict[self.get_hg_room(event.evicted)].remove(event.evicted)
                for room in self.rooms:
                    for interactable in room.interactables:
                        for interacting_hgs in interactable.interactors.values():
                            if event.evicted in interacting_hgs:
                                interacting_hgs.remove(event.evicted)
                evicted_convo = self.get_hg_conversation(event.evicted)
                if evicted_convo:
                    evicted_convo.active_participants.remove(event.evicted)
                    if not evicted_convo.is_active():
                        self.convos.remove(evicted_convo)

            # SPECIAL/META
            case EndWeek():
                self.setup_new_week()
            
    
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


    def process_phase_turn(self, week: DefaultWeek, phase: DefaultPhase, timestamp: DefaultTimestamp, status: PhaseStatus) -> list[DefaultGameEvent]:
        
        events = []

        if timestamp.turn_number == 1:
            match phase:
                case OpenPhase() | SleepPhase():
                    pass
                case CompPhase():
                    events.extend(self.get_gather_events(timestamp, self.room_registry["Backyard"]))
                case _:  # Every ceremony happens in the Living Room
                    events.extend(self.get_gather_events(timestamp, self.room_registry["Living Room"]))

        match phase:
            case CompPhase():
                TT = CompPhase.TurnType
                assert(isinstance(status, CompPhase.Status))
                match status.get_turn_type():
                    case TT.INIT:  # TODO; For now, just build the status instance and re-run
                        disallowed_players = self.filter_cast_by_roles(phase.disallowed_roles)
                        allowed_players = self.filter_cast_by_roles(phase.allowed_roles)
                        competitors = [hg for hg in allowed_players if hg not in disallowed_players]
                        status.players = competitors
                        return self.process_phase_turn(week, phase, timestamp, status)
                    case TT.GET_EFFORTS:
                        # TODO: Actually make efforts have some effect
                        # IGNORE: effort should be cosmetic for now; comps are purely random
                        request_dict: dict[DefaultHouseguest, DefaultRequest] = {
                            hg: hg.get_chat_request(
                                prompt=self.get_prompt(week, phase, timestamp, hg, self.registry, EffortMoveResponse),
                                user_message=self.get_user_message(hg, EffortMoveResponse.options(hg, {})),
                                response_type=EffortMoveResponse,
                                registry={},
                            ) for hg in status.players
                        }
                        efforts: dict[DefaultHouseguest, int] = {}
                        for move in self.get_batch_moves(request_dict):
                            # TODO: The asserts need to go. This is just for the linter, for now.
                            # IGNORE: [1]
                            assert(isinstance(move, EffortMove))
                            efforts[move.actor] = move.effort
                        status.efforts = efforts
                    case TT.GET_SCORES:
                
                        comp = DefaultCompetition(
                            ruleset=phase.comp_ruleset,
                            competitors=status.players,
                        )
                        # Run competition
                        ## TODO: SHOULD get the effort/stats from each hg first instead, THEN run w/ that context
                        ## For now, it's purely random results anyway
                        ## IGNORE: yeah ignore it
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
                        # FIX: This is the wrong approach; the scores should be the random values, not the efforts.
                        # Effort management is for a planned "throwing" mechanic, and should be purely cosmetic
                        # For now.
                        status.scores = [
                            CompScore(actor=hg, value=random.randint(1, 100))
                            for hg in status.players
                        ]
                    case TT.CROWN_WINNER:
                        # TODO: Do we want HG reactions? Might be useful. For now, etc.
                        # IGNORE: A separate turn for reactions might be better served by a DR/Q&A Phase.
                        # Don't worry about implementing that yet, that's in the future.
                        status.winner_crowned = True
                        return self.process_phase_turn(week, phase, timestamp, status)

            
            case EvictionVotePhase():
                TT = EvictionVotePhase.TurnType
                # TODO: The asserts need to go. This is just for the linter, for now.
                # IGNORE: Unless you have a very good, very simple workaround that still respects the linter,
                # Just leave these alone. Henceforth referred to as [1]
                assert(isinstance(status, EvictionVotePhase.Status))
                match status.get_turn_type():
                    case TT.INIT:
                        active_players = self.filter_cast_by_roles([DefaultRole.ACTIVE])
                        noms = self.filter_cast_by_roles([DefaultRole.NOMINEE])
                        hoh = self.filter_cast_by_roles([DefaultRole.HOH])

                        voters = [hg for hg in active_players if hg not in noms + hoh]
                        status.voters = voters
                        return self.process_phase_turn(week, phase, timestamp, status)
                    case TT.VOTE_NEEDED:
                        vote_events = []
                        noms = self.filter_cast_by_roles([DefaultRole.NOMINEE])
                        vote_registry: Registry = {DefaultHouseguest.Ref: {nom.name: nom for nom in noms}}
                        request_dict: dict[DefaultHouseguest, DefaultRequest] = {
                            hg: hg.get_chat_request(
                                prompt=self.get_prompt(week, phase, timestamp, hg, self.registry, EvictionVoteMoveResponse),
                                user_message=self.get_user_message(hg, EvictionVoteMoveResponse.options(hg, vote_registry)),
                                response_type=EvictionVoteMoveResponse,
                                registry=vote_registry,
                            ) for hg in status.voters
                        }
                        vote_tally: dict[DefaultHouseguest, DefaultHouseguest] = {}
                        for move in self.get_batch_moves(request_dict):
                            # TODO: The asserts need to go. This is just for the linter, for now.
                            # IGNORE: [1]
                            assert(isinstance(move, EvictionVoteMove))
                            vote_events.append(EvictionVoteEvent(
                                timestamp=timestamp,
                                location=self.room_registry["Diary Room"],
                                perspective_map={
                                    move.actor: Perspective.ACTOR,
                                },
                                choice=move.choice,
                            ))
                            vote_tally[move.actor] = move.choice
                        status.vote_tally = vote_tally
                        events.extend(vote_events)
                    case TT.TIEBREAK_NEEDED:
                        noms = self.filter_cast_by_roles([DefaultRole.NOMINEE])
                        tally = {nom: 0 for nom in noms}
                        for choice in status.vote_tally.values():
                            tally[choice] += 1

                        top_count = max(tally.values())
                        top_noms = [nom for nom, count in tally.items() if count == top_count]

                        if len(top_noms) > 1:
                            hohs = self.role_dict[DefaultRole.HOH]
                            if len(hohs) != 1:
                                raise ValueError("Too many HOHs to break an eviction tie")
                            hoh = hohs[0]
                            tiebreak_registry: Registry = {DefaultHouseguest.Ref: {nom.name: nom for nom in top_noms}}
                            move = hoh.get_move(
                                prompt=self.get_prompt(week, phase, timestamp, hoh, self.registry, EvictionVoteMoveResponse),
                                user_message=self.get_user_message(hoh, EvictionVoteMoveResponse.options(hoh, tiebreak_registry)),
                                response_type=EvictionVoteMoveResponse,
                            ).get_move(tiebreak_registry)
                            tiebreak_perspective_map = {
                                hg: Perspective.WITNESS
                                for hg in self.role_dict[DefaultRole.ACTIVE]
                            }
                            tiebreak_perspective_map.update({move.choice: Perspective.TARGET})
                            tiebreak_perspective_map.update({hoh: Perspective.ACTOR})
                            tiebreak_event = EvictionVoteEvent(
                                timestamp=timestamp,
                                location=self.room_registry["Living Room"],
                                perspective_map=tiebreak_perspective_map,
                                choice=move.choice,
                            )
                            events.append(tiebreak_event)
                            status.vote_tally[hoh] = move.choice
                            tally[move.choice] += 1
                            evicted = move.choice
                        else:
                            evicted = top_noms[0]

                        saved = [nom for nom in noms if nom != evicted]
                        result_perspective_map = {
                            hg: Perspective.WITNESS
                            for hg in self.role_dict[DefaultRole.ACTIVE]
                        }
                        result_perspective_map.update({nom: Perspective.TARGET for nom in saved})
                        result_perspective_map.update({evicted: Perspective.ACTOR})
                        result_event = EvictionResultEvent(
                            timestamp=timestamp,
                            location=self.room_registry["Living Room"],
                            perspective_map=result_perspective_map,
                            vote_dict=tally,
                        )
                        events.append(result_event)
                        decrown_event = DeCrowning(
                            timestamp=timestamp,
                            location=self.room_registry["Living Room"],
                            perspective_map=result_perspective_map,
                            prize=DefaultRole.ACTIVE,
                        )
                        events.append(decrown_event)
                        eviction_event = EvictionEvent(
                            timestamp=timestamp,
                            location=self.room_registry["Living Room"],
                            perspective_map=result_perspective_map,
                        )
                        events.append(eviction_event)
                        status.evicted = evicted


            case OpenPhase():
                # The logic:
                # First, speak anything that is meant for the room to hear.
                # Second, if anyone leaves a convo or room, invalidate any relevant whispers.
                # Third, if anyone joins a convo, invalidate any 'careful' whispers.
                # Fourth, ensure that all convos are still actually active.
                # Fifth, whisper anything that is meant for the conversationalists to hear.
                # Last, handle any low-priority moves
                request_dict: dict[DefaultHouseguest, DefaultRequest] = {}
                for hg in self.filter_cast_by_roles([DefaultRole.ACTIVE]):
                    hg_room = self.get_hg_room(hg)
                    open_registry: Registry = {
                        DefaultHouseguest.Ref: {other.name: other for other in self.room_dict[hg_room] if other != hg},
                        InteractiveRoom.Ref: {room.name: room for room in self.room_layout[hg_room]},
                        Conversation.Ref: {p.name: convo for convo in self.convos if convo.room == hg_room for p in convo.active_participants},
                        Interactable.Ref: {interactable.name: interactable for interactable in hg_room.interactables},
                    }
                    request_dict[hg] = hg.get_chat_request(
                        prompt=self.get_prompt(week, phase, timestamp, hg, self.registry, OpenMoveResponse),
                        user_message=self.get_user_message(hg, OpenMoveResponse.options(hg, open_registry)),
                        response_type=OpenMoveResponse,
                        registry=open_registry,
                    )
                moves = self.get_batch_moves(request_dict)

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
                        case EndInteractionMove():
                            end_interaction_event = EndInteractionEvent(
                                timestamp=timestamp,
                                location=location,
                                perspective_map=base_perspective_map,
                                object=move.interactable,
                            )
                            events.append(end_interaction_event)
                        case SpeakMove():
                            # Speaking is loud enough for neighboring rooms to notice
                            base_perspective_map = self.get_base_perspective_map(move, location, include_snoops=True)
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
                        case WhisperMove() | StartConversationMove() | JoinConversationMove() | ExitConversationMove() | ChangeRoomMove():
                            round_2_moves.add(move)
                        case _:
                            raise ValueError(f"'{type(move).__name__}' is not a valid open-phase move.")

                # Second, if anyone leaves a convo or room, invalidate any relevant whispers.

                whispers: set[WhisperMove] = set()
                whisper_map: dict[DefaultHouseguest, Conversation] = {}

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

                for whisper in whispers:
                    for conversation in self.convos:
                        if whisper.actor in conversation.active_participants:
                            whisper_map[whisper.actor] = conversation


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
                                actor_convo.active_participants.remove(exit_move.actor)
                                exit_convo_event = ExitConvoEvent(
                                    timestamp=timestamp,
                                    location=location,
                                    convo=actor_convo,
                                    perspective_map=base_perspective_map,
                                )
                                events.append(exit_convo_event)

                            for interactable in old_room.interactables:
                                for interacting_hgs in interactable.interactors.values():
                                    if exit_move.actor in interacting_hgs:
                                        end_interaction_event = EndInteractionEvent(
                                            timestamp=timestamp,
                                            location=old_room,
                                            perspective_map=base_perspective_map,
                                            object=interactable,
                                        )
                                        events.append(end_interaction_event)
                                        break
                
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
                    if whisperer in whisper_map and not whisper_map[whisperer].is_active():
                        skippable_moves.append(whisper)

                # Fifth, whisper anything that is meant for the conversationalists to hear.

                for whisper in skippable_moves:  # Remove the accumulated skipped ones
                    whispers.discard(whisper)
                
                for whisper in whispers:
                    location = self.get_hg_room(whisper.actor)
                    base_perspective_map = self.get_base_perspective_map(whisper, location)
                    actor_convo = self.get_hg_conversation(whisper.actor)
                    if not actor_convo:
                        raise ValueError(f"{whisper.actor.name} tried to whisper, but is not part of a conversation.")

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

                assert(isinstance(status, OpenPhase.Status))
                status.turns_run += 1
            
            case SleepPhase():
                # TODO: The asserts need to go. This is just for the linter, for now.
                # IGNORE: [1]
                assert(isinstance(status, SleepPhase.Status))
                schemers = self.filter_cast_by_roles([DefaultRole.ACTIVE])
                request_dict: dict[DefaultHouseguest, DefaultRequest] = {
                    hg: hg.get_chat_request(
                        prompt=self.get_prompt(week, phase, timestamp, hg, self.registry, SchemeMoveResponse),
                        user_message=self.get_user_message(hg, SchemeMoveResponse.options(hg, {})),
                        response_type=SchemeMoveResponse,
                        registry={},
                    ) for hg in schemers
                }
                scheme_dict: dict[DefaultHouseguest, str] = {}
                for move in self.get_batch_moves(request_dict):
                    # TODO: The asserts need to go. This is just for the linter, for now.
                    # IGNORE: [1]
                    assert(isinstance(move, SchemeMove))
                    scheme_event = SchemeEvent(
                        timestamp=timestamp,
                        location=self.get_hg_room(move.actor),
                        perspective_map={move.actor: Perspective.ACTOR},
                        updated_memory=move.updated_memory,
                    )
                    events.append(scheme_event)
                    scheme_dict[move.actor] = move.updated_memory.content
                status.schemers = [hg for hg in schemers]
                status.scheme_dict = scheme_dict
            case NominationPhase():
                TT = NominationPhase.TurnType
                # TODO: The asserts need to go. This is just for the linter, for now.
                # IGNORE: [1]
                assert(isinstance(status, NominationPhase.Status))
                match status.get_turn_type():
                    case TT.INIT:
                        hohs = self.role_dict[DefaultRole.HOH]
                        if len(hohs) != 1:
                            raise ValueError("Too many HOHs to do a Nomination Ceremony")
                        status.hoh = hohs[0]
                        return self.process_phase_turn(week, phase, timestamp, status)
                    case TT.GET_NOMINATIONS:
                        # TODO: There's gotta be a better way to verify
                        # IGNORE: [1]
                        assert(status.hoh)
                        nominatables = [
                            hg for hg in self.filter_cast_by_roles([DefaultRole.ACTIVE])
                            if hg != status.hoh
                        ]
                        nomination_registry: Registry = {DefaultHouseguest.Ref: {hg.name: hg for hg in nominatables}}
                        move = status.hoh.get_move(
                            prompt=self.get_prompt(week, phase, timestamp, status.hoh, self.registry, NominationMoveResponse),
                            user_message=self.get_user_message(status.hoh, NominationMoveResponse.options(status.hoh, nomination_registry)),
                            response_type=NominationMoveResponse,
                        ).get_move(nomination_registry)
                        base_perspective_map = {
                            hg:Perspective.WITNESS 
                            for hg in self.role_dict[DefaultRole.ACTIVE]
                        }
                        base_perspective_map.update(
                            {target: Perspective.TARGET 
                                for target in move.nominees
                            }
                        )
                        base_perspective_map.update({move.actor:Perspective.ACTOR})
                        nom_event = NominationEvent(
                            perspective_map=base_perspective_map,
                            location=self.room_registry["Living Room"],
                            timestamp=timestamp,
                        )
                        events.append(nom_event)
                        for nominee in move.nominees:
                            nominee_crown_map = {
                                hg: Perspective.WITNESS
                                for hg in self.role_dict[DefaultRole.ACTIVE]
                            }
                            nominee_crown_map.update({nominee: Perspective.ACTOR})
                            crown_event = AdditiveCrowning(
                                timestamp=timestamp,
                                location=self.room_registry["Living Room"],
                                perspective_map=nominee_crown_map,
                                prize=DefaultRole.NOMINEE,
                            )
                            events.append(crown_event)
                        status.nominees = [nom for nom in move.nominees]
            case VetoPhase():
                TT = VetoPhase.TurnType
                # TODO: The asserts need to go. This is just for the linter, for now.
                # IGNORE: [1]
                assert(isinstance(status, VetoPhase.Status))
                match status.get_turn_type():
                    case TT.INIT:
                        holders = self.role_dict[DefaultRole.POV]
                        if len(holders) != 1:
                            raise ValueError(f"Invalid number of veto holders ({len(holders)})")
                        status.holder = holders[0]
                        return self.process_phase_turn(week, phase, timestamp, status)
                    case TT.VETO_CHOICE:
                        # TODO: There's gotta be a better way to verify
                        # IGNORE: [1]
                        assert(status.holder)
                        noms = self.filter_cast_by_roles([DefaultRole.NOMINEE])
                        veto_registry: Registry = {DefaultHouseguest.Ref: {nom.name: nom for nom in noms}}
                        move = status.holder.get_move(
                            prompt=self.get_prompt(week, phase, timestamp, status.holder, self.registry, VetoMoveResponse),
                            user_message=self.get_user_message(status.holder, VetoMoveResponse.options(status.holder, veto_registry)),
                            response_type=VetoMoveResponse,
                        ).get_move(veto_registry)
                        # FABLE: With no eligible replacement (a final-four holder who
                        # isn't nominated), using the veto is disallowed, per the show.
                        hohs = self.role_dict[DefaultRole.HOH]
                        replaceables = [
                            hg for hg in self.filter_cast_by_roles([DefaultRole.ACTIVE])
                            if hg not in noms + hohs + [status.holder]
                        ]
                        if move.choice and replaceables:
                            status.saved = move.choice
                        else:
                            status.saved = False
                            base_perspective_map = {
                                hg: Perspective.WITNESS
                                for hg in self.role_dict[DefaultRole.ACTIVE]
                            }
                            base_perspective_map.update({status.holder: Perspective.ACTOR})
                            veto_event = VetoUseEvent(
                                timestamp=timestamp,
                                location=self.room_registry["Living Room"],
                                perspective_map=base_perspective_map,
                                used_on=None,
                                replacement=None,
                            )
                            events.append(veto_event)
                    case TT.REPLACEMENT_CHOICE:
                        # TODO: There's gotta be a better way to verify
                        # IGNORE: [1]
                        assert(status.holder)
                        assert(isinstance(status.saved, DefaultHouseguest))
                        hohs = self.role_dict[DefaultRole.HOH]
                        if len(hohs) != 1:
                            raise ValueError("Too many HOHs to name a replacement nominee")
                        hoh = hohs[0]
                        noms = self.filter_cast_by_roles([DefaultRole.NOMINEE])
                        replaceables = [
                            hg for hg in self.filter_cast_by_roles([DefaultRole.ACTIVE])
                            if hg not in noms + [hoh, status.holder]
                        ]
                        replacement_registry: Registry = {DefaultHouseguest.Ref: {hg.name: hg for hg in replaceables}}
                        move = hoh.get_move(
                            prompt=self.get_prompt(week, phase, timestamp, hoh, self.registry, ReplacementNomineeMoveResponse),
                            user_message=self.get_user_message(hoh, ReplacementNomineeMoveResponse.options(hoh, replacement_registry)),
                            response_type=ReplacementNomineeMoveResponse,
                        ).get_move(replacement_registry)
                        replacement = move.choice

                        base_perspective_map = {
                            hg: Perspective.WITNESS
                            for hg in self.role_dict[DefaultRole.ACTIVE]
                        }
                        base_perspective_map.update({status.saved: Perspective.TARGET})
                        base_perspective_map.update({replacement: Perspective.TARGET})
                        base_perspective_map.update({status.holder: Perspective.ACTOR})
                        veto_event = VetoUseEvent(
                            timestamp=timestamp,
                            location=self.room_registry["Living Room"],
                            perspective_map=base_perspective_map,
                            used_on=status.saved,
                            replacement=replacement,
                        )
                        events.append(veto_event)

                        decrown_perspective_map = {
                            hg: Perspective.WITNESS
                            for hg in self.role_dict[DefaultRole.ACTIVE]
                        }
                        decrown_perspective_map.update({status.saved: Perspective.ACTOR})
                        decrown_event = DeCrowning(
                            timestamp=timestamp,
                            location=self.room_registry["Living Room"],
                            perspective_map=decrown_perspective_map,
                            prize=DefaultRole.NOMINEE,
                        )
                        events.append(decrown_event)

                        crown_perspective_map = {
                            hg: Perspective.WITNESS
                            for hg in self.role_dict[DefaultRole.ACTIVE]
                        }
                        crown_perspective_map.update({replacement: Perspective.ACTOR})
                        crown_event = AdditiveCrowning(
                            timestamp=timestamp,
                            location=self.room_registry["Living Room"],
                            perspective_map=crown_perspective_map,
                            prize=DefaultRole.NOMINEE,
                        )
                        events.append(crown_event)
                        status.replacement = replacement
            case JuryVotePhase():
                TT = JuryVotePhase.TurnType
                # TODO: The asserts need to go. This is just for the linter, for now.
                # IGNORE: [1]
                assert(isinstance(status, JuryVotePhase.Status))
                match status.get_turn_type():
                    case TT.INIT:
                        status.voters = [hg for hg in self.jury]
                        return self.process_phase_turn(week, phase, timestamp, status)
                    case TT.VOTE_NEEDED:
                        vote_events = []
                        finalists = self.filter_cast_by_roles([DefaultRole.ACTIVE])
                        vote_registry: Registry = {DefaultHouseguest.Ref: {finalist.name: finalist for finalist in finalists}}
                        request_dict: dict[DefaultHouseguest, DefaultRequest] = {
                            hg: hg.get_chat_request(
                                prompt=self.get_prompt(week, phase, timestamp, hg, self.registry, JuryVoteMoveResponse),
                                user_message=self.get_user_message(hg, JuryVoteMoveResponse.options(hg, vote_registry)),
                                response_type=JuryVoteMoveResponse,
                                registry=vote_registry,
                            ) for hg in status.voters
                        }
                        vote_tally: dict[DefaultHouseguest, DefaultHouseguest] = {}
                        for move in self.get_batch_moves(request_dict):
                            # TODO: The asserts need to go. This is just for the linter, for now.
                            # IGNORE: [1]
                            assert(isinstance(move, JuryVoteMove))
                            vote_events.append(JuryVoteEvent(
                                timestamp=timestamp,
                                location=self.room_registry["Diary Room"],
                                perspective_map={
                                    move.actor: Perspective.ACTOR,
                                },
                                choice=move.choice,
                            ))
                            vote_tally[move.actor] = move.choice
                        status.vote_tally = vote_tally
                        events.extend(vote_events)
                    case TT.EVICTION:
                        finalists = self.filter_cast_by_roles([DefaultRole.ACTIVE])
                        tally = {finalist: 0 for finalist in finalists}
                        for choice in status.vote_tally.values():
                            tally[choice] += 1
                        winner = max(tally, key=lambda finalist: tally[finalist])
                        runners_up = [finalist for finalist in finalists if finalist != winner]

                        perspective_map = {
                            hg: Perspective.WITNESS
                            for hg in self.role_dict[DefaultRole.ACTIVE] + self.jury
                        }
                        perspective_map.update({winner: Perspective.ACTOR})
                        crown_event = ExclusiveCrowning(
                            timestamp=timestamp,
                            location=self.room_registry["Living Room"],
                            perspective_map=perspective_map,
                            prize=DefaultRole.WINNER,
                        )
                        events.append(crown_event)

                        result_perspective_map = {
                            hg: Perspective.WITNESS
                            for hg in self.role_dict[DefaultRole.ACTIVE] + self.jury
                        }
                        result_perspective_map.update({r: Perspective.TARGET for r in runners_up})
                        result_perspective_map.update({winner: Perspective.ACTOR})
                        result_event = JuryResultEvent(
                            timestamp=timestamp,
                            location=self.room_registry["Living Room"],
                            perspective_map=result_perspective_map,
                            vote_dict=tally,
                        )
                        events.append(result_event)
                        # FABLE: The Status has no winner field; the runner-up fills 'evicted' so the machine terminates
                        # RESOLVE: This is correct. No action needed.
                        status.evicted = runners_up[0]
            case VetoDrawPhase():
                TT = VetoDrawPhase.TurnType
                # TODO: The asserts need to go. This is just for the linter, for now.
                # IGNORE: [1]
                assert(isinstance(status, VetoDrawPhase.Status))
                match status.get_turn_type():
                    case TT.INIT:  # FABLE: This is a "No API" turn (a random draw), like the other INITs
                        drafters = self.filter_cast_by_roles([DefaultRole.HOH, DefaultRole.NOMINEE])
                        drafter = drafters[0]
                        pool = [
                            hg for hg in self.filter_cast_by_roles([DefaultRole.ACTIVE])
                            if hg not in drafters
                        ]
                        # Late-season, there aren't always enough houseguests left to fill three draws
                        status.draws_needed = min(status.draws_needed, len(pool))
                        # Drawing your own name stands in for the "Houseguest's Choice" chip
                        drawn = random.choice(pool + [drafter])
                        status.drawn_dict[drafter] = drawn
                        if drawn != drafter:
                            perspective_map = {
                                hg: Perspective.WITNESS
                                for hg in self.role_dict[DefaultRole.ACTIVE]
                            }
                            perspective_map.update({drawn: Perspective.ACTOR})
                            crown_event = AdditiveCrowning(
                                timestamp=timestamp,
                                location=self.room_registry["Living Room"],
                                perspective_map=perspective_map,
                                prize=DefaultRole.DRAWN_FOR_VETO,
                            )
                            events.append(crown_event)
                    case TT.DRAW_NEEDED:  # FABLE: This is a "No API" turn (a random draw), like the other INITs
                        drafters = self.filter_cast_by_roles([DefaultRole.HOH, DefaultRole.NOMINEE])
                        remaining_drafters = [hg for hg in drafters if hg not in status.drawn_dict]
                        drafter = remaining_drafters[0]
                        already_drawn = [drawn for drawn in status.drawn_dict.values()]
                        pool = [
                            hg for hg in self.filter_cast_by_roles([DefaultRole.ACTIVE])
                            if hg not in drafters and hg not in already_drawn
                        ]
                        # Drawing your own name stands in for the "Houseguest's Choice" chip
                        drawn = random.choice(pool + [drafter])
                        status.drawn_dict[drafter] = drawn
                        if drawn != drafter:
                            perspective_map = {
                                hg: Perspective.WITNESS
                                for hg in self.role_dict[DefaultRole.ACTIVE]
                            }
                            perspective_map.update({drawn: Perspective.ACTOR})
                            crown_event = AdditiveCrowning(
                                timestamp=timestamp,
                                location=self.room_registry["Living Room"],
                                perspective_map=perspective_map,
                                prize=DefaultRole.DRAWN_FOR_VETO,
                            )
                            events.append(crown_event)
                    case TT.HG_CHOICE:
                        chooser = None
                        for drafter, drawn in status.drawn_dict.items():
                            if drafter == drawn:
                                chooser = drafter
                        # TODO: There's gotta be a better way to verify
                        # IGNORE: [1]
                        assert(chooser)
                        drafters = self.filter_cast_by_roles([DefaultRole.HOH, DefaultRole.NOMINEE])
                        choosables = [
                            hg for hg in self.filter_cast_by_roles([DefaultRole.ACTIVE])
                            if hg not in drafters and hg not in status.drawn_dict.values()
                        ]
                        choice_registry: Registry = {DefaultHouseguest.Ref: {hg.name: hg for hg in choosables}}
                        move = chooser.get_move(
                            prompt=self.get_prompt(week, phase, timestamp, chooser, self.registry, VetoDrawChoiceMoveResponse),
                            user_message=self.get_user_message(chooser, VetoDrawChoiceMoveResponse.options(chooser, choice_registry)),
                            response_type=VetoDrawChoiceMoveResponse,
                        ).get_move(choice_registry)
                        status.drawn_dict[chooser] = move.choice
                        perspective_map = {
                            hg: Perspective.WITNESS
                            for hg in self.role_dict[DefaultRole.ACTIVE]
                        }
                        perspective_map.update({move.choice: Perspective.ACTOR})
                        crown_event = AdditiveCrowning(
                            timestamp=timestamp,
                            location=self.room_registry["Living Room"],
                            perspective_map=perspective_map,
                            prize=DefaultRole.DRAWN_FOR_VETO,
                        )
                        events.append(crown_event)
            case FinalThreeEvictionPhase():
                TT = FinalThreeEvictionPhase.TurnType
                # TODO: The asserts need to go. This is just for the linter, for now.
                # IGNORE: [1]
                assert(isinstance(status, FinalThreeEvictionPhase.Status))
                match status.get_turn_type():
                    case TT.INIT:
                        hohs = self.role_dict[DefaultRole.HOH]
                        if len(hohs) != 1:
                            raise ValueError("Too many HOHs to do a Final Three Eviction Ceremony")
                        status.voters = [hg for hg in hohs]
                        return self.process_phase_turn(week, phase, timestamp, status)
                    case TT.VOTE_NEEDED:
                        hoh = status.voters[0]
                        evictables = [
                            hg for hg in self.filter_cast_by_roles([DefaultRole.ACTIVE])
                            if hg not in status.voters
                        ]
                        vote_registry: Registry = {DefaultHouseguest.Ref: {hg.name: hg for hg in evictables}}
                        move = hoh.get_move(
                            prompt=self.get_prompt(week, phase, timestamp, hoh, self.registry, EvictionVoteMoveResponse),
                            user_message=self.get_user_message(hoh, EvictionVoteMoveResponse.options(hoh, vote_registry)),
                            response_type=EvictionVoteMoveResponse,
                        ).get_move(vote_registry)
                        perspective_map = {
                            hg: Perspective.WITNESS
                            for hg in self.role_dict[DefaultRole.ACTIVE]
                        }
                        perspective_map.update({move.choice: Perspective.TARGET})
                        perspective_map.update({hoh: Perspective.ACTOR})
                        vote_event = EvictionVoteEvent(
                            timestamp=timestamp,
                            location=self.room_registry["Living Room"],
                            perspective_map=perspective_map,
                            choice=move.choice,
                        )
                        events.append(vote_event)
                        status.choice = move.choice
                    case TT.EVICTION:
                        # TODO: There's gotta be a better way to verify
                        # IGNORE: [1]
                        assert(status.choice)
                        evicted = status.choice
                        saved = [
                            hg for hg in self.filter_cast_by_roles([DefaultRole.ACTIVE])
                            if hg not in [evicted] + status.voters
                        ]
                        result_perspective_map = {
                            hg: Perspective.WITNESS
                            for hg in self.role_dict[DefaultRole.ACTIVE]
                        }
                        result_perspective_map.update({hg: Perspective.TARGET for hg in saved})
                        result_perspective_map.update({evicted: Perspective.ACTOR})
                        result_event = EvictionResultEvent(
                            timestamp=timestamp,
                            location=self.room_registry["Living Room"],
                            perspective_map=result_perspective_map,
                            vote_dict={evicted: 1},
                        )
                        events.append(result_event)
                        decrown_event = DeCrowning(
                            timestamp=timestamp,
                            location=self.room_registry["Living Room"],
                            perspective_map=result_perspective_map,
                            prize=DefaultRole.ACTIVE,
                        )
                        events.append(decrown_event)
                        eviction_event = EvictionEvent(
                            timestamp=timestamp,
                            location=self.room_registry["Living Room"],
                            perspective_map=result_perspective_map,
                        )
                        events.append(eviction_event)
                        status.evicted = True
            case _:
                raise ValueError(f"Phase type '{phase.name}' has not been covered.")
        return events


    def simulate_season(self):
        logger = get_logger()
        index = 0
        self.setup_new_season()

        for w_ind, week in enumerate(self.schedule):
            logger.info(f"Running {week.name}")
            self.setup_new_week()

            for p_ind, phase in enumerate(week.schedule):
                phase_log_info = f"{phase.name} ({phase.num_turns} turns)" if isinstance(phase, OpenPhase) else phase.name
                logger.info(f"Running Phase '{phase_log_info}' ({week.name})")

                t_ind = 0
                status = phase.get_status()

                while status.get_turn_type():

                    index += 1
                    timestamp = DefaultTimestamp(
                        week_number=w_ind+1,
                        phase_number=p_ind+1,
                        turn_number=t_ind+1,
                        index=index,
                    )

                    logger.debug(timestamp.describe())
                    events = self.process_phase_turn(week=week, phase=phase, timestamp=timestamp, status=status)

                    # Record and process the events
                    self.history[timestamp] = events

                    for event in events:
                        self.process_event(event)   

                    t_ind += 1
        
        logger.info("Simulation finished")