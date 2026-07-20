import random

from aibb.base import Competition, CompRuleset, CompResults
from aibb.houseguest import DefaultHouseguest
from aibb import utils


class DefaultCompResults(CompResults[DefaultHouseguest]):

    def describe(self):
        return f"{self.winner.name} has won!"


class RandomCompRuleset(CompRuleset[DefaultHouseguest, DefaultCompResults]):
    
    def run_comp(self, pool):
        winner = random.choice(pool)
        return DefaultCompResults(winner=winner)
    
    def describe(self):
        return "A randomly-selected houseguest wins."


class DefaultCompetition(Competition[DefaultHouseguest, DefaultCompResults]):

    def describe(self):
        return f'''
        Rules: {self.ruleset.describe()}
        Players: {utils.listed([c.name for c in self.competitors])}
        Results: {self.results.describe() if self.results else 'TBD'}
        '''