"""
This module will print the details for the most recent pitch in a MLB
and MiLB games provided with a gamePk from the MLB/MiLB website

You can find the gamePk for a given game by going to the 'Gameday'
section of the desired game and by looking for a string of 6 consecutive
numbers in the url.
"""

import curses
import sys
import argparse
from typing import Tuple
from get.game import Game, PlayEvents, AllPlays
from get.statsapi_plus import get_game_dict, get_run_expectency_numpy
from get.umpire import Umpire
from get.runners import Runners


def print_last_pitch(gamePk: int = None,
                     delay: float = 0):
    """
    Prints the following for the latest pitch:
    
    1. Away/Home teams + score
    2. Inning
    3. Count
    4. Pitcher and Batter name

    Pitch Details:
    5. Pitch Result
    6. Pitch Speed + Name
    7. Spin Rate
    8. If pitch was in zone + home favor if missed call

    Hit Details:
    9. Exit Velocity
    10. Launch Angle
    11. Total Distance

    Args:
        gamePk (int): The gamePk for the desired
        delay (float, optional): The numbers of seconds you want the
            output to be delayed. Useful so that pitch info does not
            show up before pitch is thrown on TV. Defaults to 0
    """
    print(f'gamePk: {gamePk}, delay: {delay}')

    if gamePk is None:
        raise ValueError('gamePk not provided')

    clr = ' ' * 40
    god = curses.initscr()

    while True:
        try:
            game = Game(get_game_dict(gamePk=gamePk, delay_seconds=delay))
            at_bat = game.liveData.plays.allPlays[-1]

            if len(at_bat.playEvents) > 0:
                pitch = at_bat.playEvents[-1]

                i = 0
                for line in _get_game_details(game, at_bat):
                    god.addstr(i, 0, f'{line} {clr}')
                    i += 1

                for line in _get_at_bat_details(at_bat, pitch):
                    god.addstr(i, 0, f'{line} {clr}')
                    i += 1

                i += 1
                for line in _get_run_details(game, at_bat, pitch):
                    god.addstr(i, 0, f'{line} {clr}')
                    i += 1

                i += 1
                for line in _get_pitch_details(pitch):
                    god.addstr(i, 0, f'{line} {clr}')
                    i += 1

                i += 1
                for line in _get_hit_details(pitch):
                    god.addstr(i, 0, f'{line} {clr}')
                    i += 1

                god.refresh()

        except KeyboardInterrupt:
            sys.exit()


def _get_game_details(game: Game, at_bat: AllPlays) -> Tuple[str, str]:
    away_team = game.gameData.teams.away.teamName
    away_score = at_bat.result.awayScore
    home_team = game.gameData.teams.home.teamName
    home_score = at_bat.result.homeScore

    half_inn = at_bat.about.halfInning.capitalize()
    inning = at_bat.about.inning

    line_0 = f'{away_team} ({away_score}) at {home_team} ({home_score})'
    line_1 = f'{half_inn} {inning}'
    return (line_0, line_1)


def _get_at_bat_details(at_bat: AllPlays,
                        pitch: PlayEvents) -> Tuple[str, str, str]:
    pitcher = at_bat.matchup.pitcher.fullName
    batter = at_bat.matchup.batter.fullName

    balls = pitch.count.balls
    strikes = pitch.count.strikes
    outs = pitch.count.outs

    runners = Runners()
    # end_batter method sets the runners which is why its used here
    # might have errors with walks?
    runners.end_batter(runners)

    line_0 = f'{pitcher} to {batter}'
    line_1 = f'{balls}-{strikes} | {outs} Outs'
    line_2 = f'{str(runners)}'

    return (line_0, line_1, line_2)


def _get_run_details(game: Game,
                     at_bat: AllPlays,
                     pitch: PlayEvents) -> Tuple[str, str]:

    away_team = game.gameData.teams.away.abbreviation
    home_team = game.gameData.teams.home.abbreviation

    balls = pitch.count.balls
    strikes = pitch.count.strikes
    outs = pitch.count.outs
    runners = int(at_bat.runners)

    renp = get_run_expectency_numpy()
    run_exp = renp[balls][strikes][outs][runners]

    misses, favor, _ = Umpire.find_missed_calls(game=game)

    line_0 = f'Expected Runs: {run_exp:.2f}'

    if favor < 0:
        line_1 = f'Ump Favor: {-favor:+5.2f} {away_team} ({misses})'
    else:
        line_1 = f'Ump Favor: {favor:+5.2f} {home_team} ({misses})'

    return (line_0, line_1)


def _get_pitch_details(pitch: PlayEvents) -> Tuple[str, str, str, str, str]:
    if pitch.isPitch is True:
        desc = pitch.details.description
        speed = pitch.pitchData.startSpeed
        pitch_type = pitch.details.type.description
        spin_rate = pitch.pitchData.breaks.spinRate

        line_0 = 'Pitch Details: '
        line_1 = f'{desc}'
        line_2 = f'{speed} {pitch_type}'
        line_3 = f'{spin_rate} RPM'
        line_4 = f'Zone: {pitch.pitchData.zone}'
    else:
        desc = pitch.details.description

        line_0 = 'Pitch Details: '
        line_1 = f'{desc}'
        line_2 = ''
        line_3 = ''
        line_4 = ''

    return (line_0, line_1, line_2, line_3, line_4)


def _get_hit_details(pitch: PlayEvents) -> Tuple[str, str, str, str]:
    if pitch.hitData is not None:
        exit_velo = pitch.hitData.launchSpeed
        launch_angle = pitch.hitData.launchAngle
        distance = pitch.hitData.totalDistance

        line_0 = 'Hit Details:'
        line_1 = f'Exit Velo: {exit_velo}'
        line_2 = f'Launch Angle: {launch_angle}'
        line_3 = f'Total Dist: {distance}'
    else:
        line_0 = ''
        line_1 = ''
        line_2 = ''
        line_3 = ''

    return (line_0, line_1, line_2, line_3)


def main():
    """
    Main function that grabs system arguments and runs code
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-g', '--gamepk', help = 'gamePk', type=int)
    parser.add_argument('-d', '--delay', help='delay in seconds', type=int)
    args = parser.parse_args()

    if args.gamepk is not None:
        gamePk = args.gamepk
    else:
        gamePk = int(input('gamePk: '))

    if args.delay is not None:
        delay = args.delay
    else:
        delay = float(input('delay: '))

    print_last_pitch(gamePk, delay=delay)


if __name__ == '__main__':
    main()