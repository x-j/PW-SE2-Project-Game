#!/usr/bin/env python
import socket
from argparse import ArgumentParser
from datetime import datetime
from threading import Thread
from time import sleep

from src.communication.messages import Message


class Player:
    TIME_BETWEEN_MESSAGES = 5  # time in s between each message sent by player
    INTER_CONNECTION_TIME = 10  # time in s between attemps to connect to server
    CONNECTION_ATTEMPTS = 3  # how many times the clients will retry the attempt to connect
    DEFAULT_HOSTNAME = socket.gethostname() # keep this as socket.gethostname() if you're debugging on your own pc
    DEFAULT_PORT = 8000
    MESSAGE_BUFFER_SIZE = 1024

    def __init__(self, index, verbose):
        """
        constructor.
        :param index: local index used to differentiate between different players running in threads
        :param verbose: boolean value. if yes, there will be a lot of output printed out.
        """
        self.socket = socket.socket()
        self.index = index
        self.id = None  # will be assigned after connecting to server.
        self.verbose = verbose
        self.verbose_debug("Player created.")

    def connect(self, hostname=DEFAULT_HOSTNAME, port=DEFAULT_PORT):
        """
        try to connect to server and receive UID
        :param hostname: host name to connect to
        :param port: port to connect to
        """

        failed_connections = 0

        while True:
            try:
                self.verbose_debug("Trying to connect to server " + str(hostname + " at port " + str(port) + "."))
                self.socket.connect((hostname, port))
                self.verbose_debug("Connected to server.")

                received = self.socket.recv(Player.MESSAGE_BUFFER_SIZE)
                self.id = received.decode()
                self.verbose_debug("Received UID from server=" + str(self.id))
                return True

            except socket.error:
                if failed_connections < Player.CONNECTION_ATTEMPTS:
                    failed_connections += 1
                    self.verbose_debug("Attempt number " + str(failed_connections) + " failed. Trying again in " + str(
                        Player.INTER_CONNECTION_TIME) + " seconds.")
                    sleep(Player.INTER_CONNECTION_TIME)
                    continue
                else:
                    self.verbose_debug("Attempt number " + str(
                        failed_connections) + " failed. No more attempts to connect will be made.")
                    return False

    def play(self, messages_count=1):
        """
        send and receive messages to/from server
        :param messages_count: how many messages should be sent from player to server
        """

        gamenames = ['game1', 'game2', 'game3']
        blueteamplayers = [3, 4, 7]
        redteamplayers = [2, 1, 1]
        playerteam = ['red', 'red', 'blue', 'blue', 'red', 'blue']
        playertype = ['master', 'player', 'leader', 'player', 'leader', 'master']
        playersid = [3, 4, 5, 1, 2, 5]
        taskfieldsX = [1, 1, 2, 2, 3, 3]
        taskfieldsY = [4, 5, 6, 4, 4, 6]
        taskfieldsdistances = [1, 1, 2, 1, 0, 1]

        for i in range(messages_count):
            try:
                # Send a message:
                # message = "Hello world."
                # message = Message.registergame(self, 'test', 2, 3)
                # message = Message.confirmgameregistration(self, 5)
                # message = Message.registeredgames(self, gamenames, blueteamplayers, redteamplayers)
                # message = Message.joingame(self, 'test', 'master', 'red')
                # message = Message.confirmjoininggame(self, 2, 3, 'aaaxxx-bbb-ccc-ddd-eeefff', 3, 'red', 'master')
                # message = Message.gamemessage(self, 3, playerteam, playertype, playersid, 7, 7, 7, 0, 0)
                # message = Message.discover(self, 3, 'c094cab7-da7b-457f-89e5-a5c51756035f')
                # message = Message.dataresponsefordiscover(self, 3, 'false', taskfieldsX, taskfieldsY, taskfieldsdistances, 3, 'unknown')
                # message = Message.move(self, 4, 'c094cab7-da7b-457f-89e5-a5c51756035f', 'up')
                # message = Message.moveresponsegood(self, 3, 'false', taskfieldsX, taskfieldsY, taskfieldsdistances, 3, 2)
                # message = Message.moveresponseplayer(self, 3, 'false', taskfieldsX, taskfieldsY, taskfieldsdistances, 3, 2, 1, 'unknown')
                # message = Message.moveresponseedge(self, 3, 'false', 5, 3)
                # message = Message.pickup(self, 4, 'c094cab7-da7b-457f-89e5-a5c51756035f')
                # message = Message.pickupresponse(self, 4, 'false', 3, 'unknown')
                # message = Message.testpiece(self, 4, 'c094cab7-da7b-457f-89e5-a5c5175666')
                # message = Message.placeresponse(self, 4, 'false', 3, 'sham')
                # message = Message.authorizeknowledgeexchange(self, 4, 3, 'c094cab7-da7b-457f-89e5-a5c5175666')
                message = Message.knowledgeexchangerequest(self, 4, 3)



                # message = messages.randomMessage()
                # message = messages.getgames()

                self.socket.send(message.encode())
                self.verbose_debug("Sent to server: " + message)

                # Receive a response:
                received_data = self.socket.recv(Player.MESSAGE_BUFFER_SIZE)
                self.verbose_debug("Received from server: \"" + received_data.decode() + "\"")
                sleep(Player.TIME_BETWEEN_MESSAGES)

            except socket.error as e:
                self.verbose_debug("Socket error caught: " + str(e) + ". Shutting down the connection.", True)
                self.socket.close()
                return

    def verbose_debug(self, message, important=False):
        """
        if in verbose mode, print out the given message with player index and timestamp
        :param message: message to be printed
        """
        if self.verbose or important:
            header = "P" + str(self.index) + " at " + str(datetime.now().time()) + " - "
            print(header, message)


def run(number_of_players=1, verbose=True, messages_count=1):
    """
    deploy client threads/
    :param number_of_players:
    :param verbose: if the clients should operate in verbose mode.
    :param messages_count: how many messages should be sent from player to server
    """
    for i in range(number_of_players):
        Thread(target=deploy_player, args=(i + 1, verbose, messages_count)).start()
        sleep(1)


def deploy_player(index, verbose=True, messages_count=1):
    p = Player(index, verbose)
    if p.connect():
        p.play(messages_count)


parser = ArgumentParser()
parser.add_argument('-c', '--playercount', default=1, help='Number of players to be deployed.')
parser.add_argument('-v', '--verbose', action='store_true', default=False, help='Use verbose debugging mode.')
parser.add_argument('-m', '--messagecount', default=1, help='Number of messages each player should send.')
args = vars(parser.parse_args())

run(int(args["playercount"]), args["verbose"], int(args["messagecount"]))
