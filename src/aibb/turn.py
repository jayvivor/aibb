from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, Literal
from pydantic import Field

from aibb.base import Base, Turn, CompRuleset, Timestamp
from aibb.houseguest import DefaultHouseguest
from aibb.room import InteractiveRoom
from aibb.competition import DefaultCompetition
from aibb.events import (
        GameEvent,
        SpokenMessage,
        WhisperedMessage,
        JoinConvoEvent,
        JoinRoomEvent,
        ExitConvoEvent,
        ExitRoomEvent,
        Interaction,
        ConversationHistory,
        CompScoreboard,
        EvictionVoteEvent,
        EvictionResultEvent,
    )
from aibb.move import (
        Conversation,
        DefaultMove, 
        SchemeMove, 
        SpeakMove,
        WhisperMove,
        InteractMove,
        StartConversationMove,
        JoinConversationMove,
        ExitConversationMove,
        ChangeRoomMove,
        CompMove,
        EvictionVoteMove,
        JuryVoteMove,
    )


# class DefaultTurnType(TurnType):
#     SCHEME = "Scheme"
#     OPEN = "Open"
#     COMP = "Comp"
#     VOTE = "Vote"
#     EVICTION = "Eviction"
#     NOMINATION = "Nomination"
#     VETO = "Veto"
#     JURY_VOTE = "Jury Vote"

#     @property
#     def description(self):
#         mapping = {
#             DefaultTurnType.SCHEME: "Houseguests make and review plans for future rounds.",
#             DefaultTurnType.OPEN: "Houseguests are permitted to openly mingle.",
#             DefaultTurnType.COMP: "Houseguests are competing for a prize.",
#             DefaultTurnType.VOTE: "Houseguests are voting to evict.",
#             DefaultTurnType.JURY_VOTE: "Houseguests are voting to select a winner.",
#             DefaultTurnType.EVICTION: "Houseguests are saying their goodbyes to the evicted houseguest.",
#             DefaultTurnType.NOMINATION: "Houseguests are nominating for eviction.",
#             DefaultTurnType.VETO: "Houseguests are attending the veto meeting.",
#         }
#         return mapping[self]

DM = TypeVar("DM", bound=DefaultMove)
GE = TypeVar("GE", bound=GameEvent)

class TurnResult(Base, Generic[GE]):
    events: dict[DefaultHouseguest | Literal[0], list[GE]]

    def describe(self):
        return "\n".join([ge.describe() for event in self.events.values() for ge in event])


class DefaultTurn(Turn, ABC, Generic[DM]):
    name: str
    timestamp: Timestamp
    moves: list[DM] = Field(default_factory=list)

    @abstractmethod
    def execute(self, *args, **kwargs) -> TurnResult:
        ...

    @abstractmethod
    def get_options(self, *args, **kwargs) -> list[type[DefaultMove]]:
        ...

    @property
    def info(self):
        raise NotImplementedError


SCHEME_INFO = f'''
Your current turn is the 'scheme' turn.
During this turn, you have the chance to update your message/event history to your scratchpad/memory.
You may include whatever you'd like in here, and organize/format it however you'd like.
However, there is a strict 1000 character limit for your scratchpad; anything in excess of this
will be silently truncated.
Memories, plans, and context will not carry over between phases; this is the last time this context will be available to you.
'''

class SchemeTurn(DefaultTurn[SchemeMove]):
    name: str = "Scheme"

    def execute(self):
        events = {}
        for move in self.moves:
            hg = move.actor
            new_memory = move.updated_memory
            hg.memory = new_memory
            events[hg] = new_memory
        return TurnResult(events=events)

    @property
    def info(self):
        return SCHEME_INFO
    
    @abstractmethod
    def get_options(self) -> list[type[DefaultMove]]:
        return [SchemeMove]

class OpenTurn(DefaultTurn[
    SpeakMove | WhisperMove | StartConversationMove | 
    JoinConversationMove | ExitConversationMove | InteractMove |
    ChangeRoomMove
    ]):
    name: str = "Open"
    active_conversations: list[Conversation]
    rooms: list[InteractiveRoom]


    @property
    def room_placement_dict(self):
        return {room:room.members for room in self.rooms}

    @property
    def reverse_room_placement_dict(self):
        hg_dict: dict[DefaultHouseguest, InteractiveRoom] = {}
        for room, hg_list in self.room_placement_dict.items():
            for hg in hg_list:
                hg_dict[hg] = room
        return hg_dict


    def execute(self):
        # The logic:
        # First, speak anything that is meant for the room to hear.
        # Second, if anyone leaves a convo or room, invalidate any relevant whispers.
        # Third, if anyone joins a convo, invalidate any 'careful' whispers.
        # Fourth, ensure that all convos are still actually active.
        # Fifth, whisper anything that is meant for the conversationalists to hear.
        # Last, handle any low-priority moves
        events = {move.actor:[] for move in self.moves}

        unavailable_hgs: set[DefaultHouseguest] = set()
        
        skippable_moves = []
        round_1_moves = {move for move in self.moves}
        round_2_moves: set[
            WhisperMove | StartConversationMove | 
            JoinConversationMove | ExitConversationMove | ChangeRoomMove] = set()
        for move in round_1_moves: # First, speak anything that is meant for the room to hear.
            match move:
                case InteractMove():
                    actor = move.actor
                    interaction_event = Interaction(
                        timestamp=self.timestamp,
                        actor=actor,
                        object=move.interactable,
                        action=move.action,
                        turn_duration=0,
                    )
                    for member in self.reverse_room_placement_dict[actor].members:
                        member.history.append(interaction_event)
                    events[actor].append(interaction_event)
                case SpeakMove():
                    speaker = move.actor
                    room = self.reverse_room_placement_dict[speaker]

                    event = SpokenMessage(
                            timestamp=self.timestamp,
                            speaker=speaker,
                            content=move.content,
                    )
                    room.add_event(event)
                    for member in self.reverse_room_placement_dict[speaker].members:
                        member.history.append(event)
                    events[speaker].append(event)
                case _:
                    round_2_moves.add(move)

        # Second, if anyone leaves a convo or room, invalidate any relevant whispers.

        whispers: set[WhisperMove] = set()
        whisper_map: dict[DefaultHouseguest, Conversation] = {}
        for whisper in whispers:
            for conversation in self.active_conversations:
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
            match exit_move:
                case ExitConversationMove():
                    leaver = exit_move.actor
                    convo = exit_move.conversation

                    changed_convos[convo] = leaver
                    convo.active_participants.remove(leaver)
                    event = ExitConvoEvent(timestamp=self.timestamp, hg=leaver)
                    convo.add_event(event)
                    events[leaver].append(event)
                    for member in self.reverse_room_placement_dict[leaver].members:
                        member.history.append(event)
                    
                case ChangeRoomMove():
                    room_changer = exit_move.actor
                    old_room = self.reverse_room_placement_dict[room_changer]
                    new_room = exit_move.room

                    unavailable_hgs.add(room_changer)
                    self.room_placement_dict[old_room].remove(room_changer)
                    exit_event = ExitRoomEvent(timestamp=self.timestamp, hg=room_changer)
                    old_room.add_event(exit_event)
                    events[room_changer].append(exit_event)
                    for member in self.reverse_room_placement_dict[room_changer].members:
                        member.history.append(exit_event)

                    self.room_placement_dict[new_room].append(room_changer)
                    join_event = JoinRoomEvent(timestamp=self.timestamp, hg=room_changer)
                    new_room.add_event(join_event)
                    events[room_changer].append(join_event)
                    for member in self.reverse_room_placement_dict[room_changer].members:
                        member.history.append(join_event)

                    for convo in self.active_conversations: # Leaving a room is leaving a convo
                        if room_changer in convo.active_participants:
                            changed_convos[convo] = room_changer
                            convo.active_participants.remove(room_changer)
                            exit_convo_event = ExitConvoEvent(timestamp=self.timestamp, hg=room_changer)
                            convo.add_event(exit_convo_event)
                            events[room_changer].append(exit_convo_event)
                            for member in self.reverse_room_placement_dict[room_changer].members:
                                member.history.append(exit_convo_event)
        
        for whisper in whispers:
            whisperer = whisper.actor
            convo = None
            for c in self.active_conversations:
                if whisperer in c.active_participants:
                    convo = c
                    break
            if convo in changed_convos:
                # Skip the whisper; someone left
                skippable_moves.append(whisper)
        

        # Third, if anyone joins a convo, invalidate any 'careful' whispers or start attempts.

        for join_move in joins:
            match join_move:
                case JoinConversationMove():
                    joiner = join_move.actor
                    convo = join_move.conversation

                    unavailable_hgs.add(joiner)
                    changed_convos[convo] = joiner
                    join_convo_event = JoinConvoEvent(timestamp=self.timestamp, hg=joiner)
                    convo.add_event(join_convo_event)
                    events[joiner].append(join_convo_event)
                    for member in self.reverse_room_placement_dict[joiner].members:
                                member.history.append(join_convo_event)

        for whisper in whispers:
            if whisper.allow_join:  # If joining is allowed, don't worry about it
                continue
            whisperer = whisper.actor
            convo = None
            for c in self.active_conversations:
                if whisperer in c.active_participants:
                    convo = c
                    break
            if convo in changed_convos:
                # Skip the whisper; someone left
                skippable_moves.append(whisper)

        # Fourth, ensure that all convos are still actually active.

        for convo in changed_convos:
            if not convo.is_active():
                convo.history.turn_duration = self.timestamp - convo.history.timestamp
                self.active_conversations.remove(convo)
        
        for whisper in whispers:
            whisperer = whisper.actor
            if not whisper_map[whisperer].is_active():
                skippable_moves.append(whisper)

        # Fifth, whisper anything that is meant for the conversationalists to hear.

        for whisper in skippable_moves:  # Remove the accumulated skipped ones
            whispers.remove(whisper)
        
        for whisper in whispers:
            whisperer = whisper.actor
            convo = whisper_map[whisperer]
            room = self.reverse_room_placement_dict[whisperer]


            whisper_event = WhisperedMessage(
                speaker=whisperer,
                content=whisper.content,
                timestamp=self.timestamp, 
                targets=[hg for hg in convo.active_participants if hg != whisperer],
                witnesses=[hg for hg in room.members if hg not in convo.active_participants],
            )
            events[whisperer].append(whisper_event)
            convo.add_event(whisper_event)
            for witness in self.reverse_room_placement_dict[whisperer].members:
                witness.history.append(whisper_event)

        # Last, any unmentioned events

        for move in final_round_moves:
            match move:
                case StartConversationMove():
                    starter, participants = move.actor, move.participants
                    all_participants = [starter] + participants

                    # Skip anyone who's left the room or joined another convo already
                    if any(p in unavailable_hgs for p in all_participants):
                        continue

                    c_history = ConversationHistory(
                        timestamp=self.timestamp,
                        join_history=[
                            JoinConvoEvent(
                                timestamp=self.timestamp,
                                hg=hg,
                            )
                            for hg in all_participants
                        ]
                    )
                    convo = Conversation(
                        active_participants=all_participants,
                        history=c_history,
                        room=self.reverse_room_placement_dict[starter],
                    )
                case _:
                    raise ValueError("Somehow, there's a move type that hasn't been covered.")

        # Clear empty keys
        temp_events = {k:v for k,v in events.items()}
        events = {k:v for k,v in temp_events.items() if v}

        result = TurnResult(events=events) # type: ignore
        return result


    def get_options(self) -> list[type[DefaultMove]]:
        return [
            SpeakMove,
            WhisperMove,
            StartConversationMove,
            JoinConversationMove,
            ExitConversationMove,
            InteractMove,
            ChangeRoomMove,
        ]                    


class CompTurn(DefaultTurn[CompMove]):
    name: str = "Competition"
    ruleset: CompRuleset
    players: list[DefaultHouseguest]

    def execute(self) -> TurnResult:
        events = {}
        
        # TODO: Integrate player moves
        competition = DefaultCompetition(
            ruleset=self.ruleset,
            competitors=self.players,
        )

        results = competition.run_comp()

        events[None] = results

        result = TurnResult[CompScoreboard](events=events)
        return result
    
    def get_options(self) -> list[type[DefaultMove]]:
        return [
            CompMove,
        ]  


class EvictionVoteTurn(DefaultTurn[EvictionVoteMove]):
    name: str = "Eviction Vote"


    def execute(self):

        events: dict[DefaultHouseguest | Literal[0], list[EvictionVoteEvent | EvictionResultEvent]] = {
            move.actor:
            [EvictionVoteEvent(
                timestamp=self.timestamp,
                voter=move.actor,
                choice=move.choice,
            )] for move in self.moves
            if isinstance(move, EvictionVoteMove)
            and not move.is_tiebreaker
        }

        choices = {move.choice:0 for move in self.moves if not move.is_tiebreaker}

        # Tabulate
        for move in self.moves:
            choices[move.choice] += 1

        # Check for ties
        high_score = max(choices.values())
        losers = [choice for choice, score in choices.items() if score == high_score]

        if len(losers) > 1:  # Tiebreaker!

            events.update({
                move.actor:
                [EvictionVoteEvent(
                    timestamp=self.timestamp,
                    voter=move.actor,
                    choice=move.choice,
                )] for move in self.moves
                if isinstance(move, EvictionVoteMove)
                and move.is_tiebreaker
            })

            choices.update({move.choice:0 for move in self.moves if move.is_tiebreaker})
            high_score = max(choices.values())
            losers = [choice for choice, score in choices.items() if score == high_score]
            if len(losers) > 1:
                raise ValueError("I don't know how, but there's still a tie.")

        evicted = losers[0]

        events[0] = [EvictionResultEvent(
            timestamp=self.timestamp,
            evicted=evicted,
            saved=[hg for hg in choices.keys() if hg != evicted],
            vote_dict=choices,
        )]

        result = TurnResult[EvictionVoteEvent | EvictionResultEvent](events=events)
        return result
    
    def get_options(self) -> list[type[DefaultMove]]:
        return [
            EvictionVoteMove,
        ]