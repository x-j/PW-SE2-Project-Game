#!/usr/bin/python
import socket
import sys
from argparse import ArgumentParser
from datetime import datetime
from enum import Enum
from threading import Thread
from time import sleep


class Communication(Enum):
    """
    an Enum class for flags which will be useful later on for distinguishing between message recipients
    """
    SERVER_TO_CLIENT = 0
    CLIENT_TO_SERVER = 1
    OTHER = 2


class CommunicationServer:
    # some constants:
    INTER_PRINT_STATE_TIME = 5
    DEFAULT_BUFFER_SIZE = 1024
    DEFAULT_PORT = 420
    DEFAULT_TIMEOUT = 10
    DEFAULT_CLIENT_LIMIT = 10
    DEFAULT_HOSTNAME = socket.gethostname()

    def __init__(self, verbose, host=DEFAULT_HOSTNAME, port=DEFAULT_PORT, client_limit=DEFAULT_CLIENT_LIMIT):
        """
        constructor.
        :param verbose:
        :param host:
        :param port:
        """
        self.host = host
        self.port = port
        self.clientLimit = client_limit
        self.socket = socket.socket()
        self.playerDict = {}
        self.clientCount = 0
        self.verbose = verbose

        try:
            self.socket.bind((host, port))
        # self.socket.settimeout(CommunicationServer.DEFAULT_TIMEOUT)
        except OSError as e:
            self.verbose_debug("Error while setting up the socket: " + str(e), True)
            sys.exit(0)

        self.verbose_debug("Created server with hostname: " + host + " on port " + str(port), True)
        self.running = True

    def verbose_debug(self, message, important=False):
        """
        if in verbose mode, print out the given message with a timestamp
        :param message: message to be printed
        :param important: if not in verbose mode, setting this flag to True will make sure this message gets printed
        """
        if self.verbose or important:
            header = "S at " + str(datetime.now().time()) + " - "
            print(header, message)

    def print_state(self):
        """
        method running on a separate Thread, prints the current state of the server every couple of seconds
        time between each printing of debug messages is specified by the constant CommunicationServer.INTER_PRINT_STATE_TIME
        """
        while self.running:
            self.verbose_debug("Currently there are " + str(self.clientCount) + " clients connected.")
            sleep(CommunicationServer.INTER_PRINT_STATE_TIME)

    def listen(self):
        """
        accept client connections and deploy threads.
        """
        self.socket.listen()
        self.verbose_debug("Started listening")
        Thread(target=self.print_state, daemon=True).start()
        Thread(target=self.accept_clients, daemon=True).start()

        # wait for and respond to user commands:
        try:
            while self.running:
                command = input()

                if command == "stop" or command == "close" or command == "quit" or command == "exit":
                    raise KeyboardInterrupt

                elif command == "state":
                    self.verbose_debug("Currently there are " + str(self.clientCount) + " clients connected.", True)

                elif command == "clients":
                    self.verbose_debug("Currently connected clients:", True)
                    if len(self.playerDict) > 0:
                        for player_index in self.playerDict:
                            print(" P" + str(player_index) + ": " + str(self.playerDict[player_index].getsockname()))
                    else:
                        print(" There are no currently connected clients.")

                elif command == "toggle-verbose":
                    self.verbose = not self.verbose

                elif str(command).startswith("echo "):
                    command = str(command)
                    message_text = command.split(" ")
                    speech = ""
                    for word in message_text:
                        if word != "echo":
                            speech += word + " "
                    print(speech)

        except EOFError:
            # handle C-C, C-Z and "stop" commands
            self.verbose_debug("Server closed by user.", True)
            self.shutdown()

        except KeyboardInterrupt:
            # handle C-C, C-Z and "stop" commands
            self.verbose_debug("Server closed by user.", True)
            self.shutdown()

    def accept_clients(self):
        """
        method running endlessly on a separate thread, accepts new clients and deploys threads to handle them
        """
        player_index = 1
        while self.running:
            # block and wait until a client connects:
            if self.clientCount < self.clientLimit:
                # if client limit not exceeded, handle the new client
                client_socket, address = self.socket.accept()
                self.register_connection(client_socket, player_index)
            else:
                sleep(1)

    def register_connection(self, client_socket, player_index):
        # send a single byte which says "greetings"
        client_socket.send('\0'.encode())
        # receive hello from client
        # received = self.receive(client_socket)
        # if received == "0":
        #     # client is GameMaster
        #     pass
        # else:
        #     # client is just a Player
        #     pass

        self.playerDict[player_index] = client_socket
        self.clientCount += 1
        player_index += 1

        self.verbose_debug(
            "New client: " + str(client_socket.getsockname()) + " with index " + str(player_index) + " connected.",
            True)
        if self.clientCount == self.clientLimit:
            self.verbose_debug("Client capacity reached.")

        thread = Thread(target=self.handle_player, args=(client_socket, player_index))
        thread.daemon = True
        thread.start()

    def handle_player(self, client, player_index):
        """
        Receive and send messages to/from a given client.
        :param client: a client socket
        :param player_index: local index, used in playerDict
        :return:
        """
        try:
            # LEGACY:
            # first, tell the player what his local index is:
            # self.send(client, player_index, Communication.SERVER_TO_CLIENT, player_index)
            # self.verbose_debug("Sent id to player " + str(player_index) + ".")

            while self.running:
                received_data = self.receive(client, Communication.CLIENT_TO_SERVER, player_index)

                response = ("Your message was: " + str(received_data))

                self.send(client, response, Communication.SERVER_TO_CLIENT, player_index)

        except ConnectionAbortedError:
            self.verbose_debug("Player " + str(player_index) + " disconnected. Closing connection.", True)
            client.close()
            self.clientCount -= 1
            return False

        except socket.error as e:
            self.verbose_debug(
                "Closing connection with Player " + str(player_index) + " due to a socket error: " + str(e) + ".", True)
            client.close()
            self.clientCount -= 1
            return False

        except Exception as e:
            self.verbose_debug("Unexpected exception: " + str(e) + ".", True)
            client.close()
            self.clientCount -= 1
            raise e

    def shutdown(self):
        # I added this since I heard it's a hack to make the server shutdown but I guess it works without it
        # See http://stackoverflow.com/questions/16734534/close-listening-socket-in-python-thread
        self.running = False
        self.socket.close()
        self.verbose_debug("Shutting down the server.", True)

    def send(self, recipient, message, com_type_flag=Communication.OTHER, player_index=0):
        """
        a truly vital method. Sends a given message to a recipient.
        :param recipient: socket object of the recipient.
        :param message: message to be passed, any type. will be encoded as string.
        :param com_type_flag: a Communication flag. I am adding this here because it might be useful later.
        """
        message = str(message)
        recipient.send(message.encode())

        if com_type_flag == Communication.SERVER_TO_CLIENT:
            self.verbose_debug("Message sent to P" + str(player_index) + ": \"" + message + "\".")
        else:
            pass

    def receive(self, client, com_type_flag=Communication.OTHER, player_index=0):
        """
        :param client:
        :param com_type_flag: a Communication flag. I am adding this here because it might be useful later.
        """
        received_data = client.recv(CommunicationServer.DEFAULT_BUFFER_SIZE).decode()

        if com_type_flag == Communication.CLIENT_TO_SERVER:
            self.verbose_debug("Message received from P" + str(player_index) + ": \"" + received_data + "\".")
        else:
            pass

        return received_data


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='Use verbose debugging mode.')
    args = vars(parser.parse_args())
    server = CommunicationServer(args["verbose"])
    server.listen()
