# Golem chatbot framework

Golem is a python framework for building chatbots for Messenger and other platforms.

What it can do:
- Receive messages from Messenger (Telegram and more platforms coming soon)
- Extract *entities* from these messages using [Wit.ai](http://wit.ai)
  - e.g. "Show me the best concert" -> *intent:* recommend, *query:* concert
- Keep track of the history of all entity values in the *context*
- Move between different *states* of the conversation based on intent and other entities
- Call actions of these states and return messages
- It supports any language supported by Wit (English is recommended)

What it can NOT do:
- It does not pre-train Wit, you have to do that yourself
- It does not use Wit stories, only entity recognition
- It's not built for AI conversational bots (you can try though :P)

# Docs

Find out how to make your own bot on the **[Wiki](https://github.com/prihoda/golem/wiki)**.
