import streamlit as st
import numpy as np
import pandas as pd
import streamlit.components.v1 as components
from streamlit_option_menu import option_menu
import statsapi
import requests
from collections import defaultdict
from enum import Enum


def main():
    st.title('MLB Insights')
    st.caption('MLB Insights is the ultimate site for baseball fans who want to stay up-to-date on the latest player statistics and profiles.')
    st.divider()

    players = defaultdict(dict)  # id -> Player()
    name_to_id = defaultdict(str)  # name -> id
    name_to_id[''] = None

    player = None

    all_players = statsapi.lookup_player("")
    if not all_players:
        st.error('No players were found!')

    for player in all_players:
        id = player['id']
        name = player['fullName']

        players[id] = Player(player)
        name_to_id[name] = id

    page = Page.PLAYER_SEARCH.value  # default page
    with st.sidebar:
        page = option_menu("MLB Insights", [Page.PLAYER_SEARCH.value, Page.LEAGUE_LEADERS.value],
                           icons=['search', 'list-task'], menu_icon="body-text", default_index=0)

    if page == Page.PLAYER_SEARCH.value:
        player_name = st.selectbox(
            label='Search for a player',
            options=name_to_id.keys(),
            help="Enter a player's name then press ENTER...")

        if player_name != None:
            id = name_to_id[player_name]
            player = players[id]

        if player:
            st.success(f'You Selected: {player}')
            display_player_info(player)

    elif page == Page.LEAGUE_LEADERS.value:
        pass
    else:
        page = Page.PLAYER_SEARCH.value


def display_player_info(player):
    st.divider()

    res = requests.get(
        f"http://lookup-service-prod.mlb.com/json/named.player_info.bam?sport_code='mlb'&player_id='{player.id}'")

    if res.status_code == 200:
        res = res.json()

        info = res['player_info']['queryResults']['row']

        city, state, country = info['birth_city'], info['birth_state'], info['birth_country']
        birth_location = ''
        if city:
            birth_location = f'{city}, {country}'
        elif state:
            birth_location = f'{state}, {country}'

        height = f"{info['height_feet']}' {info['height_inches']}\""

        st.markdown(
            f'''
            # {player.name} ({player.position}) - :red[#{player.number}]
            > **Age:** {info['age']} | **Height:** {height} | **Weight:** {info['weight']}lbs | **Bats/Throws:** {info['bats']}/{info['throws']} | **Status:** {info['status']}
            >
            > **Team:** {info['team_name']}
            ''')

        tab1, tab2, tab3 = st.tabs(["Cat", "Dog", "Owl"])

        with tab1:
            st.header("A cat")
            st.image("https://static.streamlit.io/examples/cat.jpg", width=200)

        with tab2:
            st.header("A dog")
            st.image("https://static.streamlit.io/examples/dog.jpg", width=200)

        with tab3:
            st.header("An owl")
            st.image("https://static.streamlit.io/examples/owl.jpg", width=200)

    else:
        st.error(f'Unable to fetch full player info for {player.name}!')


class Page(Enum):
    PLAYER_SEARCH = 'Player Search'
    LEAGUE_LEADERS = 'League Leaders'


class Player:
    def __init__(self, info):
        self.name = info.get('fullName')
        self.id = info.get('id')
        self.number = info.get('primaryNumber')
        self.position = info.get('primaryPosition').get('abbreviation')

    def __repr__(self) -> str:
        return f'{self.name} ({self.id})'


if __name__ == '__main__':
    main()
