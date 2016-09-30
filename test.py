from messenger.messenger import Messenger
from fb_messenger import post_message

uid = "test_user"
text = 'Hi'
developer_mode = True

Messenger.send_to_bot(post_message, uid, text, developer_mode)
