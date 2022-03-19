import json, datetime, sqlite3, sys, os, inspect, time
from contextlib import nullcontext
from pickletools import uint1
from socket import timeout
from time import sleep
from uuid import uuid4
from requests import Session
from telegram import InlineQueryResultArticle, InlineKeyboardButton, InlineKeyboardMarkup, Update, InputTextMessageContent
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    CallbackContext,
    InlineQueryHandler,
    MessageHandler,
    Filters
)
from telegram.utils.helpers import escape_markdown

TOKEN = "telegram_token"
API_KEY_COINMARKETCUP = "coinmarketcup_token"

def round_price(price):
    forRound = {10000:0,
                1000:1,
                100:2,
                10:3,
                1:4,
                0.1:5,
                0.01:6,
                0.001:7,
                0.0001:8}
    for above, r in forRound.items():
        if price > above: return(round(price, r))
    return (price)

def get_script_dir(follow_symlinks=True):
    if getattr(sys, 'frozen', False): # py2exe, PyInstaller, cx_Freeze
        path = os.path.abspath(sys.executable)
    else:
        path = inspect.getabsfile(get_script_dir)
    if follow_symlinks:
        path = os.path.realpath(path)
    return os.path.dirname(path)

def load_from_db(uId):
    sqlite_connection = sqlite3.connect(DB_PATCH)
    cursor = sqlite_connection.cursor()
    try:
        cursor.execute('''SELECT coinList FROM users WHERE id = '''+str(uId))
        one_user_load = cursor.fetchone()
        sqlite_connection.close()
    except Exception as e:
        print(e)
        return([])
    if one_user_load and one_user_load[0]:
        return (one_user_load[0].split("%"))
    else: return([])

def save_to_db(uId, one_user_list, name="?", surname="?"):
    coinString = ""
    for coin in one_user_list:
        if coinString: coinString+="%"+coin
        else: coinString = coin
    one_user = (uId,coinString, name, surname)

    sqlite_connection = sqlite3.connect(DB_PATCH)
    cursor = sqlite_connection.cursor()
    try:
        if not one_user_list:
            cursor.execute('''DELETE FROM users WHERE id = '''+str(uId))
            sqlite_connection.commit()
            return True
        cursor.execute('''SELECT coinList FROM users WHERE id = '''+str(one_user[0]))
        if not cursor.fetchall(): 
            cursor.execute('''INSERT INTO users VALUES(?,?,?,?)''', one_user)
        else:
            cursor.execute('UPDATE users SET coinList = "'+one_user[1]+'" where id = '+str(one_user[0]))
        sqlite_connection.commit()
        sqlite_connection.close()
        return True
    except Exception as e:
        print(e)
        return False
    
def get_data(uId, name=""):
    if datetime.datetime.now() - lastRequestTime > datetime.timedelta(minutes=10):
        url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
        parameters = {'limit':500}
        headers = {'Accepts': 'application/json','X-CMC_PRO_API_KEY': API_KEY_COINMARKETCUP,}

        session = Session()
        session.headers.update(headers)
        try:
            response = session.get(url, params=parameters)
            data = json.loads(response.text)
            print("New responce to Coinmarketcup")
            if data["status"]["error_code"] != 0: return({"status":0, "data":data["status"]["error_message"]})
        except: return({"status":0, "data":"Unknown error"})
        globals()["requestData"] = data
        globals()["lastRequestTime"] = datetime.datetime.now()
        if not iconsDict:
            for item in requestData["data"]:
                 globals()["iconsDict"][item["symbol"].upper()] = item["id"]

    if not name:
        summary20Item = {"status":0, "data":{}}
        one_user_list = load_from_db(uId)
        if one_user_list:
            for item in requestData["data"]:
                if item["symbol"].upper() in one_user_list:
                    summary20Item["data"][item["symbol"]] = "{0} ({1}): {2}$ ({3}%)".format(
                                        item["symbol"], 
                                        item["name"], 
                                        round_price(item["quote"]["USD"]["price"]), 
                                        round(item["quote"]["USD"]["percent_change_24h"], 2))
        else:
            itemNum = 0
            for item in requestData["data"]:
                summary20Item["data"][item["symbol"]] = "{0} ({1}): {2}$ ({3}%)".format(
                                    item["symbol"], 
                                    item["name"], 
                                    round_price(item["quote"]["USD"]["price"]), 
                                    round(item["quote"]["USD"]["percent_change_24h"], 2))
                itemNum += 1
                if itemNum >= 7: break
        summary20Item["status"] = 200
        return(summary20Item)
    else:
        name = name.upper()
        findedItem = {"status":0, "data":{}}
        for item in requestData["data"]:
            if name in item["symbol"].upper() or name in item["name"].upper():
                findedItem["data"][item["symbol"]] = "{0} ({1}): {2}$ ({3}%)".format(
                                item["symbol"], 
                                item["name"], 
                                round_price(item["quote"]["USD"]["price"]), 
                                round(item["quote"]["USD"]["percent_change_24h"], 2))
        findedItem["status"] = 200
        return(findedItem)
        
# Stages
FORK, SEE, ADD, TIMEOUT = range(4)
# # Callback data
# see, add, back, dellAll, top20, toend = range(6)

def start(update: Update, context: CallbackContext) -> int:
    """Send message on `/start`."""

    keyboard = [
        [
            InlineKeyboardButton("Show favorite", callback_data="see"),
            InlineKeyboardButton("Add currency", callback_data="add"),
        ]
    ]
    text = "Hi "+update._effective_user.name+", I will help you complete the list of favorite cryptocurrencies"
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message: update.message.reply_text(text, reply_markup=reply_markup)
    else: update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    return FORK

def start_over(update: Update, context: CallbackContext) -> int:
    query = update.callback_query

    query.answer()
    keyboard = [
        [
            InlineKeyboardButton("Show favorite", callback_data="see"),
            InlineKeyboardButton("Add currency", callback_data="add"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    query.edit_message_text(text="Hi "+update._effective_user.name+", I will help you complete the list of favorite cryptocurrencies", reply_markup=reply_markup)
    return FORK

def show_list(update: Update, context: CallbackContext) -> int:
    text = ""
    query = update.callback_query
    query.answer()
    uId = query.from_user.id

    #dell from USER LIST
    one_user_list = load_from_db(uId)
    if "dellOne" in query.data:
        cur = query.data[len("dellOne"):]
        if cur in one_user_list: 
            one_user_list.remove(cur) 
            text+="Deleted {0}.\n\n".format(cur)
        else: text+="❗ {0} removal error\n".format(cur)
    elif "dellAll" in query.data:
        one_user_list = []

    #ADDONE    
    elif "addOne" in query.data:
        cur = query.data[len("addOne"):]
        if one_user_list.count(cur) > 0: text+="{0} already added.\n\n".format(cur)
        else: 
            one_user_list.append(cur)
            text+="Added {0} to the list of favorite cryptocurrencies.\n\n".format(cur)

    save_to_db(uId, one_user_list, query.from_user.first_name, query.from_user.last_name)


    keyboard = [[]]
    lvl1 = 0
    lvl2 = 0
    was_add = False
    if one_user_list:
        for tiker in one_user_list:
            was_add = True
            line = InlineKeyboardButton(tiker.upper(), callback_data="dellOne"+tiker)
            if lvl1 < 5:            
                keyboard[lvl2].append(line)
                lvl1 += 1
            else:
                lvl2 += 1
                lvl1 = 1
                keyboard.append([])
                keyboard[lvl2].append(line)
        text+="Your list of cryptocurrencies, select the currency to delete"
        keyboard.append([])
        keyboard[lvl2+1].extend(
            [
                InlineKeyboardButton("Back", callback_data="back"),
                InlineKeyboardButton("Add currency", callback_data="add"),
                InlineKeyboardButton("Delete all", callback_data="dellAll"),
            ]
        )
    else:
        text+="There are no favorite cryptocurrencies"
        lineIndex = 0
        if was_add: lineIndex = lvl2+1
        keyboard[lineIndex].extend(
            [
                InlineKeyboardButton("Back", callback_data="back"),
                InlineKeyboardButton("Add currency", callback_data="add"),
            ]
        )

    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(
        text=text, reply_markup=reply_markup
    )
    return SEE


def add_cur(update: Update, context: CallbackContext) -> int:
    if update.callback_query: 
        query = update.callback_query
        query.answer()
        if query.data != "top25":
            keyboard = [
                [
                    InlineKeyboardButton("Back", callback_data="back"),
                    InlineKeyboardButton("TOP 25", callback_data="top25"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.edit_message_text(
                text="To add a cryptocurrency, send me its name or ticker", reply_markup=reply_markup)
            return ADD
        else:
            keyboard = [[]]
            lvl1 = 0
            lvl2 = 0
            lvlsize = 3
            was_add = False
            num_buttons = 0
            text = ""
            if not requestData: get_data(query.id, "BTC")
            for item in requestData["data"]:
                if num_buttons > 24:
                    break
                was_add = True
                num_buttons+=1
                line = InlineKeyboardButton(item["symbol"].upper(), callback_data="addOne"+item["symbol"])
                if lvl1 < lvlsize:       
                    keyboard[lvl2].append(line)
                    lvl1 += 1
                else:
                    lvlsize += 1
                    lvl2 += 1
                    lvl1 = 1
                    keyboard.append([])
                    keyboard[lvl2].append(line)

            lineIndex = 0
            if was_add: 
                lineIndex = lvl2+1
                keyboard.append([])
            keyboard[lineIndex].extend(
                [
                    InlineKeyboardButton("Back", callback_data="add"),
                ]
            )
            text="Select a currency to add to your favorites list"
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.edit_message_text(
                text=text, reply_markup=reply_markup
            )
            return SEE

    elif update.message:
        query = update.message
        cur = query.text.upper()
        if len(cur) < 2: 
            text+="I did not find suitable currencies, please specify your request"
            keyboard = [
                [
                    InlineKeyboardButton("Back", callback_data="back"),
                    InlineKeyboardButton("TOP 25", callback_data="top25"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.reply_text(
                text=text, reply_markup=reply_markup
            )
            return ADD
        keyboard = [[]]
        lvl1 = 0
        lvl2 = 0
        was_add = False
        num_buttons = 0
        text = ""
        if not requestData: get_data(query.from_user.id, "BTC")
        for item in requestData["data"]:
            if num_buttons > 19:
                text+="Not all results shown, check your query.\n\n"
                break
            if cur in item["symbol"].upper() or cur in item["name"].upper():
                was_add = True
                num_buttons+=1
                line = InlineKeyboardButton(item["symbol"].upper(), callback_data="addOne"+item["symbol"])
                if lvl1 < 5:            
                    keyboard[lvl2].append(line)
                    lvl1 += 1
                else:
                    lvl2 += 1
                    lvl1 = 1
                    keyboard.append([])
                    keyboard[lvl2].append(line)

        lineIndex = 0
        if was_add: 
            lineIndex = lvl2+1
            keyboard.append([])
        keyboard[lineIndex].extend(
            [
                InlineKeyboardButton("Back", callback_data="back"),
            ]
        )
        if num_buttons == 0: 
            text+="I did not find suitable currencies, please specify your request"
            keyboard = [
                [
                    InlineKeyboardButton("Back", callback_data="back"),
                    InlineKeyboardButton("TOP 25", callback_data="top25"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.reply_text(
                text=text, reply_markup=reply_markup
            )
            return ADD
        text+="Select a currency to add to your favorites list"
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.reply_text(
            text=text, reply_markup=reply_markup
        )
        return SEE

    else: return ADD

def end(update: Update, context: CallbackContext) -> int:

    query = update.message
    keyboard = [
        [
            InlineKeyboardButton("Начать", callback_data="start"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.reply_text(text="See you next time!", reply_markup=reply_markup)
    return ConversationHandler.END

def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    update.message.reply_text('use /start for start talking\nuse /stop for stop talking')

def inlinequery(update: Update, context: CallbackContext) -> None:
    results = []
    """Handle the inline query."""
    query = update.inline_query.query
    print(update._effective_user)
    if query != "" and len(query) < 2: return
    else:
        getDataAnswer = get_data(update.effective_user.id, query)
        if not getDataAnswer: return
        if getDataAnswer["status"] == 200:
            cur_was = []
            for key, value in getDataAnswer["data"].items():
                if cur_was.count(value) < 1:
                    cur_was.append(value)
                    results.append(InlineQueryResultArticle(
                            id=str(uuid4()),
                            title=key,
                            description=value,
                            input_message_content=InputTextMessageContent(value),
                            thumb_url="https://s2.coinmarketcap.com/static/img/coins/128x128/{0}.png".format(iconsDict[key]),
                        ))
            return(update.inline_query.answer(results, cache_time=30))
        else:
            results.append(InlineQueryResultArticle(
                    id=str(uuid4()),
                    title=getDataAnswer["data"],
                    input_message_content=InputTextMessageContent(getDataAnswer["data"]),
                ))
            return(update.inline_query.answer(results))


def main() -> None:
    """Run the bot."""
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start), CallbackQueryHandler(start, pattern='^start$')],
        states={
            FORK: [
                CallbackQueryHandler(show_list, pattern='^see$'),
                CallbackQueryHandler(add_cur, pattern='^add$'),
                CommandHandler("stop", end),
            ],
            SEE: [
                CallbackQueryHandler(end, pattern='^toend$'),
                CallbackQueryHandler(add_cur, pattern='^add$'),
                CallbackQueryHandler(start_over, pattern='^back$'),
                CallbackQueryHandler(show_list, pattern='^dell'),
                CallbackQueryHandler(show_list, pattern='^addOne'),
                CommandHandler("stop", end),
            ],
            ADD: [
                CallbackQueryHandler(end, pattern='^toend$'),
                CallbackQueryHandler(start_over, pattern='^back$'),
                CallbackQueryHandler(add_cur, pattern='^top25$'),
                MessageHandler(Filters.text , add_cur),
                CommandHandler("stop", end),
            ],
            TIMEOUT: [
                CallbackQueryHandler(end),
            ],
        },
        fallbacks=[CommandHandler('start', start)],
        # per_message=True
    )

    dispatcher.add_handler(conv_handler)

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CallbackQueryHandler(start, pattern='^start$'))
    dispatcher.add_handler(CommandHandler("help", help_command))

    dispatcher.add_handler(InlineQueryHandler(inlinequery))

    updater.start_polling()

    updater.idle()


if __name__ == '__main__':
    lastRequestTime = datetime.datetime.now() - datetime.timedelta(minutes=10)
    requestData = ""
    iconsDict = {}
    DB_PATCH = get_script_dir()+'/cprices.db'
    #DB CONNECT
    sqlite_connection = sqlite3.connect(DB_PATCH)
    cursor = sqlite_connection.cursor()
    try:
        cursor.execute("""CREATE TABLE if not exists users
                        (id integer, coinList text, name text, surname text)
                    """)
        sqlite_connection.commit()
    except Exception as e:
        print(e)
    sqlite_connection.close()

    param = sys.argv
    if len(param) > 1: time.sleep(30)
    main()