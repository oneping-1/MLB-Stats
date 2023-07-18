from typing import List, Tuple
from .game import Game, AllPlays, PlayEvents
from .runners import Runners
from .statsapi_plus import get_game_dict


class Missed_Call():
    def __init__(self, pitch: PlayEvents):
        self.pX = pitch.pitchData.coordinates.pX
        self.pZ = pitch.pitchData.coordinates.pZ

        self.sZ_top = pitch.pitchData.coordinates.sZ_top
        self.sZ_bot = pitch.pitchData.coordinates.sZ_bot

        self.pZ_top = pitch.pitchData.coordinates.pZ_top
        self.pZ_bot = pitch.pitchData.coordinates.pZ_bot

class Umpire():
    def __init__(self,
                 gamePk: int = None,
                 game: Game = None):

        if game is not None:
            self.game = game
        elif gamePk is not None:
            game_dict= get_game_dict(gamePk)
            self.game = Game(game_dict)
        else:
            raise ValueError('gamePk and game arguments not provided')

        self.num_missed_calls = 0
        self.missed_calls: List[Missed_Call] = []
        self.home_favor = 0

    def set(self,
            print_missed_calls: bool = False
            ) -> Tuple[int, float, List[Missed_Call]]:

        stats = self.find_missed_calls(game=self.game,
                                     print_missed_calls=print_missed_calls)

        self.num_missed_calls, self.home_favor, self.missed_calls = stats

    @classmethod
    def find_missed_calls(cls,
                            game: Game = None,
                            gamePk: int = None,
                            print_missed_calls: bool = False)-> float:
        """
        Calculates total favored runs for the home team for a given team

        Itterates through every pitch in a given game and finds pitches that
            the umpire missed.
        When home_favor >0, umpire effectively gave the home team runs.
        When <0, gave runs to the away team

        print_every_missed_call will print the following for every missed
            call when set to True. Defaults to False:
        1. Inning
        2. Pitcher and Batter
        3. Count
        4. Pitch Location
        5. Strike Zone Location
        6. Favor

        Returns:
            num_missed_calls (int): The number of missed calls by the umpire
            home_favor (float): The runs the umpire gave the home team
                by their missed calls
            missed_calls (List[Missed_Calls]): A list of missed calls
                with each element a Missed_Calls class

        Raises:
            ValueError: If game and gamePk are not provided
        """
        if game is None and gamePk is not None:
            game_dict = get_game_dict(gamePk)
            game = Game(game_dict)
        elif game is None and gamePk is None:
            raise ValueError('game and gamePk not provided')

        runners: Runners = Runners()
        runners_int = int(runners)

        home_favor: float = 0
        missed_calls: List[Missed_Call] = []

        for at_bat in game.liveData.plays.allPlays:
            runners.place_runners(at_bat)
            isTopInning = at_bat.about.isTopInning

            for i in at_bat.pitchIndex:
                pitch: PlayEvents = at_bat.playEvents[i]

                home_delta = pitch.delta_favor_monte(runners_int, isTopInning)

                if home_delta != 0:
                    home_favor += home_delta
                    missed_calls.append(pitch)

                    if print_missed_calls is True:
                        print(cls._missed_pitch_details(
                            at_bat, pitch, runners, home_delta))

        return (len(missed_calls), home_favor, missed_calls)

    @classmethod
    def _missed_pitch_details(cls,
                            at_bat: AllPlays,
                            pitch: PlayEvents,
                            runners: List[bool],
                            home_delta: float) -> str:

        to_print_str = ''

        half_inn = at_bat.about.halfInning.capitalize()
        inning = at_bat.about.inning
        pitcher_name = at_bat.matchup.pitcher.fullName
        batter_name = at_bat.matchup.batter.fullName

        to_print_str += f'{half_inn} {inning}\n'
        to_print_str += f'{pitcher_name} to {batter_name}\n'

        if pitch.count.outs == 1:
            to_print_str += f'{pitch.count.outs} out, '
        else:
            to_print_str += f'{pitch.count.outs} outs, '

        if runners == [False, False, False]:
            to_print_str += 'bases empty\n'
        elif runners == [True, False, False]:
            to_print_str += 'runner on first\n'
        elif runners == [False, True, False]:
            to_print_str += 'runner on second\n'
        elif runners == [True, True, False]:
            to_print_str += 'runners on first and second\n'
        elif runners == [False, False, True]:
            to_print_str += 'runner on third\n'
        elif runners == [True, False, True]:
            to_print_str += 'runner on first and third\n'
        elif runners == [False, True, True]:
            to_print_str += 'runner on second and third\n'
        elif runners == [True, True, True]:
            to_print_str += 'bases loaded\n'

        balls = pitch.count.balls
        strikes = pitch.count.strikes

        if pitch.details.code == 'C':
            to_print_str += f'{balls}-{strikes-1}, ball called strike\n'
        elif pitch.details.code == 'B':
            to_print_str += f'{balls-1}-{strikes}, strike called ball\n'


        to_print_str += (f'pX = {pitch.pitchData.coordinates.pX:.3f} | '
                        f'pZ = {pitch.pitchData.coordinates.pZ:.3f}\n')

        to_print_str += (f'bot = {pitch.pitchData.coordinates.pZ_bot:.3f} | '
                        f'top = {pitch.pitchData.coordinates.pZ_top:.3f}\n')

        to_print_str += f'Home Favor: {home_delta:5.3f}\n'

        return to_print_str


    def __len__(self):
        return len(self.missed_calls)


    def __str__(self):
        prt_str = ''

        prt_str += f'{len(self.missed_calls)} Missed Calls. '
        prt_str += f'{self.home_favor} Home Favor'

        return prt_str
