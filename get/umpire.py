from typing import List, Tuple
import random
import math
from get.game import Game, AllPlays, PlayEvents
from get.runners import Runners
from get.statsapi_plus import get_game_dict
from get.statsapi_plus import get_run_expectency_numpy
from get.statsapi_plus import get_run_expectency_difference_numpy

HAWKEYE_MARGIN_OF_ERROR = 0.25/12 # Margin of Error of hawkeye system (inches)

# max distance a ball can be from strike zone edge before umpire
# call becomes incorrect. between 0.320 and 0.505 based of tests
BUFFER_INCH = .350
BUFFER_FEET = BUFFER_INCH / 12


class Umpire():
    hmoe = HAWKEYE_MARGIN_OF_ERROR
    renp = get_run_expectency_numpy()
    rednp = get_run_expectency_difference_numpy()


    def __init__(self,
                 gamePk: int = None,
                 game: Game = None):

        if game is not None:
            self.game = game
        elif gamePk is not None:
            game_dict = get_game_dict(gamePk)
            self.game = Game(game_dict)
        else:
            raise ValueError('gamePk and game arguments not provided')

        self.gamePk = game.gamePk
        self.num_missed_calls = 0
        self.missed_calls: List[PlayEvents] = []
        self.home_favor = 0
        self.away_abv = game.gameData.teams.away.abbreviation
        self.home_abv = game.gameData.teams.home.abbreviation


    def set(self, print_missed_calls: bool = False
            ) -> Tuple[int, float, List[PlayEvents]]:
        """
        A instance method that runs the Umpire.find_missed_calls class
        method and inputs the results directly into the Umpire instance

        Args:
            print_missed_calls (bool, optional): _description_.
                Defaults to False.
        """

        stats = self.find_missed_calls(game=self.game,
                                     print_missed_calls=print_missed_calls)

        self.num_missed_calls, self.home_favor, self.missed_calls = stats

    @classmethod
    def find_missed_calls(cls, game: Game = None, gamePk: int = None,
                          print_missed_calls: bool = False
                          ) -> Tuple[int, float, List[PlayEvents]]:
        """
        Calculates total favored runs for the home team for a given
        team. Itterates through every pitch in a given game and finds
        pitches that the umpire missed. When home_favor >0, umpire gave
        the home team runs. When <0, gave runs to the away team

        Args:
            game (Game, optional): A Game class from get.game. Takes
                priority over gamePk argument. Defaults to None.
            gamePk (int, optional): A gamePk for the desired game.
                Useful to avoid manually creating Game class before
                running this method. Defaults to None.
            print_missed_calls (bool, optional): Prints info for each
                missed call in a game. Including inning, pitcher, batter,
                count, pitch location, strike zone info, and favor.
                Defaults to False.

        Raises:
            ValueError: If game and gamePk are not provided
            ConnectionError: If connection to API fails

        Returns:
            Tuple[int, float, List[PlayEvents]]: The number of missed
                calls, the home favor, and a list of pitches that were
                all called wrong in the given game
        """
        if game is None and gamePk is not None:
            game_dict = get_game_dict(gamePk)
            game = Game(game_dict)
        elif game is None and gamePk is None:
            raise ValueError('game and gamePk not provided')

        j = 1

        home_favor: float = 0
        missed_calls: List[PlayEvents] = []
        runners = Runners()

        for at_bat in game.liveData.plays.allPlays:
            runners.new_batter(at_bat)
            isTopInning = at_bat.about.isTopInning

            for i in at_bat.pitchIndex:
                pitch: PlayEvents = at_bat.playEvents[i]
                home_delta = Umpire.delta_favor_dist(pitch, isTopInning,
                                                     runners=runners)

                if home_delta != 0:
                    home_favor += home_delta
                    missed_calls.append(pitch)

                    if print_missed_calls is True:
                        print(cls._missed_pitch_details(
                            at_bat, runners, pitch, home_delta,j))
                        j += 1

            runners.end_batter(at_bat)

        return (len(missed_calls), home_favor, missed_calls)


    @classmethod
    def _missed_pitch_details(cls, at_bat: AllPlays, runners: Runners,
                              pitch: PlayEvents, home_delta: float, i: int
                              ) -> str:
        """Helper method to find_missed_calls"""
        to_print_str = ''

        half_inn = at_bat.about.halfInning.capitalize()
        inning = at_bat.about.inning
        pitcher_name = at_bat.matchup.pitcher.fullName
        batter_name = at_bat.matchup.batter.fullName

        to_print_str += f'{i}: {half_inn} {inning}\n'
        to_print_str += f'{pitcher_name} to {batter_name}\n'

        if pitch.count.outs == 1:
            to_print_str += f'{pitch.count.outs} out, '
        else:
            to_print_str += f'{pitch.count.outs} outs, '

        to_print_str += f'{str(runners)}\n'

        balls = pitch.count.balls
        strikes = pitch.count.strikes

        if pitch.details.code == 'C':
            to_print_str += f'{balls}-{strikes-1}, ball called strike\n'
        elif pitch.details.code == 'B':
            to_print_str += f'{balls-1}-{strikes}, strike called ball\n'


        to_print_str += (f'pX = {pitch.pitchData.coordinates.pX:.5f} | '
                        f'pZ = {pitch.pitchData.coordinates.pZ:.5f}\n')

        to_print_str += (f'left: {pitch.pitchData.coordinates.PX_MIN:.5f} | '
                         f'right: {pitch.pitchData.coordinates.PX_MAX:.5f}\n')

        to_print_str += (f'bot = {pitch.pitchData.coordinates.pZ_bot:.5f} | '
                        f'top = {pitch.pitchData.coordinates.pZ_top:.5f}\n')

        to_print_str += f'Home Favor: {home_delta:4.2f}\n'

        return to_print_str


    @classmethod
    def delta_favor_zone(cls, pitch: PlayEvents, isTopInning: bool,
                         runners: Runners = None, runners_int: int = None,
                         ) -> float:
        """
        Calculates the favored runs the umpire gave the home team if
        a pitch is missed based of the zone number of the pitch.

        The zone number is a single digit (1-9) if the pitch is a strike
        and a two digit number (11-14) if the pitch is a ball. MLB
        calculates the zone number automatically reducing the amount of
        work this function needs. Unfortunately most places that
        calculate umpire missed calls use some sort of buffer zone
        that allows for a pitch to miss by some amount while still
        giving the umpire the correct call

        Args:
            pitch (PlayEvents): The pitch data from the game.PlayEvents
                class. The PlayEvents class holds all the pitch data
            isTopInning (bool): A boolean that represents if its the
                top inning. Flips the sign of the result to adjust for
                top/bottom of inning
            runners (Runners, optional): The Runners class that holds
                data for runners locations. Takes priority over
                runners_int. Defaults to None
            runners_int (int, optional): The integer representation for
                base runner locations. Can be obtained by using
                int(Runners) where Runners is the Runners class.
                Defaults to None

        Raises:
            ValueError: If no runners or runners_int argument provided
            TypeError: If runners_int argument is not type int
            TypeError: If isTopInning argument is not type bool

        Returns:
            floa): The amount of runs the umpire gave for a pitch. 0 if
                pitch is swung or correct call was made.
        """
        if runners_int is None and runners is None:
            raise ValueError('No runners_int or runners argument provided')
        if isinstance(runners_int, int) is False and runners_int is not None:
            raise TypeError('runners_int should be type int')
        if isinstance(isTopInning, bool) is False:
            raise TypeError('isTopInning should be type bool')

        if runners is not None:
            runners_int = int(runners)

        home_delta = 0

        correct = True

        balls = pitch.count.balls
        strikes = pitch.count.strikes
        outs = pitch.count.outs

        runners = runners_int

        if pitch.details.code in ('C', 'B'):
            correct = Umpire._is_correct_call_zone_num(pitch)

        if correct is True:
            return 0
        if pitch.details.code == 'C':
            # Ball called Strike
            home_delta += Umpire.rednp[balls][strikes-1][outs][runners]

        elif pitch.details.code == 'B':
            # Strike called Ball
            home_delta -= Umpire.rednp[balls-1][strikes][outs][runners]

        if isTopInning is True:
            return home_delta
        return -home_delta


    @classmethod
    def delta_favor_dist(cls, pitch: PlayEvents, isTopInning: bool,
                         runners: Runners = None, runners_int: int = None
                         ) -> float:
        """
        Calculates the favored runs the umpire gave the home team if
        a pitch is missed based of the distance the pitch was from the
        edges of the zone

        Most places that calculate missed calls made by umpires define
        a grace area that a pitch can land on and the correct call be
        made. That is what this method uses. If a pitch is within
        a certain distance from the edges of the strike zone, it returns
        0 because that pitch can be called a ball or strike and still
        be correct. If a pitch falls outside the grace area, the home
        favor will be calculated off the zone number due to its speed

        Args:
            pitch (PlayEvents): The pitch data from the game.PlayEvents
                class. The PlayEvents class holds all the pitch data
            isTopInning (bool): A boolean that represents if its the
                top inning. Flips the sign of the result to adjust for
                top/bottom of inning
            runners (Runners, optional): The Runners class that holds
                data for runners locations. Takes priority over
                runners_int. Defaults to None
            runners_int (int, optional): The integer representation for
                base runner locations. Can be obtained by using
                int(Runners) where Runners is the Runners class.
                Defaults to None

        Raises:
            ValueError: If not runners or runners_int arugments provided
            TypeError: If runners_int argument is not type int
            TypeError: If isTopInning argument is not type bool

        Returns:
            float: The amount of runs the umpire gave for  pitch. 0 if
                pitch is swung or correct call was made.
        """
        if runners is None and runners_int is None:
            raise ValueError('runners and runners_int were not provided')
        if isinstance(runners_int, int) is False and runners_int is not None:
            raise TypeError('runners_int should be type int')
        if isinstance(isTopInning, bool) is False:
            raise TypeError('isTopInning should be type bool')

        if runners is not None:
            runners_int = int(runners)

        if pitch.pitchData is None:
            return 0

        if pitch.pitchData.coordinates.is_valid() is False:
            return 0

        if Umpire._in_buffer_zone(pitch) is True:
            return 0

        return Umpire.delta_favor_zone(pitch=pitch,
                                       runners_int=runners_int,
                                       isTopInning=isTopInning)


    @classmethod
    def delta_favor_monte(cls, pitch: PlayEvents, isTopInning: bool,
                          runners: Runners = None, runners_int: int = None
                          ) -> float:
        """
        Claculates the favored runs the umpire gave the home team if
        a pitch is missed based off potential pitch locations

        The Hawkeye tracking system is not perfect and can miss a
        pitches real location by up to a quarter of an inch. This method
        calculates 500 potential pitch locations that the real pitch
        location could have been. For a pitch to be a missed call one
        of the two scenarios must be true:
        1. Called ball but >90% of simulated pitches were balls
        2. Called strike but >90% of simulated pitches were strikes

        This is what UmpScorecards claims they do but I do not believe
        it after some testing. I believe they use the delta_favor_dist()
        method instead
        https://umpscorecards.com/explainers/accuracy

        Args:
            pitch (PlayEvents): The pitch data from the game.PlayEvents
                class. The PlayEvents class holds all the pitch data
            isTopInning (bool): A boolean that represents if its the
                top inning. Flips the sign of the result to adjust for
                top/bottom of inning
            runners (Runners, optional): The Runners class that holds
                data for runners locations. Takes priority over
                runners_int. Defaults to None. Defaults to None.
            runners_int (int, optional): The integer representation for base
                runner locations. Can be obtained by using int(Runners)
                where Runners is the Runners class. Defaults to None

        Raises:
            ValueError: _description_
            TypeError: _description_
            TypeError: _description_

        Returns:
            float: _description_
        """
        if runners is None and runners_int is None:
            raise ValueError('runners and runners_int were not provided')
        if isinstance(runners_int, int) is False:
            raise TypeError('runners_int should be type int')
        if isinstance(isTopInning, bool) is False:
            raise TypeError('isTopInning should be type bool')

        if runners is not None:
            runners_int = int(runners)

        home_delta = 0

        correct = True

        balls = pitch.count.balls
        strikes = pitch.count.strikes
        outs = pitch.count.outs

        runners = runners_int

        if pitch.pitchData is None:
            return 0

        if pitch.pitchData.coordinates.is_valid() is False:
            return 0

        if pitch.details.code in ('C', 'B'):
            correct = Umpire._is_correct_call_monte_carlo(pitch)

        if correct is True:
            return 0

        if pitch.details.code == 'C':
            # Ball called Strike
            home_delta += Umpire.rednp[balls][strikes-1][outs][runners]
        elif pitch.details.code == 'B':
            # Strike called Ball
            home_delta -= Umpire.rednp[balls-1][strikes][outs][runners]

        if isTopInning is True:
            return home_delta
        return -home_delta


    @classmethod
    def _is_correct_call_zone_num(cls, pitch: PlayEvents) -> bool:
        """Helper method to delta_favor_zone"""
        if pitch.details.code == 'C' and pitch.pitchData.zone > 10:
            return False
        if pitch.details.code == 'B' and 1 <= pitch.pitchData.zone <= 9:
            return False
        return True


    @classmethod
    def _is_correct_call_monte_carlo(cls, pitch: PlayEvents) -> bool:
        """Helper method to delta_favor_zone"""
        strike = 0
        ball = 0

        pX_left = pitch.PX_MIN
        pX_right = pitch.PX_MAX
        pZ_top = pitch.pitchData.coordinates.pZ_top
        pZ_bot = pitch.pitchData.coordinates.pZ_bot

        for _ in range(1, 501):
            rand_x, rand_z = Umpire._generage_random_pitch_location(pitch)

            if pX_left <= rand_x <= pX_right and pZ_bot <= rand_z <= pZ_top:
                strike += 1
            else:
                ball += 1

        total = ball + strike

        if pitch.details.code == 'B' and ((strike / total) > 0.90):
            return False
        if pitch.details.code =='C' and ((ball / total) > 0.90):
            return False
        return True


    @classmethod
    def _in_buffer_zone(cls, pitch: PlayEvents) -> bool:
        buf = BUFFER_FEET # buffer in feet but short

        pX = pitch.pitchData.coordinates.pX
        pZ = pitch.pitchData.coordinates.pZ

        pZ_top = pitch.pitchData.coordinates.pZ_top
        pZ_bot = pitch.pitchData.coordinates.pZ_bot

        pX_left = pitch.pitchData.coordinates.PX_MIN
        pX_right = pitch.pitchData.coordinates.PX_MAX

        # left zone
        if (((pX_left - buf) <= pX <= (pX_left + buf)) and
            ((pZ_bot - buf) <= pZ <= (pZ_top + buf))):
            return True

        # right zone
        if (((pX_right - buf) <= pX <= (pX_right + buf)) and
            ((pZ_bot - buf) <= pZ <= (pZ_top + buf))):
            return True

        # top zone
        if (((pZ_top - buf) <= pZ <= (pZ_top + buf)) and
            ((pX_left - buf) <= pX <= (pX_right + buf))):
            return True

        # bottom zone
        if (((pZ_bot - buf) <= pZ <= (pZ_bot + buf)) and
            (pX_left - buf) <= pX <= (pX_right + buf)):
            return True

        return False


    @classmethod
    def _generage_random_pitch_location(cls, pitch: PlayEvents
                                        ) -> Tuple[float, float]:
        """Helper method to delta_favor_zone"""
        moe = HAWKEYE_MARGIN_OF_ERROR
        pX = pitch.pitchData.coordinates.pX
        pZ = pitch.pitchData.coordinates.pZ

        delta_radius = random.uniform(-moe, moe)
        angle = random.uniform(0, 360)
        angle = math.radians(angle)

        dx = delta_radius * math.cos(angle)
        dz = delta_radius * math.sin(angle)

        rand_x = pX + dx
        rand_z = pZ + dz

        return (rand_x, rand_z)


    def __len__(self):
        return len(self.missed_calls)


    def __str__(self):
        prt_str = ''

        prt_str += f'{len(self.missed_calls)} Missed Calls. '
        prt_str += f'{self.home_favor} Home Favor'

        return prt_str
