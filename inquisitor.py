import telebot
import config
import datetime
from time import time
import json
import re

bot = telebot.TeleBot(config.TOKEN)
GROUP = config.group
SUPERUSER = config.superuser


# ----------------------------- QUARANTINE -------------------------------------------------
@bot.message_handler(content_types=["new_chat_members"])
def handler_new_member(message):
    if data['moderation']:
        if check_username(message):
            ban_user(message, 'Bad Username')

    else:
        bot.restrict_chat_member(GROUP, message.from_user.id, until_date=time() + data["restrict_user"],
                                 can_send_messages=True)
        user_id = str(message.from_user.id)
        date = int(message.date)
        data["quarantine"] = {key: value for key, value in data["quarantine"].items() if value > date}
        data["quarantine"][user_id] = date + data['quarantine_time']
        save_data()
        quarantine = datetime.datetime.fromtimestamp(data["quarantine"][user_id]).strftime('%Y-%m-%d %H:%M:%S')
        msg = f'{make_fullname(message)} joined the chat {message.chat.title}. Quarantine until {quarantine}'
        log_it(msg)


# ----------------------------- FILTER FOR NEW MEMBERS --------------------------------------------
@bot.message_handler(func=lambda message: message.text
                                          and message.chat.id == GROUP
                                          and data["quarantine"].get(str(message.from_user.id), 0) > time())
def filer_new_members(message):
    if data['moderation']:
        # horses emoji
        if any([chr(i) in message.text for i in (128014, 127943, 128052)]):
            reason = "horses emoji from new user"
            ban_user(message, reason)

        # symbols in message
        elif len([ord(i) for i in message.text if 180 < ord(i) < 1040 or 1112 < ord(i)]) > 7:
            count = len([ord(i) for i in message.text if 180 < ord(i) < 1040 or 1112 < ord(i)])
            reason = f"too many symbols ({count}) from new user"
            ban_user(message, reason)

        # horses in message
        elif any(map(lambda match: re.search(match, re.sub(r'[\W]', '', message.text.lower())), config.reglist)):
            reason = "horses regex from new user"
            ban_user(message, reason)

        else:
            msg = f'{date_and_time()} : {make_fullname(message)} wrote to {message.chat.id} chat: "{message.text}"'
            # print(msg)

    else:
        msg = f"user {message.from_user.id} said {message.text} and was not banned in {message.chat.title}."
        log_it(msg)


# ------------------------------- COMMANDS ------------------------------------------------
@bot.message_handler(commands=['send_message'])
def send(message):
    if message.from_user.username in config.admins:
        admin_message = message.text[14:]
        if admin_message:
            msg = f"@{message.from_user.username} sent message to all: {admin_message}"
            log_it(msg)
            bot.send_message(GROUP, admin_message)


@bot.message_handler(commands=['turn_on_moderation', 'turn_off_moderation'])
def turn_moderation(message):
    if message.from_user.username in config.admins and message.chat.id != GROUP:
        if message.text == '/turn_on_moderation':
            data['moderation'] = True
            msg = f'@{message.from_user.username} turned on moderation'
            bot.send_message(message.chat.id, 'Модерацію увімкнено', reply_to_message_id=message.message_id)
            log_it(msg)

        elif message.text == '/turn_off_moderation':
            data['moderation'] = False
            msg = f'@{message.from_user.username} turned off moderation'
            bot.send_message(message.chat.id, 'Модерацію вимкнено', reply_to_message_id=message.message_id)
            log_it(msg)

        save_data()


@bot.message_handler(commands=['print_data', 'print_status'])
def print_data(message):
    if message.from_user.username in config.admins:
        if message.text == '/print_data':
            bot.send_message(message.chat.id, f'{data}')
        elif message.text == '/print_status':
            working = (datetime.date.today() - datetime.date(2021, 2, 17)).days
            bans, tips = data["banned"], data["tips"]
            msg = f"I'm working for you for {working // 30} month and {working % 30} days already.\n" \
                  f"{bans} horses were banned, {tips} tips were given."
            bot.send_message(message.chat.id, msg)


# ----------------------- FUNCTIONS -------------------------
def save_data():
    with open(config.data_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_data():
    with open(config.data_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def log_it(msg):
    log = f"{date_and_time()} : {msg}\n"
    with open('/root/Inquisitor/log.log', 'a', encoding='utf-8') as f:
        f.write(log)


def make_fullname(message):
    name = f"{message.from_user.id} {message.from_user.first_name}"
    if hasattr(message.from_user, 'last_name') and message.from_user.last_name is not None:
        name += f" {message.from_user.last_name}"
    if hasattr(message.from_user, 'username') and message.from_user.username is not None:
        name += f" (@{message.from_user.username})"
    return name


def date_and_time():
    return datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S")


def ban_user(message, reason):
    msg = f"{make_fullname(message)} was banned in {message.chat.title}. Reason: {reason} in message \"{message.text}\"."
    bot.delete_message(message.chat.id, message.message_id)
    bot.send_message(SUPERUSER, msg)
    bot.kick_chat_member(message.chat.id, message.from_user.id, until_date=0)
    log_it(msg)
    data["banned"] += 1
    save_data()


def check_username(message):
    name = (message.from_user.first_name + (message.from_user.last_name or '')).lower()
    if (any(map(lambda match: re.search(match, re.sub(r'[\W]', '', name)), config.reglist))) or \
            (any([chr(i) in name for i in (128014, 127943, 128052)])) or \
            (len([ord(i) for i in name if 180 < ord(i) < 1040 or 1112 < ord(i)]) > 7):
        return True
    else:
        return False


# --------------------------ALL OTHER MESSAGES -------------------------------------------
@bot.message_handler(content_types=['text'])
def all_text_messages(message):
    chat = lambda message: message.chat.title or 'private'
    msg = f'{date_and_time()} : {make_fullname(message)} wrote to {chat(message)} chat: "{message.text}"'
    # print(msg)


# ---------------------------------------------------------------------------------------
if __name__ == '__main__':
    data = load_data()
    log_it('Bot started')
    bot.send_message(SUPERUSER, 'Bot started')
    bot.infinity_polling()
