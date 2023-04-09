import streamlit as st
import pandas as pd
from streamlit_option_menu import option_menu
import statsapi
import requests
from collections import defaultdict
from enum import Enum
from streamlit_folium import folium_static
import folium
import json
from datetime import datetime
import altair as alt
import os
import time
import re

st.set_page_config(
    page_title="MLB Insights",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': f'''
        MLB Insights is the ultimate site for baseball fans who want to stay up-to-date on the latest player statistics and profiles.

        **Developed by:** Sebastian Nunez ({datetime.now().year})

        Did you know that we have an `easter egg` *hidden* somewhere on the site? To find it, you'll need to use your skills as a detective and delve into the **HTML source code**. Keep your eyes peeled for any clues that might lead you to the hidden gem. Who knows what kind of insights or fun surprises you might uncover? Happy hunting!
        '''
    }
)

selected_player = None
BALLPARKS_JSON_PATH = './ballsparks.json'
EMAILS_FILE_PATH = './emails.json'
EMAIL_PATTERN = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"


class Page(Enum):
    WHY_US = 'Why Us?'
    SEARCH_ENGINE = 'Search Engine'
    LEAGUE_LEADERS = 'League Leaders'
    BALLPARKS = 'Ball Parks'


def main():
    # default page
    page = Page.SEARCH_ENGINE.value

    # sidebar
    with st.sidebar:
        page = option_menu("MLB Insights", [Page.SEARCH_ENGINE.value, Page.LEAGUE_LEADERS.value, Page.BALLPARKS.value, Page.WHY_US.value, ],
                           icons=['search', 'list-task', 'geo-alt', 'info-circle'], menu_icon="body-text", default_index=0)

    # main content
    if page == Page.SEARCH_ENGINE.value:
        display_player_search()
    elif page == Page.LEAGUE_LEADERS.value:
        display_league_leaders()
    elif page == Page.BALLPARKS.value:
        display_ballparks()
    elif page == Page.WHY_US.value:
        display_benefits()
    else:
        page = Page.SEARCH_ENGINE.value


class Player:
    def __init__(self, info):
        self.name = info.get('fullName')
        self.id = info.get('id')
        self.number = info.get('primaryNumber')
        self.position = info.get('primaryPosition').get('abbreviation')

    def __repr__(self) -> str:
        return f'{self.name} ({self.id})'


def display_player_search():
    global selected_player

    st.title('MLB Insights')
    st.caption('MLB Insights is the ultimate site for baseball fans who want to stay up-to-date on the latest player statistics and profiles.')
    st.divider()

    id_to_player = defaultdict(dict)  # id -> Player()
    name_to_id = defaultdict(str)  # name -> id
    name_to_id[''] = None

    all_players = statsapi.lookup_player("")
    if not all_players:
        st.error('No players were found through the StatsAPI!')
        return

    for player in all_players:
        id = player['id']
        name = player['fullName']

        id_to_player[id] = Player(player)
        name_to_id[name] = id

    # sort names alphabetically
    name_to_id = dict(sorted(name_to_id.items(), key=lambda x: x[0]))

    st.header(Page.SEARCH_ENGINE.value)

    player_name = st.selectbox(
        label="Enter a player's name to see their stats!",
        options=name_to_id.keys(),
        help="Enter a player's name then press ENTER...",
    )

    st.divider()

    if player_name != None:
        id = name_to_id[player_name]
        selected_player = id_to_player[id]

    if selected_player:
        # success = st.success(f'You Selected: {player}')
        display_player_info(selected_player)


def display_player_info(player):
    res = requests.get(
        f"http://lookup-service-prod.mlb.com/json/named.player_info.bam?sport_code='mlb'&player_id='{player.id}'")

    if res.status_code == 200:
        res = res.json()

        info = res['player_info']['queryResults']['row']

        city, state, country = info['birth_city'], info['birth_state'], info['birth_country']
        birth_location = ''
        if country:
            if city and state:
                birth_location = f'{city}, {state}, {country}'
            elif city and not state:
                birth_location = f'{city}, {country}'
            elif state and not city:
                birth_location = f'{state}, {country}'
        else:
            birth_location = 'Unknown'

        height = f"{info['height_feet']}' {info['height_inches']}\""
        st.markdown(
            f'''
            # {player.name} ({player.position}) - :red[#{player.number}]
            #### {info['team_name']}
            > **Age:** {info['age']} | **Height:** {height} | **Weight:** {info['weight']}lbs | **Bats/Throws:** {info['bats']}/{info['throws']} | **Status:** {info['status']}
            >
            > **Born:** {birth_location}
            ''')

        data = statsapi.player_stat_data(
            player.id, group="[hitting,pitching]", type='[career,season]', sportId=1)

        if not data:
            st.error(f'Unable to fetch player statistics for {player.name}!')
            return

        career_hitting = None
        career_pitching = None
        season_hitting = None
        season_pitching = None
        for entry in data['stats']:
            type = entry['type']
            group = entry['group']
            stats = entry['stats']

            if type == 'career':
                if group == 'hitting':
                    career_hitting = stats
                elif group == 'pitching':
                    career_pitching = stats
            elif type == 'season':
                if group == 'hitting':
                    season_hitting = stats
                elif group == 'pitching':
                    season_pitching = stats

        display_player_stats(
            career_hitting, career_pitching, season_hitting, season_pitching)
    else:
        st.error(f'Unable to fetch full player info for {player.name}!')


def display_league_leaders():
    st.header(Page.LEAGUE_LEADERS.value)
    st.caption("Find the top performers in the MLB under these categories is a way to identify the players who are having exceptional seasons and contributing significantly to their team's success.")
    st.divider()

    options = {
        'Homeruns': 'homeRuns',
        'Strikeouts': 'strikeouts',
        'Avg': 'battingAverage',
        'ERA': 'earnedRunAverage',
        'RBI': 'runsBattedIn',
        'Errors': 'errors',
    }

    # st.write(statsapi.meta('leagueLeaderTypes'))

    # Parameters
    metric = st.radio("Select a metric:", options.keys(),
                      help='Please visit [MLB Standard Stats](https://www.mlb.com/glossary/standard-stats) to see details!')

    seasons = [year for year in range(datetime.now().year, 1971, -1)]
    selected_season = st.selectbox(
        'Select a season:', seasons, help='Regular season appearances')

    max_results = st.slider('Select the number of results:', 5,
                            100, step=5, value=10)
    st.divider()

    # data fetching
    data = statsapi.league_leader_data(metric, season=selected_season, limit=max_results, statGroup=None,
                                       leagueId=None, gameTypes=None, playerPool=None, sportId=1, statType=None)
    if not data:
        st.error('Unable to fetch data for {metric}!')
        return

    df = pd.DataFrame(data, columns=['Rank', 'Player', 'Team', metric])

    hide_table_row_index = """
        <style>
        thead tr th:first-child {display:none}
        tbody th {display:none}
        </style>
        """

    # Inject CSS with Markdown
    st.markdown(hide_table_row_index, unsafe_allow_html=True)

    st.subheader(
        f'Top {max_results} Players by {metric} ({selected_season})')

    table_tab, chart_tab = st.tabs(['Table', 'Chart'])

    with table_tab:
        st.table(df)

    with chart_tab:

        # horizontal bar chart using Altair
        chart = alt.Chart(df).mark_circle().encode(
            y=alt.Y(metric, sort='-y'),
            x=alt.X('Player', sort='-x'),
            color='Team'
        ).properties(
            width=700,
            height=400,

        )

        # display the chart in Streamlit
        st.altair_chart(chart, use_container_width=True)

    display_signup_form()


def display_ballparks():
    st.header(Page.BALLPARKS.value)
    st.caption('You can find all the MLB stadiums on this map!')
    st.divider()

    if not os.path.exists(BALLPARKS_JSON_PATH):
        st.error(
            f'Unable to fetch Ballpark locations! (fetching from {BALLPARKS_JSON_PATH})')
        return

    with open(BALLPARKS_JSON_PATH, 'r') as f:
        map = folium.Map(location=[40, -95], zoom_start=4)

        data = json.load(f)
        for name, park in data.items():
            lat = park["lat"]
            long = park["long"]
            team = park["team"]
            popup_text = f"{name} ({team})"

            folium.Marker(location=[lat, long],
                          popup=popup_text).add_to(map)

        folium_static(map)
        st.caption('> Please note that the MLB Stadium map is for reference only and may not be up-to-date. We cannot guarantee the accuracy or completeness of the information provided.')

        display_game_pace()

        display_signup_form()


def display_game_pace():
    current_year = datetime.now().year

    st.divider()
    st.header('Game Pace')
    st.markdown(
        f'> With this tool, you can easily compare the general *pace* of baseball games between :red[**1999**] and :red[**{current_year}**] to identify any trends.')

    season1 = st.number_input(
        f"Select a year between 1999 and {current_year}",
        min_value=1999,
        max_value=current_year-1,
        value=2001,
        step=1,
        label_visibility='collapsed'
    )

    st.subheader('vs.')

    season2 = st.number_input(
        f"Select a year between 1999 and {current_year}",
        min_value=season1+1,
        max_value=current_year,
        value=current_year,
        step=1,
        label_visibility='collapsed'
    )

    pace1 = statsapi.game_pace_data(season=season1, sportId=1)['sports'][0]
    pace2 = statsapi.game_pace_data(
        season=season2, sportId=1)['sports'][0]

    if not pace1 or not pace2:
        st.error(f'Unable to compare {season1} to {season2}!')
        return

    # only these selected features can be compared
    data = {
        'season': [],
        'hitsPer9Inn': [],
        'runsPer9Inn': [],
        'pitchesPer9Inn': [],
        'hitsPerGame': [],
        'runsPerGame': [],
        'pitchesPerGame': [],
        'timePerGame': [],
        'timePerPitch': [],
        'pitchesPerPitcher': [],
    }

    for metric in data:
        data[metric].append(pace1[metric])
        data[metric].append(pace2[metric])

    df = pd.DataFrame(data)
    df.set_index('season', inplace=True)

    st.divider()
    st.subheader(f'{season1} vs. {season2}')
    st.bar_chart(df, width=600, height=600, use_container_width=True)


def display_benefits():
    st.title('MLB Insights')
    st.caption('MLB Insights is the ultimate site for baseball fans who want to stay up-to-date on the latest player statistics and profiles.')
    st.divider()

    st.markdown(
        f'''
        ## Benefits

        1. **Easy-to-use interface:** The site is designed with an easy-to-use interface, so you can quickly find the information you need.

        2. **Search functionality:** MLB Insights has a powerful search functionality that allows you to search for specific players, teams, or games.

        3. **Perfect for fantasy baseball:** If you're a serious fantasy baseball player, MLB Insights is the perfect resource to help you make informed decisions about your team.

        4. **Comprehensive player profiles:** With detailed player profiles, you can get a complete picture of a player's performance history, strengths, weaknesses, and more.

        5. **Available 24/7:** MLB Insights is always available, so you can access the site whenever you need it, day or night.

        6. **Free to use:** MLB Insights is completely free to use, so you don't have to worry about paying for a subscription or membership.
        '''
    )

    easter_egg = st.checkbox('Check me... But how? Hmmmmm', disabled=True)
    if easter_egg:
        st.success('Congratulations! You have found the easter egg on the MLB Insights website! Your sharp detective skills have paid off and we are thrilled that you were able to uncover our hidden gem!')
        st.balloons()

    display_signup_form()


def is_valid_email(email):
    if not email:
        return False

    return re.match(EMAIL_PATTERN, email)


def save_email(email):
    if not email:
        st.error('No email was inputted! Unable to save!')
        return

    users = []

    try:
        with open(EMAILS_FILE_PATH, "r") as file:
            users = json.load(file)
    except FileNotFoundError:
        st.error(f'Unable to open {EMAILS_FILE_PATH}!')

    if email not in users:
        users.append(email)

    with open(EMAILS_FILE_PATH, "w") as file:
        json.dump(users, file)


def display_signup_form():
    st.divider()

    with st.form("sign_up", clear_on_submit=True):
        st.markdown(
            f'''
            #### Sign Up for Notifications!
            > Don't miss out on the latest news! Sign up for our email notifications to stay informed about the latest updates, news, and announcements.
            '''
        )
        email = st.text_input("Enter your email address:", help='*By signing up for notifications on this site, you may receive occasional emails or alerts from us. We strive to make these notifications useful and relevant, but we cannot guarantee their accuracy or timeliness. You can unsubscribe anytime.*')

        submitted = st.form_submit_button(
            "Submit")

        if submitted:
            if email:
                if is_valid_email(email):
                    save_email(email)

                    success = st.success("Thank you for signing up!")
                    time.sleep(3)
                    success.empty()
                else:
                    invalid_email = st.error("Invalid email address!")
                    time.sleep(3)
                    invalid_email.empty()
            else:
                no_email = st.warning("Please enter an email address.")
                time.sleep(3)
                no_email.empty()


def display_player_stats(career_hitting, career_pitching, season_hitting, season_pitching):
    career_hitting_tab, season_hitting_tab, career_pitching_tab, season_pitching_tab = st.tabs(
        ['Career Hitting', 'Season Hitting', 'Career Pitching', 'Season Pitching'])

    with career_hitting_tab:
        if career_hitting:
            display_hitting_stats(career_hitting)
        else:
            st.warning(
                f'Oh wow! {selected_player.name} has not batted in their entire career!')

    with season_hitting_tab:
        if season_hitting:
            display_hitting_stats(season_hitting)
        else:
            st.warning(f'{selected_player.name} has not hit this season!')

    with career_pitching_tab:
        if career_pitching:
            display_pitching_stats(career_pitching)
        else:
            st.warning(
                f'Jeez! {selected_player.name} has not pitched this season!')

    with season_pitching_tab:
        if season_pitching:
            display_pitching_stats(season_pitching)
        else:
            st.warning(
                f'{selected_player.name} has not pitched in their entire career!')


def display_hitting_stats(stats):
    basic_stats = {
        'Average': stats['avg'],
        'Homeruns': stats['homeRuns'],
        'RBI': stats['rbi'],
        'Runs': stats['runs'],
        'Stolen Bases': stats['stolenBases'],
        'Games Played': stats['gamesPlayed'],
    }

    advanced_stats = {
        'OBP': stats['obp'],
        'SLG': stats['slg'],
        'OPS': stats['ops'],
        'Doubles': stats['doubles'],
        'Triples': stats['triples'],
        'Stolen Base (%)': stats['stolenBasePercentage'],
    }

    hide_table_row_index = """
        <style>
        thead tr:first-child {display:none} th
        tbody th {display:none}
        </style>
        """

    st.markdown(hide_table_row_index, unsafe_allow_html=True)
    st.table(basic_stats)

    with st.expander('Advanced Statistics'):
        st.table(advanced_stats)


def display_pitching_stats(stats):
    basic_stats = {
        'ERA': stats['era'],
        'Avg': stats['avg'],
        'Homeruns': stats['homeRuns'],
        'Strikeouts': stats['strikeOuts'],
        'Stolen Base (%)': stats['stolenBasePercentage'],
        'Win (%)': stats['winPercentage'],
        'Games Pitched': stats['gamesPitched'],
    }

    advanced_stats = {
        'Innings Pitched': stats['inningsPitched'],
        'Strike (%)': stats['strikePercentage'],
        'Whip': stats['whip'],
        'OBP': stats['obp'],
        'SLG': stats['slg'],
        'OPS': stats['ops'],
        'Games Started': stats['gamesStarted'],
        'Shutouts': stats['shutouts'],
        'Blown Saves': stats['blownSaves'],
        'Wild Pitches': stats['wildPitches'],
        'Hit By Pitch': stats['hitByPitch'],
        'Base on Balls': stats['baseOnBalls'],
    }

    hide_table_row_index = """
        <style>
        thead tr:first-child {display:none} th
        tbody th {display:none}
        </style>
        """

    # Inject CSS with Markdown
    st.markdown(hide_table_row_index, unsafe_allow_html=True)
    st.table(basic_stats)

    with st.expander('Advanced Statistics'):
        st.table(advanced_stats)


if __name__ == '__main__':
    main()
