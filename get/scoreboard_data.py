from typing import Tuple
import copy
from get.game import Game
from get.runners import Runners
from get.umpire import Umpire

class ScoreboardData:
    keys = ['abstractGameState',
            'abstractGameCode',
            'detailedState',
            'codedGameState',
            'delay_seconds',
            'statusCode',
            'game_state',
            'away_abv',
            'home_abv',
            'away_score',
            'home_score',
            'start_time',
            'inning',
            'inning_state',
            'outs',
            'runners',
            'umpire',
            'gamepk']

    def __init__(self, gamepk: int = None, delay_seconds: int = 0):
        self.gamepk: int = gamepk
        self.delay_seconds: int = delay_seconds

        self.game: Game = Game.get_game_from_pk(gamepk =self.gamepk,
                                                delay_seconds=self.delay_seconds)

        self.abstractGameState: str = self.game.gameData.status.abstractGameState
        self.abstractGameCode: str = self.game.gameData.status.abstractGameCode
        self.detailedState: str = self.game.gameData.status.detailedState
        self.codedGameState: str = self.game.gameData.status.codedGameState
        self.statusCode: str = self.game.gameData.status.statusCode

        # See get/game.py/status for more info:
        self.game_state: str = self.game.gameData.status.game_state

        self.away_abv: str = self.game.gameData.teams.away.abbreviation
        self.home_abv: str = self.game.gameData.teams.home.abbreviation

        self.away_score: int = self.game.liveData.linescore.teams.away.runs
        self.home_score: int = self.game.liveData.linescore.teams.home.runs

        self.start_time: str = self.game.gameData.datetime.startTime

        self.inning: int = self.game.liveData.linescore.currentInning

        isTopInning = self.game.liveData.linescore.isTopInning

        if isTopInning is True:
            self.inning_state: str = 'T'
        else:
            self.inning_state: str = 'B'

        self.outs: int = self.game.liveData.linescore.outs

        runners = Runners()
        runners.set_bases_from_offense(self.game.liveData.linescore.offense)
        self.runners = int(runners)

        self.umpire = 'L'
        umpire = Umpire(gamepk=self.gamepk, delay_seconds=self.delay_seconds)
        umpire.calculate(delta_favor_func=Umpire.delta_favor_monte)
        self.umpire: str = f'{repr(umpire)} ({umpire.num_missed_calls:d})'

    def update_and_return_new(self) -> Tuple['ScoreboardData', bool]:
        new_game = ScoreboardData(gamepk=self.gamepk,
                                  delay_seconds=self.delay_seconds)

        differences = copy.deepcopy(self)

        new_info: bool = False

        for key in ScoreboardData.keys:
            old_value = getattr(self, key)
            new_value = getattr(new_game, key)
            if old_value != new_value:
                setattr(self, key, new_value)
                setattr(differences, key, new_value)
                new_info = True
            else:
                setattr(differences, key, None)

        return (differences, new_info)

    def to_dict(self) -> dict:
        diff = {}

        for key in ScoreboardData.keys:
            value = getattr(self, key)
            if value is not None:
                diff[key] = value

        return diff
