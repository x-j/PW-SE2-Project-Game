from datetime import datetime
from enum import Enum


class Location():
    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y

    def __str__(self):
        return "({0}, {1})".format(str(self.x), str(self.y))


class ClientTypeTag(Enum):
    CLIENT = "C"
    PLAYER = "P"
    LEADER = "L"
    GAME_MASTER = "GM"
    BLUE_PLAYER = "BP"
    BLUE_LEADER = "BL"
    RED_PLAYER = "RP"
    RED_LEADER = "RL"


class Direction(Enum):
    UP = 'up'
    DOWN = 'down'
    LEFT = 'left'
    RIGHT = 'right'


class Allegiance(Enum):
    RED = 'red'
    BLUE = 'blue'
    NEUTRAL = 'neutral'


class PlayerType(Enum):
    MEMBER = "member"
    LEADER = "leader"


class PieceType(Enum):
    SHAM = 'sham'
    NORMAL = 'normal'
    UNKNOWN = 'unknown'


class GoalFieldType(Enum):
    GOAL = 'goal'
    NON_GOAL = 'non-goal'
    UNKNOWN = 'unknown'


class FieldInfo:
    def __init__(self, x=0, y=0, timestamp=datetime.now(), player_id=None):
        self.x = x
        self.y = y
        self.timestamp = timestamp
        self.player_id = -1
        if player_id is not None:
            self.player_id = player_id

    @property
    def is_occupied(self):
        return self.player_id != -1


class TaskFieldInfo(FieldInfo):
    # Maybe default values are not necessary here but I'm just testing the class
    def __init__(self, x=0, y=0, timestamp=datetime.now(), distance_to_piece=-1, player_id=None, piece_id=None):
        super(TaskFieldInfo, self).__init__(x, y, timestamp, player_id)
        self.distance_to_piece = distance_to_piece
        self.piece_id = piece_id

    def has_piece(self):
        return self.piece_id != -1


class GoalFieldInfo(FieldInfo):
    def __init__(self, x=0, y=0, allegiance=Allegiance.NEUTRAL, player_id=None, timestamp=datetime.now(),
                 type=GoalFieldType.UNKNOWN):
        super(GoalFieldInfo, self).__init__(x, y, timestamp, player_id)
        self.allegiance = allegiance
        self.type = type


class PieceInfo:
    def __init__(self, id=-1, timestamp=datetime.now(), piece_type=PieceType.NORMAL, player_id=None):
        self.id = id
        self.timestamp = timestamp
        self.piece_type = piece_type
        self.player_id = player_id


class ClientInfo:
    """might not actually be used that much, encapsulate some information about client id, their type etc."""

    def __init__(self, id="-1", tag=ClientTypeTag.CLIENT, socket=None, game_name="", game_master_id="-1"):
        self.id = id
        self.tag = tag
        self.socket = socket
        self.game_name = game_name
        self.game_master_id = game_master_id

    def get_tag(self):
        return self.tag.value + str(self.id)


class GameInfo:
    def __init__(self, id=-1, name="", task_fields=None, goal_fields=None, pieces=None, board_width=0, task_height=0,
                 goals_height=0, max_blue_players=0, max_red_players=0, open=True, finished=False, game_master_id="",
                 latest_timestamp=""):
        self.id = id
        self.name = name
        self.open = open
        self.finished = finished
        self.game_master_id = game_master_id
        if pieces is None:
            pieces = {}
        if goal_fields is None:
            goal_fields = {}
        if task_fields is None:
            task_fields = {}
        self.pieces = pieces  # pieceId => PieceInfo
        self.goal_fields = goal_fields  # (x,y) => GoalFieldInfo
        self.task_fields = task_fields  # (x,y) => TaskFieldInfo
        self.board_width = board_width
        self.task_height = task_height
        self.goals_height = goals_height
        self.latest_timestamp = latest_timestamp

        self.teams = {Allegiance.RED.value: {}, Allegiance.BLUE.value: {}}
        # self.teams is a dict of dicts: team => {player_id => PlayerInfo}

        self.max_blue_players = max_blue_players
        self.max_red_players = max_red_players

    def check_for_empty_task_fields(self):
        for task_field in self.task_fields.values():
            if task_field.piece_id == -1:
                return True

        return False

    def has_piece(self, x, y):
        if (x, y) in self.task_fields.keys():
            return self.task_fields[x, y].has_piece()
        else:
            return False

    def is_task_field(self, location: Location):
        return (location.x, location.y) in self.task_fields.keys()

    def is_goal_field(self, location: Location):
        return (location.x, location.y) in self.goal_fields.keys()

    def is_out_of_bounds(self, location: Location):
        return not (self.is_task_field(location) or self.is_goal_field(location))

    def get_neighbours(self, location: Location, look_for_extended=False):
        """
        :param look_for_extended: if True, function will look for all 8 neighbours instead of 9.
        :return:
        """
        dist = 1
        if look_for_extended:
            dist = 2

        neighbours = {}
        for (x, y), field in self.task_fields.items():
            if not (abs(location.x - x) > 1) and not abs(location.y - y) > 1:
                if abs(location.x - x) + abs(location.y - y) <= dist:
                    neighbours[x, y] = field
        for (x, y), field in self.goal_fields.items():
            if not (abs(location.x - x) > 1) and not abs(location.y - y) > 1:
                if abs(location.x - x) + abs(location.y - y) <= dist:
                    neighbours[x, y] = field
        return neighbours

    def manhattan_distance(self, field_a: FieldInfo, field_b: FieldInfo):
        return abs(field_a.x - field_b.x) + abs(field_a.y - field_b.y)


class PlayerInfo(ClientInfo):
    """used by GameMaster only (for now, at least...)"""

    def __init__(self, id="-1", tag=PlayerType.MEMBER.value, team=None, info: GameInfo = None,
                 location: Location = None, guid=None):
        super(PlayerInfo, self).__init__(id=id, tag=ClientTypeTag.PLAYER)
        self.type = tag
        self.info = info
        self.team = team
        self.location = location
        self.guid = guid
