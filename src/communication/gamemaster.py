import os
import uuid
import xml.etree.ElementTree as ET
from argparse import ArgumentParser
from datetime import datetime
from enum import Enum
from random import random, randint
from threading import Thread
from time import sleep

from src.communication import messages_old
from src.communication.client import Client
from src.communication.info import GameInfo, GoalFieldInfo, Allegiance, TaskFieldInfo, PieceInfo, PieceType, \
    GoalFieldType, \
    ClientTypeTag
from src.communication.unexpected import UnexpectedServerMessage

GAME_SETTINGS_TAG = "{https://se2.mini.pw.edu.pl/17-pl-19/17-pl-19/}"
XML_MESSAGE_TAG = "{https://se2.mini.pw.edu.pl/17-results/}"
ET.register_namespace('', "https://se2.mini.pw.edu.pl/17-results/")


class PlayerType(Enum):
    LEADER = "leader"
    MEMBER = "member"


def parse_game_master_settings():
    full_file = os.getcwd() + "\GameMasterSettings.xml"
    tree = ET.parse(full_file)
    root = tree.getroot()

    return root


class GameMaster(Client):
    def parse_game_definition(self):
        root = parse_game_master_settings()

        self.keep_alive_interval = int(root.attrib.get('KeepAliveInterval'))
        self.retry_register_game_interval = int(root.attrib.get('RetryRegisterGameInterval'))

        goals = {}

        board_width = 0
        task_area_length = 0
        goal_area_length = 0

        for game_attributes in root.findall(GAME_SETTINGS_TAG + "GameDefinition"):
            # load goal field information:
            for goal in game_attributes.findall(GAME_SETTINGS_TAG + "Goals"):
                colour = goal.get("team")
                x = int(goal.get("x"))
                y = int(goal.get("y"))
                if colour == "red":
                    goals[x, y] = GoalFieldInfo(x, y, Allegiance.RED, type=GoalFieldType.GOAL)
                if colour == "blue":
                    goals[x, y] = GoalFieldInfo(x, y, Allegiance.BLUE, type=GoalFieldType.GOAL)

            self.sham_probability = float(game_attributes.find(GAME_SETTINGS_TAG + "ShamProbability").text)
            self.placing_pieces_frequency = int(
                game_attributes.find(GAME_SETTINGS_TAG + "PlacingNewPiecesFrequency").text)
            self.initial_number_of_pieces = int(game_attributes.find(GAME_SETTINGS_TAG + "InitialNumberOfPieces").text)
            board_width = int(game_attributes.find(GAME_SETTINGS_TAG + "BoardWidth").text)
            task_area_length = int(game_attributes.find(GAME_SETTINGS_TAG + "TaskAreaLength").text)
            goal_area_length = int(game_attributes.find(GAME_SETTINGS_TAG + "GoalAreaLength").text)

            self.game_name = game_attributes.find(GAME_SETTINGS_TAG + "GameName").text
            self.num_of_players_per_team = int(game_attributes.find(GAME_SETTINGS_TAG + "NumberOfPlayersPerTeam").text)

        self.info = GameInfo(goal_fields=goals, board_width=board_width, task_height=task_area_length,
                             goals_height=goal_area_length)

    def parse_action_costs(self):
        root = parse_game_master_settings()

        for action_costs in root.findall(GAME_SETTINGS_TAG + "ActionCosts"):
            self.move_delay = int(action_costs.find(GAME_SETTINGS_TAG + "MoveDelay").text)
            self.discover_delay = int(action_costs.find(GAME_SETTINGS_TAG + "DiscoverDelay").text)
            self.test_delay = int(action_costs.find(GAME_SETTINGS_TAG + "TestDelay").text)
            self.pickup_delay = int(action_costs.find(GAME_SETTINGS_TAG + "PickUpDelay").text)
            self.placing_delay = int(action_costs.find(GAME_SETTINGS_TAG + "PlacingDelay").text)
            self.knowledge_exchange_delay = int(action_costs.find(GAME_SETTINGS_TAG + "KnowledgeExchangeDelay").text)

    def __init__(self, index=1, verbose=False):
        super().__init__(index, verbose)

        self.RANDOMIZATION_ATTEMPTS = 10
        self.piece_counter = 0
        self.typeTag = ClientTypeTag.GAME_MASTER
        self.game_on = False
        self.player_indexer = 0

        self.blue_players = {}
        self.blue_players_locations = {}
        self.red_players = {}
        self.red_players_locations = {}

        self.parse_game_definition()
        self.parse_action_costs()

    def run(self):
        register_game_message = messages_old.register_game(self.game_name, self.num_of_players_per_team,
                                                           self.num_of_players_per_team)
        self.send(register_game_message)

        message = self.receive()

        try:
            if "RejectGameRegistration" in message:
                sleep(self.retry_register_game_interval)
                self.send(register_game_message)

            elif "ConfirmGameRegistration" in message:
                # read game id from message
                confirmation_root = ET.fromstring(message)
                self.info.id = int(confirmation_root.attrib.get("gameId"))

                while True:
                    # now, we will be receiving messages about players who are trying to join:
                    message = self.receive()  # this will block

                    if "JoinGame" in message:
                        # a player is trying to join! let's parse his message
                        joingame_root = ET.fromstring(message)

                        in_game_id = int(confirmation_root.attrib.get("gameId"))
                        in_game_name = joingame_root.attrib.get("gameName")

                        in_pref_team = joingame_root.attrib.get("preferedTeam")
                        in_pref_role = joingame_root.attrib.get("preferedRole")

                        # in theory, received gamename has to be the same as our game, it should be impossible otherwise
                        self.verbose_debug("in_game_name is: " + in_game_name + " self.gamename: " + self.game_name)
                        if in_game_name != self.game_name:
                            raise UnexpectedServerMessage

                        # let's see if we can fit the player at all:
                        if len(self.blue_players) == self.num_of_players_per_team and len(
                                self.red_players) == self.num_of_players_per_team:
                            # he can't fit in, send a rejection message :(
                            self.send(messages_old.reject_joining_game(self.game_name, self.player_indexer))
                            continue

                        player_id = joingame_root.attrib["playerId"]

                        # generating the private GUID
                        private_guid = uuid.uuid4()

                        # add him to a team while taking into account his preferences:
                        if in_pref_team == "blue":
                            if len(self.blue_players) == self.num_of_players_per_team:
                                self.add_player(Allegiance.RED, in_pref_role)
                            else:
                                self.add_player(Allegiance.BLUE, in_pref_role)

                        if in_pref_team == "red":
                            if len(self.red_players) == self.num_of_players_per_team:
                                self.add_player(Allegiance.BLUE, in_pref_role)
                            else:
                                self.add_player(Allegiance.RED, in_pref_role)

                        if self.player_indexer - 1 in self.red_players.keys():
                            self.send(messages_old.confirm_joining_game(in_game_id, private_guid, player_id, 'red',
                                                                        self.red_players[self.player_indexer - 1]))
                        else:
                            self.send(messages_old.confirm_joining_game(in_game_id, private_guid, player_id, 'blue',
                                                                        self.blue_players[self.player_indexer - 1]))

                        if len(self.blue_players) == self.num_of_players_per_team and len(
                                self.red_players) == self.num_of_players_per_team:
                            #  We are ready to start the game
                            self.set_up_game()
                            self.send(messages_old.game_started(self.info.id))

            else:
                raise UnexpectedServerMessage

        except UnexpectedServerMessage:
            self.verbose_debug("Shutting down due to unexpected message: " + message)
            self.shutdown()

    def set_up_game(self):
        # now that the players have connected, we can prepare the game
        self.whole_board_length = 2 * self.info.goals_height + self.info.task_height - 1
        # initialize goal and task fields:
        y = self.whole_board_length

        for i in range(self.info.goals_height):
            for x in range(self.info.board_width):
                if (x, y) not in self.info.goal_fields.keys():
                    self.info.goal_fields[x, y] = GoalFieldInfo(x, y, Allegiance.RED)

            y -= 1

        for i in range(self.info.task_height):
            for x in range(self.info.board_width):
                self.info.task_fields[x, y] = TaskFieldInfo(x, y)
            y -= 1

        for i in range(self.info.goals_height):
            for x in range(self.info.board_width):
                if (x, y) not in self.info.goal_fields.keys():
                    self.info.goal_fields[x, y] = GoalFieldInfo(x, y, Allegiance.BLUE)

            y -= 1

        # place the players:
        for i in self.red_players.keys():
            x = randint(0, self.info.board_width - 1)
            y = randint(self.whole_board_length - self.info.goals_height + 1, self.whole_board_length)
            random_red_goal_field = self.info.goal_fields[x, y]
            while not random_red_goal_field.is_occupied() and random_red_goal_field.type is GoalFieldType.NON_GOAL:
                x = randint(0, self.info.board_width - 1)
                y = randint(0, self.info.goals_height)
                random_red_goal_field = self.info.goal_fields[x, y]

            self.info.goal_fields[x, y].player_id = int(i)
            self.red_players_locations[i] = (x, y)

        for i in self.blue_players.keys():
            x = randint(0, self.info.board_width - 1)
            y = randint(0, self.info.goals_height - 1)
            random_blue_goal_field = self.info.goal_fields[x, y]
            while not random_blue_goal_field.is_occupied() and random_blue_goal_field.type is GoalFieldType.NON_GOAL:
                x = randint(self.info.board_width - 1)
                y = randint(self.whole_board_length - self.info.goals_height, self.whole_board_length)
                random_blue_goal_field = self.info.goal_fields[x, y]

            self.info.goal_fields[x, y].player_id = int(i)
            self.blue_players_locations[i] = (x, y)

        # create the first pieces:
        for i in range(self.initial_number_of_pieces):
            self.add_piece()

        Thread(target=self.place_pieces(), daemon=True).start()

        self.game_on = True

        self.play()

    def add_piece(self):
        id = self.piece_counter

        # check if we can add the piece at all:
        if not self.info.check_for_empty_fields():
            return False

        x = randint(0, self.info.board_width - 1)
        y = randint(0, self.info.task_height - 1)

        i = 0
        while self.info.has_piece(x, y) and i < self.RANDOMIZATION_ATTEMPTS:
            x = randint(0, self.info.board_width - 1)
            y = randint(0, self.info.task_height - 1)

        if self.info.has_piece(x, y):
            for task_field in self.info.task_fields:
                if not task_field.has_piece():
                    x = task_field.x
                    y = task_field.y

        field = TaskFieldInfo(x, y, datetime.now(), 0, -1, id)
        new_piece = PieceInfo(id, datetime.now())

        if random() >= self.sham_probability:
            new_piece.piece_type = PieceType.LEGIT
        else:
            new_piece.piece_type = PieceType.SHAM

        self.info.task_fields[x, y] = field
        self.info.pieces[id] = new_piece
        self.piece_counter += 1

    def place_pieces(self):
        while self.game_on:
            sleep(float(self.placing_pieces_frequency) / 1000)
            self.add_piece()

    def add_player(self, team, preferred_role):
        if team == Allegiance.BLUE:
            for role in self.blue_players.values():
                if role == 'leader':
                    self.blue_players[self.player_indexer] = 'member'
                    self.player_indexer += 1
                    return 'leader'
            self.blue_players[self.player_indexer] = 'leader'
            self.player_indexer += 1
            return 'leader'
        else:
            for role in self.red_players.values():
                if role == 'leader':
                    self.red_players[self.player_indexer] = 'member'
                    self.player_indexer += 1
                    return 'leader'
            self.red_players[self.player_indexer] = 'leader'
            self.player_indexer += 1
            return 'leader'

    def play(self):
        # TODO: broadcast game message to each player

        while self.game_on:
            message = self.receive()
            self.send("Thanks for the message.")


if __name__ == '__main__':
    def simulate(gamemaster_count, verbose):
        for i in range(gamemaster_count):
            gm = GameMaster(i, verbose)
            if gm.connect():
                gm.run()
                gm.shutdown()


    parser = ArgumentParser()
    parser.add_argument('-c', '--gamemastercount', default=1, help='Number of gamemasters to be deployed.')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='Use verbose debugging mode.')
    args = vars(parser.parse_args())
    simulate(int(args["gamemastercount"]), args["verbose"])
