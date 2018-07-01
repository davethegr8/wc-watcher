import requests
import json
import os.path
from enum import Enum
import signal
import sys
import time
from datetime import datetime
import private

def sigterm_handler(_signo, _stack_frame):
    sys.exit(0)

signal.signal(signal.SIGTERM, sigterm_handler)

# 17 for only WC matches, None for everything
WC_COMPETITION = private.WC_COMPETITION

FIFA_URL = 'https://api.fifa.com/api/v1'
# NOW_URL = '/live/football/'
NOW_URL = '/live/football/now'
MATCH_URL = '/timelines/{}/{}/{}/{}?language=en-US' # IdCompetition/IdSeason/IdStage/IdMatch
PLAYER_URL = ''
TEAM_URL = ''

class EventType(Enum):
    GOAL_SCORED = 0
    YELLOW_CARD = 2
    RED_CARD = 3
    DOUBLE_YELLOW = 4
    SUBSTITUTION = 5
    IGNORE = 6
    MATCH_START = 7
    HALF_END = 8
    BLOCKED_SHOT = 12
    FOUL_UNKNOWN = 14
    OFFSIDE = 15
    CORNER_KICK = 16
    BLOCKED_SHOT_2 = 17
    FOUL = 18
    UNKNOWN_3 = 22
    UNKNOWN_2 = 23
    MATCH_END = 26
    CROSSBAR = 32
    CROSSBAR_2 = 33
    OWN_GOAL = 34
    FREE_KICK_GOAL = 39
    PENALTY_GOAL = 41
    PENALTY_MISSED = 60
    UNKNOWN = 9999

    @classmethod
    def has_value(cls, value):
        return any(value == item.value for item in cls)

class Period(Enum):
    FIRST_PERIOD = 3
    SECOND_PERIOD = 5
    PENALTY_SHOOTOUT = 11

def get_current_matches():
    matches = []
    players = {}
    headers = {'Content-Type': 'application/json'}

    print(str(datetime.now()), "getting current matches", flush=True)
    try:
        # print(FIFA_URL + NOW_URL, flush=True)
        r = requests.get(url=FIFA_URL + NOW_URL, headers=headers)
        r.raise_for_status()
    except requests.exceptions.HTTPError as ex:
        return matches, players

    for match in r.json()['Results']:
        id_competition = match['IdCompetition']

        # print(str(WC_COMPETITION), str(id_competition), str(WC_COMPETITION) != str(id_competition), flush=True)
        if str(WC_COMPETITION) and str(WC_COMPETITION) != str(id_competition):
            continue

        id_season = match['IdSeason']
        id_stage = match['IdStage']
        id_match = match['IdMatch']
        home_team_id = match['HomeTeam']['IdTeam']
        for entry in match['HomeTeam']['TeamName']:
            home_team_name = entry['Description']
        away_team_id = match['AwayTeam']['IdTeam']
        for entry in match['AwayTeam']['TeamName']:
            away_team_name = entry['Description']
        if not id_competition or not id_season or not id_stage or not id_match:
            print('Invalid match information', flush=True)
            continue

        matches.append({'idCompetition': id_competition, 'idSeason': id_season, 'idStage': id_stage, 'idMatch': id_match, 'homeTeamId': home_team_id,
        'homeTeam': home_team_name, 'awayTeamId': away_team_id, 'awayTeam': away_team_name, 'events': []})

        for player in match['HomeTeam']['Players']:
            player_id = player['IdPlayer']
            for player_details in player['ShortName']:
                player_name = player_details['Description']
            players[player_id] = player_name

        for player in match['AwayTeam']['Players']:
            player_id = player['IdPlayer']
            for player_details in player['ShortName']:
                player_name = player_details['Description']
            players[player_id] = player_name

    return matches, players

def get_match_events(idCompetition, idSeason, idStage, idMatch):
    events = {}
    headers = {'Content-Type': 'application/json'}
    match_url = FIFA_URL + MATCH_URL.format(idCompetition, idSeason, idStage, idMatch)

    try:
        print(str(datetime.now()), 'getting ' + match_url, flush=True)
        r = requests.get(match_url, headers=headers)
        r.raise_for_status()
    except requests.exceptions.HTTPError as ex:
        return events

    for event in r.json()['Event']:
        eId = event['EventId']
        new_event = {}
        new_event['type'] = event['Type']
        new_event['team'] = event['IdTeam']
        new_event['player'] = event['IdPlayer']
        new_event['time'] = event['MatchMinute']
        new_event['home_goal'] = event['HomeGoals'] if event['HomeGoals'] is not None else 0
        new_event['away_goal'] = event['AwayGoals'] if event['AwayGoals'] is not None else 0
        new_event['sub'] = event['IdSubPlayer']
        new_event['period'] = event['Period']
        new_event['home_pgoals'] = event['HomePenaltyGoals']
        new_event['away_pgoals'] = event['AwayPenaltyGoals']
        new_event['url'] = match_url
        events[eId] = new_event
    return events

def build_event(player_list, current_match, event):
    event_message = ''

    # print(event)
    # print(current_match)
    # print(player_list, flush=True)

    player = player_list.get(event['player'])
    sub_player = player_list.get(event['sub'])
    active_team = current_match['homeTeam'] if event['team'] == current_match['homeTeamId'] else current_match['awayTeam']

    extraInfo = False

    if (event['type'] == EventType.GOAL_SCORED.value):
        return message_goal(player_list, current_match, event)
    elif (event['type'] == EventType.FREE_KICK_GOAL.value):
        return message_goal(player_list, current_match, event)
    elif (event['type'] == EventType.FREE_KICK_GOAL.value):
        return message_goal(player_list, current_match, event)
    elif event['type'] == EventType.YELLOW_CARD.value:
        return message_yellow(player_list, current_match, event)
    elif event['type'] == EventType.RED_CARD.value:
        return message_red(player_list, current_match, event)
    elif event['type'] == EventType.DOUBLE_YELLOW.value:
        return message_second_yellow(player_list, current_match, event)
    elif event['type'] == EventType.SUBSTITUTION.value:
        return message_sub(player_list, current_match, event)
    elif event['type'] == EventType.MATCH_START.value:
        return message_halfstart(player_list, current_match, event)
    elif event['type'] == EventType.HALF_END.value:
        return message_halfend(player_list, current_match, event)
    elif event['type'] == EventType.MATCH_END.value:
        return message_final(player_list, current_match, event)
    elif event['type'] == EventType.OWN_GOAL.value:
        return message_owngoal(player_list, current_match, event)
    elif event['type'] == EventType.PENALTY_GOAL.value:
        return message_penalty_goal(player_list, current_match, event)
    elif event['type'] == EventType.PENALTY_MISSED.value:
        return message_penalty_miss(player_list, current_match, event)
    elif EventType.has_value(event['type']):
        event_message = None
    elif private.DEBUG:
        event_message = 'Missing event information for {} vs {}: Event {}\n{}'.format(current_match['homeTeam'], current_match['awayTeam'], event['type'], event['url'])
    else:
        event_message = None

    return event_message

def save_matches(match_list):
    with open('match_list.txt', 'w') as file:
        file.write(json.dumps(match_list))

def load_matches():
    if not os.path.isfile('match_list.txt'):
        return {}
    with open('match_list.txt', 'r') as file:
        content = file.read()
    return json.loads(content) if content else {}

def message_goal(player_list, current_match, event):
    player = player_list.get(event['player'])
    active_team = current_match['homeTeam'] if event['team'] == current_match['homeTeamId'] else current_match['awayTeam']

    if (player is not None):
        message = '{} :soccer: Goal! Scored by {} ({})'
        message = message.format(event['time'], player, active_team)
    else:
        message = '{} :soccer: Goal for {}!'
        message = message.format(event['time'], active_team)

    return message

def message_owngoal(player_list, current_match, event):
    player = player_list.get(event['player'])
    active_team = current_match['homeTeam'] if event['team'] == current_match['homeTeamId'] else current_match['awayTeam']

    event_message = '{} :soccer: Own Goal by {} ({})!'
    return event_message.format(event['time'], player, active_team)

def message_halfstart(player_list, current_match, event):
    period = None
    if event['period'] == Period.FIRST_PERIOD.value:
        return '{} Kickoff!'.format(event['time'])
    elif event['period'] == Period.SECOND_PERIOD.value:
        return '{} Second half kickoff!'.format(event['time'])
    elif event['period'] == Period.PENALTY_SHOOTOUT.value:
        return '{} The penalty shootout is starting'.format(event['time'])
    else:
        return '{} {} vs {} has restarted!'.format(event['time'], current_match['homeTeam'], current_match['awayTeam'])

def message_halfend(player_list, current_match, event):
    period = None
    if event['period'] == Period.FIRST_PERIOD.value:
        period = 'first'
    elif event['period'] == Period.SECOND_PERIOD.value:
        period = 'second'
    elif event['period'] == Period.PENALTY_SHOOTOUT.value:
        event_message = '{} The penalty shootout is over.'.format(event['time'])
    else:
        period = 'invalid'
        event_message = '{} End of the half.'.format(event['time'])
    if period is not None:
        event_message = '{} End of the {} half.'.format(event['time'], period)

    return event_message

def message_final(player_list, current_match, event):
    message = 'Final'
    return message.format()

def message_yellow(player_list, current_match, event):
    player = player_list.get(event['player'])
    active_team = current_match['homeTeam'] if event['team'] == current_match['homeTeamId'] else current_match['awayTeam']

    message = '{} ' + private.YELLOW_CARD_EMOJI + ' Yellow card for {} ({})';

    return message.format(event['time'], player, active_team)

def message_second_yellow(player_list, current_match, event):
    player = player_list.get(event['player'])
    active_team = current_match['homeTeam'] if event['team'] == current_match['homeTeamId'] else current_match['awayTeam']

    message = '{} ' + private.YELLOW_CARD_EMOJI + ' ' + private.RED_CARD_EMOJI + ' Second yellow card for {} ({})';

    return message.format(event['time'], player, active_team)

def message_red(player_list, current_match, event):
    player = player_list.get(event['player'])
    active_team = current_match['homeTeam'] if event['team'] == current_match['homeTeamId'] else current_match['awayTeam']

    message = '{} ' + private.RED_CARD_EMOJI + ' Red card for {} ({})';

    return message.format(event['time'], player, active_team)

def message_sub(player_list, current_match, event):
    player = player_list.get(event['player'])
    sub_player = player_list.get(event['sub'])
    active_team = current_match['homeTeam'] if event['team'] == current_match['homeTeamId'] else current_match['awayTeam']

    event_message = '{} Substitution for {}.'.format(event['time'], active_team)

    if player and sub_player:
        event_message += ' :arrow_left: Out: {} :arrow_right: In: {}'.format(sub_player, player)

    return event_message

def message_penalty_goal(player_list, current_match, event):
    player = player_list.get(event['player'])
    active_team = current_match['homeTeam'] if event['team'] == current_match['homeTeamId'] else current_match['awayTeam']

    if event['period'] == Period.PENALTY_SHOOTOUT.value:
        event_message = ':soccer: Penalty goal for {}!'.format(active_team)
    else:
        event_message = '{} :soccer: Penalty goal for {}!'.format(event['time'], active_team)

    return event_message

def message_penalty_miss(player_list, current_match, event):
    player = player_list.get(event['player'])
    active_team = current_match['homeTeam'] if event['team'] == current_match['homeTeamId'] else current_match['awayTeam']

    if event['period'] == Period.PENALTY_SHOOTOUT.value:
        event_message = ':no_entry_sign: Penalty missed by {}!'.format(active_team)
    else:
        event_message = '{} :no_entry_sign: Penalty missed by {}!'.format(event['time'], active_team)

    return event_message

def check_for_updates():
    events = []
    match_list = load_matches()
    player_list = {}
    live_matches, players = get_current_matches()
    for match in live_matches:
        if not match['idMatch'] in match_list:
            match_list[match['idMatch']] = match

    for player in players:
        if not player in player_list:
            player_list[player] = players[player]

    done_matches = []
    for match in match_list:
        current_match = match_list[match]

        event_list = get_match_events(current_match['idCompetition'], current_match['idSeason'], current_match['idStage'], current_match['idMatch'])

        for event in event_list:
            current_event = event_list[event]

            # debugging
            if event in current_match['events']:
                continue # We already reported the event, skip it

            event_notification = build_event(player_list, current_match, current_event)

            current_match['events'].append(event)
            if not event_notification is None:
                if current_event['period'] == Period.PENALTY_SHOOTOUT.value:
                    event_notification += ' {} {} ({}):{} ({}) {}'.format(current_match['homeTeam'], event['home_goal'], event['home_pgoals'], event['away_goal'], event['away_pgoals'], current_match['awayTeam'])
                else:
                    event_notification += ' {} {}:{} {}'.format(current_match['homeTeam'], current_event['home_goal'], current_event['away_goal'], current_match['awayTeam'])

                events.append(event_notification)

            if current_event['type'] == EventType.MATCH_END.value:
                done_matches.append(match)

    # debugging
    for match in done_matches:
        del match_list[match]

    save_matches(match_list)

    return events

def send_event(event, url=private.WEBHOOK_URL):
    print(str(datetime.now()), "send_event()", event, flush=True)

    with open('events.txt', 'a') as file:
        file.write(event + "\n")

    headers = {'Content-Type': 'application/json'}
    payload = {
        'text': event,
        'channel': private.SLACK_CHANNEL,
        'username': private.SLACK_USERNAME,
        'icon_emoji': private.SLACK_AVATAR
    }

    try:
        r = requests.post(url, data=json.dumps(payload), headers=headers)
        # print(r.json(), flush=True)
        r.raise_for_status()
    except requests.exceptions.HTTPError as ex:
        print('Failed to send message: {}'.format(ex), flush=True)
        return
    except requests.exceptions.ConnectionError as ex:
        print('Failed to send message: {}'.format(ex), flush=True)
        return


def main():
    print("main()", flush=True)

    while True:
        print(str(datetime.now()), "getting events", flush=True)
        events = check_for_updates()
        for event in events:
            # print(event, flush=True)
            send_event(event)
        time.sleep(60)

    print("ohno", flush=True)

if __name__ == '__main__':
    with open('events.txt', 'w') as file:
        file.write("")

    # send_event("`soccerbot: starting up`")

    try:
        main()
    except:
        pass
    finally:
        # send_event("`soccerbot: shutting down`")
        pass

