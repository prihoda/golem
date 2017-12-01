#Golem configuration

In your settings.py, create a dict and name it **GOLEM_CONFIG**.

Inside it, you can put these configuration options:

* MSG_LIMIT_SECONDS     delay before a message is discarded
* SCHEDULE_CALLBACKS
* REDIS                 **REQUIRED** reference to redis config
* WIT_TOKEN             **REQUIRED** token for https://Wit.ai
* BOTS                  **REQUIRED** list of all dialog flows
* WEBHOOK_SECRET_URL    Secret url prefix for all messaging platforms.
* WEBHOOK_VERIFY_TOKEN  Token sent to verify requests by messaging platforms.
* FB_PAGE_TOKEN
* TELEGRAM_TOKEN
* MS_BOT_ID
* MS_BOT_NAME
* MS_BOT_TOKEN
* DEPLOY_URL            Root url of your bot's web server. Required for callbacks.
* NLP_DATA_DIR          Directory where NLP data will be saved.
* NLP_LANGUAGE          Default language of NLP. Supported values: cz, en
* WEBGUI_BOT_IMAGE      Path to your bot's icon, relative to STATIC_ROOT
* WEBGUI_USER_IMAGE
* DUCKLING_URL          Url of your duckling server. Only used with built-in NLP.
* DUCKLING_LANGUAGE     Locale parameter passed to Duckling in requests.
