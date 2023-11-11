#!/usr/bin/env python3

from datetime import date
import time
import requests
import sys
import os
from os.path import join
import json
import io

import argparse 

# Constants
CONTEXT_KEY_NAME = "name"
CONTEXT_KEY_WEBHOOK_URL = "webhook_url"
CONTEXT_KEY_THREAD_ID = "thread_id"
CONTEXT_KEY_SUBJECT = "subject"

DEFAULT_CONTEXT_NAME="default"

class SenderException(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)

class BadConfig(SenderException):
    def __init__(self, message):
        SenderException.__init__(self, message)

class BadResponse(SenderException):
    def __init__(self, message):
        SenderException.__init__(self, message)


class DiscordMessageSender():
    ''' Class which sends messages to discord with multiple groups of settings called "contexts". '''


    def __init__(self, config_file_path = None):
        ''' Initialize a Discord Message Sender '''
        if config_file_path is None:
            config_dir = os.environ.get("XDG_CONFIG_DIR", 
                    join(os.environ.get("HOME", "."), ".config"))
            config_dir = join(config_dir, "discord_message_sender")
            config_file = join(config_dir, "discord_message_sender.json")
            self.config = Config(config_file)


    def get_context(self, context_name):
        ''' Retrieve a context settings based on its name. '''
        if not context_name in self.config.contexts:
            default_context = self.config.contexts.get(DEFAULT_CONTEXT_NAME, {})
            result = self.config.contexts.setdefault(context_name, {})
            result.update(default_context)
        else:
            result = self.config.contexts[context_name]

        return result
        

    def send_message(self, context, message, force_new_message = False):
        ''' Send the message using settings from the context provided. '''
        # If the context is a string (so context name) retrieve the context for it
        if type(context) == str:
            context = self.get_context(context)

        # To create a new thread, we simply discard thread_id
        if force_new_message or CONTEXT_KEY_THREAD_ID not in context:
            if CONTEXT_KEY_THREAD_ID in context:
                del context['thread_id']
            message["thread_name"] = "%s %s" % (date.today(), context.get(CONTEXT_KEY_SUBJECT, "Potato"))
        else:
            message[CONTEXT_KEY_THREAD_ID] = context.get(CONTEXT_KEY_THREAD_ID, None)


        # Validate that we have all required info
        if not CONTEXT_KEY_WEBHOOK_URL in context:
            raise BadConfig("Error: The context \"%s\" does not have a webhook_url. Please use --webhook-url to set one. Cannot continue" % context.get(CONTEXT_KEY_NAME, "Unknown"))

        # Send the initial message
        thread_id_component = "&thread_id=%s" % context[CONTEXT_KEY_THREAD_ID]  if CONTEXT_KEY_THREAD_ID in context else ""

        r = requests.post("%s?wait=true%s" % (context[CONTEXT_KEY_WEBHOOK_URL], thread_id_component), data=message)
    
        # Retrieve the status code from the initial message
        status_code = r.status_code
    
        # If there's an error, abort
        if status_code < 200 or status_code >= 300:
            raise BadResponse("Error: Response code %s and text \"%s\"" % (r.status_code, r.text))
    
        result = {}

        # Check if the result is an appropriate shape
        if "Content-Type" not in r.headers or not r.headers["Content-Type"] == "application/json":
            raise BadResponse("Error: Response code was %s however response is NOT json. Is your webhook correct?" % (r.status_code))
        else:
            result = r.json()

        # Save the thread id when one isn't present so that replies can be submitted
        if not CONTEXT_KEY_THREAD_ID in context:
            context[CONTEXT_KEY_THREAD_ID] = result["id"]
    
        return result




class Config:
    ''' The configuration of our DiscordMessageSender. '''


    def __init__(self, config_file, autoload = True, autosave = True):
        ''' Constructs a Config object and auto-loads settings from file if specified. '''
        self.config_file = config_file
        # Represents map of names to contexts
        self.contexts = {
            DEFAULT_CONTEXT_NAME: { CONTEXT_KEY_NAME: "default" }
        }

        # Indicates if we should load-from-file on initialization
        self.autoload = autoload
        # indnicates if we should save-to-file on deconstruction
        self.autosave = autosave

        # Load if indicated
        if self.autoload:
            self.load()


    def __del__(self):
        ''' Destructs our config, saving it if autosave is true. '''
        if self.autosave:
            self.save()


    def load(self):
        ''' Loads settings from the configuration file. '''
        if not os.path.isfile(self.config_file):
            return
        with open(self.config_file) as file:
            self.contexts = json.load(file)


    def save(self):
        ''' Saves settings to the configuration file.'''
        config_dir = os.path.dirname(self.config_file)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        with io.open(self.config_file, "w") as file:
            json.dump(self.contexts, file, indent=4)


    def list_contexts(self):
        ''' Lists all known contexts and their settings '''
        if self.config.contexts:
            print("Listing contexts and their webhooks:")
            for name, context in self.config.contexts.items():
                print("  - \"%s\": %s" % (name, context))
        else:
            print("There are no contexts yet.")


    def delete_context(self, context_name):
        ''' Deletes the settings of the context with the name provided. '''
        if context_name in self.contexts:
            del self.contexts[context_name]
            print("Deleted context \"%s\"" % context_name)
        else:
            print("Context \"%s\" was not found." % context_name)






def handle_cmdline_invocation():
    # Parse Arguments
    arg_parser = argparse.ArgumentParser(
        description="Sends messages in threads to discord forum channels."
    )
    arg_parser.add_argument("-n", "--new-message"  , help="Send the next message as a new forum post, not a reply." , action='store_true')
    arg_parser.add_argument("-c", "--context"      , help="Specify the context name which should be used." , default=DEFAULT_CONTEXT_NAME)
    arg_parser.add_argument("-s", "--subject"      , help="Specify the subject of the context which is used when a new post is created." , default=None)
    arg_parser.add_argument("-u", "--webhook-url"  , help="Specify the webhook url to send requests to." , default=None)
    arg_parser.add_argument("-l", "--list-contexts", help="List known contexts and their settings instead of sending a message." , action="store_true")
    arg_parser.add_argument("--rm-context"         , help="Remove the configuration of current context from the settings." , action="store_true")
    arg_parser.add_argument("--rm-thread-id"       , help="Remove the thread_id from the current context." , action="store_true")
    arg_parser.add_argument("message"              , help="Specify the message to send as a post or reply to a previous post." , nargs="*")
    args = arg_parser.parse_args()

    # Initialize our sender
    message_sender = DiscordMessageSender()

    # Retrieve our context
    context = message_sender.get_context(args.context)
    
    # Updates from arguments
    if args.webhook_url:
        context[CONTEXT_KEY_WEBHOOK_URL] = args.webhook_url
    if args.subject:
        context[CONTEXT_KEY_SUBJECT] = args.subject

    # These are basically the "modes" this script may be run in.
    if args.list_contexts:
        message_sender.config.list_contexts()


    elif args.rm_context:

        message_sender.config.delete_context(args.context)

    elif args.rm_thread_id:

        if CONTEXT_KEY_THREAD_ID in context:
            del context[CONTEXT_KEY_THREAD_ID]
        print("Cleared the thread_id from context \"\"" % args.context)

    else:

        message = {
            "content": " ".join(args.message)
        }
        
        if message["content"]:
            message_sender.send_message(context, message, args.new_message)


if __name__ == "__main__":
    try:
        handle_cmdline_invocation()
    except SenderException as e:
        raise SystemExit(e)
