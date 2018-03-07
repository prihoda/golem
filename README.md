# Golem chatbot framework

Golem is a python framework for building chatbots for Messenger, Telegram and other platforms.

What it can do:
- __Receive messages__ from __Messenger__ and __Telegram__ (Actions on Google coming soon)
- __Extract entities__ from these messages using [Wit.ai](http://wit.ai)
  - e.g. "Show me the best concert" -> *intent:* recommend, *query:* concert
- __Keep track of the history__ of all entity values in the *context*
- __Move between different states__ of the conversation based on intent and other entities
- Call your functions for each state and return messages (images and lists too)
- It supports any language supported by Wit (English is recommended)
- Golem now has its own __web GUI__ for chatting

What it can NOT do:
- It does not pre-train Wit, you have to do that yourself
- It does not use Wit stories, only entity recognition
- It's not built for AI conversational bots (you can try though :P)

# Docs

It's very easy to get started!

Find out how to make your own bot on the **[Wiki](https://github.com/prihoda/golem/wiki)**.

Made @ [FIT CTU](https://fit.cvut.cz/en) in Prague.