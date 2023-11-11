Discord Message Sender
======================

Quick repo exploring the discord API for sending messages and the like.

Details of discord\_send\_message.py
------------------------------------
  - This script allows sending messages to discord forum channels via webhooks
  - Supports multiple "contexts", each with a name, webhook\_url, and a subject
  - The default context is called "default" and its config will be used as a
    template for all new contexts
  - A new message (either the first, or with --new-message) will create a new
    forum topic in the discord channel associated with the webhook.
  - One may specify contexts with --context
  - One may delete contexts with --rm-context (pair with --context)
  - One may send new messages with --new-message
  - Please see the --help option for more details.
  - Configs are saved in `XDG_CONFIG_DIR` (typically ~/.config/discord\_send\_message.json)
