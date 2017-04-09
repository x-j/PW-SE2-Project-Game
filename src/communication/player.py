#!/usr/bin/env python
import xml.etree.ElementTree as ET
from argparse import ArgumentParser

from src.communication import messages
from src.communication.client import Client
from src.communication.info import GameInfo, PlayerType, GoalFieldInfo, Allegiance, TaskFieldInfo, \
    PieceInfo, ClientTypeTag, PlayerInfo
from src.communication.unexpected import UnexpectedServerMessage

REGISTERED_GAMES_TAG = "{https://se2.mini.pw.edu.pl/17-results/}"


def parse_games(games):
    open_games = []
    root = ET.fromstring(games)

    for registered_games in root.findall(REGISTERED_GAMES_TAG + "GameInfo"):
        game_name = registered_games.get("gameName")
        blue_team_players = int(registered_games.get("blueTeamPlayers"))
        red_team_players = int(registered_games.get("redTeamPlayers"))
        open_games.append((game_name, blue_team_players, red_team_players))

    return open_games


class Player(Client):
    def __init__(self, index=1, verbose=False, game_name='easy clone'):
        """

        :param index: Player index for the server
        :param verbose: Verbose functionality boolean
        :param game_name: Game name for player to join
        """
        super().__init__(index, verbose)

        self.strategy = BaseStrategy(self.game_info, self.location, self.team)
        self.typeTag = ClientTypeTag.PLAYER
        self.Guid = 'Not Assigned'
        self.game_info = GameInfo()
        self.open_games = []
        self.game_name = game_name
        self.team = 'Not Assigned'
        self.role = 'Not Assigned'
        self.location = tuple()

    def handle_confirmation(self, message):
        """

        :param message:
        :return: Parses the confirmation message and extracts game information
        """
        if "ConfirmJoiningGame" in message:
            root = ET.fromstring(message)
            self.Guid = root.attrib.get('privateGuid')
            self.game_info.id = int(root.attrib.get('gameId'))
            self.game_info.name = self.game_name

            for player_definition in root.findall(REGISTERED_GAMES_TAG + "PlayerDefinition"):
                self.team = player_definition.attrib.get('team')
                self.role = player_definition.attrib.get('type')
            return True

        elif "RejectJoiningGame" in message:
            self.verbose_debug("Got rejected by the server, so shutting down.")
            self.shutdown()
            return False

        else:
            self.verbose_debug("Unexpected message from server!")
            raise UnexpectedServerMessage

    def handle_game(self, game_message):
        """

        :param game_message:
        :return: Parses the game message and extracts game information
        """
        root = ET.fromstring(game_message)

        for board in root.findall(REGISTERED_GAMES_TAG + "Board"):
            self.game_info.task_height = int(board.attrib.get('tasksHeight'))
            self.game_info.board_width = int(board.attrib.get('width'))
            self.game_info.goals_height = int(board.attrib.get('goalsHeight'))

        for player_location in root.findall(REGISTERED_GAMES_TAG + "PlayerLocation"):
            x = int(player_location.attrib.get('x'))
            y = int(player_location.attrib.get('y'))
            self.location = (x, y)

        for player_list in root.findall(REGISTERED_GAMES_TAG + "Players"):
            for in_player in player_list.findall(REGISTERED_GAMES_TAG + "Player"):
                in_team = in_player.attrib.get('team')
                in_type = in_player.attrib.get('type')
                in_id = in_player.attrib.get('id')
                self.game_info.players[in_team][in_id] = PlayerInfo(in_id, in_type, in_type)

        y = 2 * self.game_info.goals_height + self.game_info.task_height - 1
        for i in range(self.game_info.goals_height):
            for x in range(self.game_info.board_width):
                if (x, y) not in self.game_info.goal_fields.keys():
                    self.game_info.goal_fields[x, y] = GoalFieldInfo(x, y, Allegiance.RED)
            y -= 1

        for i in range(self.game_info.task_height):
            for x in range(self.game_info.board_width):
                self.game_info.task_fields[x, y] = TaskFieldInfo(x, y)
            y -= 1

        for i in range(self.game_info.goals_height):
            for x in range(self.game_info.board_width):
                if (x, y) not in self.game_info.goal_fields.keys():
                    self.game_info.goal_fields[x, y] = GoalFieldInfo(x, y, Allegiance.BLUE)
            y -= 1

    def move_message(self, direction):
        """
        :param direction: Move direction
        :return: Move direction message
        """
        return messages.move(self.game_info.id, self.Guid, direction)

    def discover_message(self):
        return messages.discover(self.game_info.id, self.Guid)

    def pickup_message(self):
        return messages_new.pick_up_piece(self.game_info.id, self.Guid)
        return messages.pick_up_piece(self.game_info.id, self.Guid)

    def place_message(self):
        return messages.place_piece(self.game_info.id, self.Guid)

    def test_piece_message(self):
        return messages.test_piece(self.game_info.id, self.Guid)

    def handle_data(self, response_data):
        root = ET.fromstring(response_data)

        self.game_info.open = not root.attrib.get('gameFinished')

        for task_field_list in root.findall(REGISTERED_GAMES_TAG + "TaskFields"):
            if task_field_list is not None:
                for task_field in task_field_list.findall(REGISTERED_GAMES_TAG + "TaskField"):
                    x = int(task_field.attrib.get('x'))
                    y = int(task_field.attrib.get('y'))
                    self.game_info.task_fields[x, y].timestamp = task_field.attrib.get('timestamp')
                    self.game_info.task_fields[x, y].distance_to_piece = int(task_field.attrib.get('distanceToPiece'))
                    if task_field.attrib.get('playerId') is not None:
                        self.game_info.task_fields[x, y].player_id = int(task_field.attrib.get('playerId'))
                    if task_field.attrib.get('pieceId') is not None:
                        self.game_info.task_fields[x, y].piece_id = int(task_field.attrib.get('pieceId'))

        for goal_field_list in root.findall(REGISTERED_GAMES_TAG + "GoalFields"):
            if goal_field_list is not None:
                for goal_field in goal_field_list.findall(REGISTERED_GAMES_TAG + "GoalField"):
                    x = int(goal_field.attrib.get('x'))
                    y = int(goal_field.attrib.get('y'))
                    self.game_info.goal_fields[x, y].timestamp = goal_field.attrib.get('timestamp')
                    if goal_field.attrib.get('playerId') is not None:
                        self.game_info.goal_fields[x, y].player_id = int(goal_field.attrib.get('playerId'))
                    self.game_info.goal_fields[x, y].allegiance = goal_field.attrib.get('team')
                    type = goal_field.attrib.get('type')
                    self.game_info.goal_fields[x, y].type = type

        for piece_list in root.findall(REGISTERED_GAMES_TAG + "Pieces"):
            if piece_list is not None:
                for piece in piece_list.findall(REGISTERED_GAMES_TAG + "Piece"):
                    id = int(piece.attrib.get('id'))
                    timestamp = piece.attrib.get('timestamp')
                    type = piece.attrib.get('type')
                    self.game_info.pieces[id] = PieceInfo(id, timestamp, type)

        for player_location in root.findall(REGISTERED_GAMES_TAG + "PlayerLocation"):
            if player_location is not None:
                x = int(task_field.attrib.get('x'))
                y = int(task_field.attrib.get('y'))
                self.location = (x, y)

    def play(self):
        self.send(messages.get_games())
        print(messages.get_games())
        games = self.receive()

        if 'RegisteredGames' in games:
            self.open_games = parse_games(games)

            if len(self.open_games) > 0:
                # TODO : remove temp fields after new messages in action
                temp_game_name = self.open_games[0][0]
                temp_preferred_role = PlayerType.LEADER.value
                temp_preferred_team = Allegiance.RED.value
                self.send(messages.join_game(temp_game_name, temp_preferred_team, temp_preferred_role, self.id))
                confirmation = self.receive()
                if confirmation is not None:
                    self.handle_confirmation(confirmation)
                game_info = self.receive()
                if game_info is not None:
                    self.handle_game(game_info)

                while 1:
                    self.strategy.get_next_move()



                """ ----------message handling for future --------
                self.send(self.move_message(Direction.UP))
                move_response = self.receive()
                if move_response is not None:
                    self.handle_data(move_response)

                self.send(self.discover_message())
                discover_response = self.receive()
                if discover_response is not None:
                    self.handle_data(discover_response)

                self.send(self.pickup_message())
                pickup_response = self.receive()
                if pickup_response is not None:
                    self.handle_data(pickup_response)

                self.send(self.place_message())
                place_response = self.receive()
                if place_response is not None:
                    self.handle_data(place_response)

                self.send(self.test_piece_message())
                test_piece_response = self.receive()
                if test_piece_response is not None:
                    self.handle_data(test_piece_response)

                """
                # TODO: add knowledge exchange sending and receiving when needed


if __name__ == '__main__':
    def simulate(player_count, verbose):
        game_name = 'easy clone'
        for i in range(player_count):
            p = Player(index=i, verbose=verbose, game_name=game_name)
            if p.connect():
                p.play()
                p.shutdown()


    parser = ArgumentParser()
    parser.add_argument('-c', '--playercount', default=1, help='Number of players to be deployed.')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='Use verbose debugging mode.')
    args = vars(parser.parse_args())
    simulate(int(args["playercount"]), args["verbose"])
