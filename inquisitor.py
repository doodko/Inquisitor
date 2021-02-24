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
        check_horses(message)
        if message.entities:
            bot.delete_message(message.chat.id, message.message_id)
            text = f'{mention_user(message)}, не встигли зайти в чат і одразу посилання вставляти\? ' \
                   f'У нас так не прийнято, спочатку ознайомтесь з [правилами]({config.rules_url})\.'
            bot.send_message(message.chat.id, text, parse_mode='MarkdownV2')
            data['tips'] += 1
        else:
            all_text_messages(message)

    else:
        msg = f'{make_fullname(message)} wrote to {message.chat.id} chat: ' \
              f'"{message.text}" and wasn\'t banned because of turned off moderation'
        log_it(msg)


@bot.edited_message_handler(func=lambda message: message.text
                            and message.chat.id == GROUP
                            and data["quarantine"].get(str(message.from_user.id), 0) > time())
def edit_message(message):
    filer_new_members(message)


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
            working = (datetime.date.today() - datetime.date(2021, 2, 20)).days
            bans, tips = data["banned"], data["tips"]
            msg = f"I'm working for you for {working // 30} month and {working % 30} days already.\n" \
                  f"{bans} horses were banned, {tips} tips were given."
            bot.send_message(message.chat.id, msg)


@bot.message_handler(commands=['ask_volodya'])
def ask_volodya(message):
    if message.reply_to_message:
        command = message.text.replace('@pk_moderatorbot', '')
        if len(command.strip()) >= 15:
            req = command[13:]
        else:
            req = 'одним словом'
        msg = f"Спробуйте запитати у Володі\:\n1\. Відкриваємо чат з ботом @pkvartal\_bot\n" \
              f"2\. Пишемо йому запит *{req}*\n3\. Отримуємо релевантні результати\. Профіт\!"
        bot.delete_message(message.chat.id, message.message_id)
        bot.send_message(message.chat.id, msg, reply_to_message_id=message.reply_to_message.message_id,
                         parse_mode='MarkdownV2')
        log_message = f"{make_fullname(message)} used the command ask_volodya"
        log_it(log_message)
        data["tips"] += 1
    else:
        bot.delete_message(message.chat.id, message.message_id)


@bot.message_handler(commands=['read_rules'])
def read_rules(message):
    if message.from_user.username in config.admins:
        if message.reply_to_message:
            user = message.reply_to_message.from_user
            bot.delete_message(message.chat.id, message.message_id)
            bot.delete_message(message.chat.id, message.reply_to_message.id)
            msg = f'[{user.first_name}](tg://user?id={user.id}), ознайомтесь з ' \
                  f'[правилами группи]({config.rules_url}), будь ласка\.'
            bot.send_message(message.chat.id, msg, message.reply_to_message.message_id, parse_mode='MarkdownV2')
            log_message = f"{make_fullname(message)} used the command read_rules"
            log_it(log_message)
            data["tips"] += 1
        else:
            bot.delete_message(message.chat.id, message.message_id)
    else:
        msg = f"{mention_user(message)}, радий що Ви спитали про правила\. [Осьо вони]({config.rules_url}), " \
              f"тепер я слідкую щоб Ви не порушували\."
        bot.send_message(message.chat.id, msg, reply_to_message_id=message.message_id, parse_mode='MarkdownV2')


@bot.message_handler(commands=['use_search'])
def use_search(message):
    if message.reply_to_message and message.from_user.username in config.admins:
        bot.delete_message(message.chat.id, message.message_id)
        user = message.reply_to_message.from_user
        msg = f'[{user.first_name}](tg://user?id={user.id}), в телеграм дуже зручно реалізований пошук по чату, ' \
              f'спробуйте скористатись ним\. Зверху натискаємо три крапочки \=\> пошук\.'
        bot.send_message(message.chat.id, msg, reply_to_message_id=message.reply_to_message.message_id,
                         parse_mode='MarkdownV2')
        log_msg = f"{make_fullname(message)} used the command use_search"
        log_it(log_msg)
        data["tips"] += 1
    else:
        bot.delete_message(message.chat.id, message.message_id)


# ----------------------- FUNCTIONS -------------------------
def save_data():
    with open(config.data_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_data():
    with open(config.data_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def log_it(msg):
    log = f"{date_and_time()} : {msg}\n"
    with open(config.log_file, 'a', encoding='utf-8') as f:
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


def check_horses(message):
    if any([chr(i) in message.text for i in (128014, 127943, 128052)]):
        reason = "horses emoji from new user"
        ban_user(message, reason)
    elif len([ord(i) for i in message.text if 180 < ord(i) < 1040 or 1112 < ord(i)]) > 7:
        count = len([ord(i) for i in message.text if 180 < ord(i) < 1040 or 1112 < ord(i)])
        reason = f"too many symbols ({count}) from new user"
        ban_user(message, reason)
    elif any(map(lambda match: re.search(match, re.sub(r'[\W]', '', message.text.lower())), config.reglist)):
        reason = "horses regex from new user"
        ban_user(message, reason)


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


def mention_user(message):
    if message.from_user.username:
        mention = '@' + message.from_user.username
    else:
        mention = f"[{message.from_user.first_name}](tg://user?id={message.from_user.id})"

    return mention


# --------------------------ALL OTHER MESSAGES -------------------------------------------
@bot.message_handler(content_types=['text'])
def all_text_messages(message):
    if any(_ in message.text for _ in config.groups) \
            and message.entities and message.from_user.username not in config.admins:
        msg = f"{mention_user(message)}, не публікуйте лінки на групи ПК в загальному чаті, будь ласка \- надсилайте " \
              f"їх в особисті повідомлення\. Дякую\!"
        bot.delete_message(message.chat.id, message.message_id)
        bot.send_message(message.chat.id, msg, parse_mode='MarkdownV2')
        log_msg = f'Bot has deleted a message from {make_fullname(message)} with a link to groups: {message.text}'
        log_it(log_msg)
        data['tips'] += 1
    elif re.search(config.regs['sale_rent'], message.text.lower()) and message.from_user.username not in config.admins:
        bot.delete_message(message.chat.id, message.message_id)
        msg = f'{mention_user(message)}, пропозиції нерухомості не в цьому чаті\.'
        bot.send_message(message.chat.id, msg, parse_mode='MarkdownV2')
        log_msg = f'Bot has deleted a message from {make_fullname(message)} with sale-rent proposition: {message.text}'
        log_it(log_msg)
        data['tips'] += 1
    elif any(_ in message.text for _ in config.links) and message.from_user.username not in config.admins:
        bot.delete_message(message.chat.id, message.message_id)
        msg = f'{mention_user(message)}, це посилання публікували вище вже три рази\. Думаю, достатньо\.'
        bot.send_message(message.chat.id, msg, parse_mode='MarkdownV2')
        log_msg = f'Bot has deleted a message from {make_fullname(message)} with petition: {message.text}'
        log_it(log_msg)
        data['tips'] += 1
    elif re.search(config.regs['advice_master'], message.text.lower()) \
            and message.from_user.username not in config.admins:
        msg = f'{mention_user(message)}, на щастя, ви не перші стикнулись з такою необхідністю \- це питання ' \
              f'вже багаторазово обговорювалось вище і радили різних майстрів\. Ви дивились попередні ' \
              f'рекомендації і всі вони не підійшли\? Якщо досі ні \- раджу скористатись пошуком, він ' \
              f'тут дуже зручно реалізован \:\)'
        bot.send_message(message.chat.id, msg, parse_mode='MarkdownV2', reply_to_message_id=message.message_id)
        log_msg = f'Bot has advised to use the search to {make_fullname(message)} with message: {message.text}'
        log_it(log_msg)
        data['tips'] += 1


# ---------------------------------------------------------------------------------------
if __name__ == '__main__':
    data = load_data()
    bot.send_message(SUPERUSER, 'Bot started')
    bot.infinity_polling()
