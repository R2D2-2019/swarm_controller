import json
import threading
import queue
import inspect

import common.frames
from client.comm import BaseComm

from module.command_node import CommandNode


class CLIController:

    def __init__(self, comm: BaseComm, command_file_list=None):
        """
        Filenames given have to be JSON files.
        """
        self.comm = comm
        self.root_node = CommandNode("ROOT")

        self.input_queue = queue.Queue()
        self.input_thread = threading.Thread()

        # These function as preserved keywords, do not use these names in commands

        self.global_commands = {
            "EXIT":     self.stop,
            "LEAVE":    self.stop,
            "QUIT":     self.stop,
            "Q":        self.stop,
            "HELP":     self.print_help,
            "BACK":     self.go_back_in_tree,
            "RETURN":   self.go_back_in_tree,
            "ROOT":     self.go_to_root
        }
        self.module_commands = []
        self.command_file_list = command_file_list
        self.load_tree()
        self.current_node = self.root_node

        self.stopped = False


    def load_tree(self):
        """
        Loads all files into command structure
        """
        for file in self.command_file_list:
            self.load_commands(file, self.root_node)

    def add_frame_commands(self, root_node):
        """
        Adds all commands from the common.frames file
        """
        #check if robot already exists, otherwise create it
        if not 'ROBOT' in root_node:
            root_node["ROBOT"] = CommandNode("ROBOT")          
        current_node = root_node["ROBOT"]

        #get class information from common.frames
        frames = inspect.getmembers(common.frames, lambda member: inspect.isclass(member) and member.__module__ == 'common.frames')
        #removes files without a desciption
        commands = [frame for frame in frames if frame[1].DESCRIPTION ]
        
        #add all commands to root node
        for command in commands:
            target_node = CommandNode(
                command[0][5:],
                parameter_list=inspect.getfullargspec(command[1].set_data).annotations,
                command_info=command[1].DESCRIPTION
            )
            target_node.set_parent(current_node)
            current_node[target_node.name] = target_node

    def add_command_from_json(self, json_command, root_node):
        """
        add one json command to root node
        THE GIVEN COMMAND MUST COME FROM A JSON FILE OTHERWISE THIS FUNCTION WILL NOT WORK
        """
        prohibited_keywords = set().union(*self.global_commands.keys())
        json_command["target"] = json_command["target"].upper()
        if json_command["target"] in prohibited_keywords:
            exit("Used keyword {} as target. Using keywords is prohibited!".format(json_command["target"]))
        current_node = root_node

        # Per path checking if it has a child
        json_command["path"] = json_command["path"].upper()
        for path_piece in json_command["path"].split(" "):
            if path_piece in prohibited_keywords:
                exit("Used keyword {} as target. Using keywords is prohibited!".format(command["target"]))

            # If the current path info already exists, traverse the tree
            # Else, add the missing link

            if path_piece in current_node:
                current_node = current_node[path_piece]
            else:
                new_node = CommandNode(path_piece, current_node)
                new_node.set_parent(current_node)
                current_node[new_node.name] = new_node
                current_node = new_node

        # After all the missing links in the tree are made, add the command
        target_node = CommandNode(
            json_command["target"],
            parameter_list=json_command["parameters"],
            command_info=json_command["info"]
        )
        target_node.set_parent(current_node)
        current_node[target_node.name] = target_node


    def load_commands(self, file, root_node):
        """
        Loads a single JSON file into command structure
        And loads all the frames from common.frames.py to the command structure
        """
        with open(file, "r") as json_file:
            data = json.load(json_file)
        try:
            # Add all commands from previously collected data
            for command in data["commands"]:
                self.add_command_from_json(command, root_node)
        except KeyError as error:
            print("Key {} was not found".format(error))

        # Add all commands from the cpp frames
        self.add_frame_commands(root_node)

    @staticmethod
    def make_path_string(path_list):
        """
        Joins given list and appends a ':'
        Expects a list
        """
        return ' / '.join(path_list) + ":"

    def print_help(self):
        node = self.current_node
        """
        Prints the info and any children or parameters of the node.
        """
        print(node.name + ":")
        print("\tInfo: " + node.command_info)
        if node.parameter_list:
            print("\tParameters: (" + (", ".join(node.parameter_list)) + ")")
        elif len(node) > 0:
            print("\tPossible commands: {}".format(", ".join(node[n].name.lower() for n in node.keys())))
        else:
            print("\tThis function requires no parameters and has no children")

    @staticmethod
    def ask_input(input_queue: queue.Queue, string=""):
        """
        Starts a new thread asking the user for input and writes this input to the given input_queue
        Optional string for input
        """
        i = input(string)
        input_queue.put(i)

    """
    Starts a new thread to make nonblocking input possible. And get the current location, after restart this is always just root
    """
    def start_thread(self):
        s = self.make_path_string(self.current_node.get_branch_names()) + " "
        self.input_thread = threading.Thread(target=self.ask_input, args=(self.input_queue, s))
        self.input_thread.daemon = True
        self.input_thread.start()

    """
    Go back one node in the tree structure. You cant go back when in root
    """
    def go_back_in_tree(self):
        if self.current_node.parent:
            self.current_node = self.current_node.parent

    """
    Go to root in tree structure
    """
    def go_to_root(self):
        self.current_node = self.root_node

    """
    Handles all non-global commands. Returns false if failed or if a function has been executed(in this case no other commands can be executed after).
    Returns true if another command can be executed after this one
    """
    def handle_nonglobal_commands(self, user_word, user_command_list):
        if user_word.upper() in self.current_node.keys():
            self.current_node = self.current_node[user_word.upper()]
            return True

        elif len(self.current_node.parameter_list) > 0:
            print("\tCommand called with {} parameters: {}".format(
                len(user_command_list[user_command_list.index(user_word):]),
                "(" + ",".join(user_command_list[user_command_list.index(user_word):]) + ")"
            ))

        elif user_word:
            print("\tCommand {} not found, type \"help\" for possible commands.".format(user_word))
        return False

    """
    Execute a command depending on text entered
    """
    def handle_new_input(self):
        user_command_list = self.input_queue.get().split(" ")
        for user_word in user_command_list:

            # Step 1: Check for global commands
            if user_word.upper() in self.global_commands.keys():
                self.global_commands[user_word.upper()]()
                    
            # Step 2: Check for location(in tree structure) specific commands
            else:
                if not self.handle_nonglobal_commands(user_word, user_command_list):
                    break
                
    """
    Starts an infinite loop (until exit command is called) which polls for input
    """
    def run_cli(self):
        """
        Starts thread asking for input if it is currently not and the input_queue is not filled.
        Otherwise processes items in the input_queue.
        """
        if not self.input_thread.isAlive() and self.input_queue.empty():
            self.start_thread()
        elif not self.input_queue.empty():
            self.handle_new_input()


    def process(self):
        """
        Main loop of the module
        """
        while self.comm.has_data():
            frame = self.comm.get_data()

        self.run_cli()



    def stop(self):
        """
        Stops the CLIController
        """
        if self.input_thread:
            self.input_thread.join()
        self.comm.stop()
        self.stopped = True
