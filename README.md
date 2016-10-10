# Golem chatbot framework

Golem is a python framework for building chatbots for Messenger and other platforms.

What it can do:
- Receive messages from Messenger (Telegram and more platforms coming soon)
- Extract *entities* from these messages using [Wit.ai](http://wit.ai)
  - e.g. "Show me the best concert" -> *intent:* recommend, *query:* concert
- Move between different *states* of the conversation based on intent and other entities
- Keep track of the history of all entity values in the *context*
- Call actions of these states and return messages

What it can NOT do:
- it does not pre-train Wit, you have to do that yourself
- it does not use Wit stories, only entity recognition
- it's not built for AI conversational bots (you can try though :P)

***

# Build your own bot

TL;DR: Here's what you'll need to do to build your own bot:

1. Think up a useful bot
2. Figure out what phrases and entities it should understand and teach them to your Wit.ai app
3. Clone and setup our repo
4. Design the flow = states of the conversation
5. Create actions for each state
  - use *templates* for common actions such as text messages or asking for input
  - implement *python functions* for custom actions such as returning items from the database
6. Profit!

# Usage

## How to use this module

### In your custom server app

### Using django example project

## Wit training

## Flows and states

The dialog is managed by flows. Each flow represents one or more intents and contains several states. 

Your dialog begins in a flow called *default*. Each flow starts in the *root* state. 

Flows are defined in python like so:

```python
{
    'default' : { # name of the flow, automatically accept intent of the same name
        'intent' : '(greeting|help)', # regex of additional intents to accept 
        'states' : { # dictionary of states
            'root' : { # the root state
                'accept' : {
                    'template' : 'message',
                    'params' : {
                        'message' : 'Hi, welcome to IT support! :)',
                        'next' : 'question'
                    }
                }
            },
            'question' : {
                'init' : my_custom_action,
                'accept' : my_input_action
            }
         ...
         
```

## Actions

Each state has two actions - **init** and **accept**.

An action can be defined either by a **template** or by a **function**.

### Init and accept

**Init** is run when you arrive directly from another state. It can be used to send messages to the user without requesting any input.

**Accept** is run when a message from the user is received. It can be used for processing input.

### Template actions

**Templates** are used for common actions like sending text messages or requesting input. 


<table style="font-size: 80%">
  <tr>
    <th>Template type</th>
    <th>Parameter</th>
    <th>Param type</th>
    <th>Default value</th>
    <th>Description</th>
    <th>Example</th>
  </tr>
  <tr>
    <td rowspan="3"><strong> message </strong></td>
    <td colspan="5">Send one or more pre-defined messages</td>
  </tr>
  <tr>
    <td>message</td>
    <td><a href="#responsetypes">Response</a>, String or a list of these</td>
    <td><em>required</em></td>
    <td>List of messages to send to the user</td>
    <td rowspan="2">
        <pre>
{
    'type' : 'message',
    'params' : {
        'message' : ['Hi :)','How are you?'],
        'next' : 'search.root'
    }
}</pre>
    </td>
  </tr>
  <tr>
    <td>next</td>
    <td>String</td>
    <td>None</td>
    <td>Name of the state to transfer to</td>
  </tr>
  <tr>
    <td rowspan="5"><strong> input </strong><br></td>
    <td colspan="5">Request input of a specific entity</td>
  </tr>
  <tr>
    <td>entity</td>
    <td>String</td>
    <td><em>required</em></td>
    <td>Name of entity to wait for</td>
    <td rowspan="5">
        <pre>
{
    'template' : 'input',
    'params' : {
        'entity' : 'yes_no',
        'missing_message' : TextMessage('Choose one :)', quick_replies=[
            {'title':'Yes'},
            {'title':'No'}
        ]),
        'next' : 'search.root'
    }
}</pre>
    </td>
  </tr>
  <tr>
    <td>text</td>
    <td>Boolean</td>
    <td>False</td>
    <td>If True, accept raw text input and save it into the specified entity (in this case, missing_message is never used)</td>
  </tr>
  <tr>
    <td>missing_message</td>
    <td><a href="#responsetypes">Response</a>, String or a list of these</td>
    <td>None</td>
    <td>Text response to send when the entity is not received in the message</td>
  </tr>
  <tr>
    <td>next</td>
    <td>String</td>
    <td>None</td>
    <td>Name of the state to transfer to after successful input</td>
  </tr>
</table>


To see all the templates in action check out the *Example chatbot*.

### Custom function actions



## Platforms

## Response types

***
