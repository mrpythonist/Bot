import logging
import telebot
from telebot.types import Message, KeyboardButton, ReplyKeyboardMarkup
from telebot import types
from Google import Create_Service
from datetime import date, datetime
import pytz

est = pytz.timezone('US/Eastern')

CLIENT_SECRET_FILE = 'client_secret.json'
API_NAME = 'sheets'
API_VERSION = 'v4'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

service = Create_Service(CLIENT_SECRET_FILE, API_NAME, API_VERSION, SCOPES)

spreadsheet_id = '1d7mW5jYBcDhY9d5IRW7OldTOQgbdmF96KUgj6X-tGfQ'
mySpreadsheets = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()

worksheet_name = 'AttendanceSheet!'
cell_range_insert = 'A2'

worksheet_name_shift = 'ShiftSheet!'
cell_range_insert_shift = 'A2'

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up Telegram API
token = "6217418979:AAEgq6s5xKs59q1SuePeOPxs6gPsYbbYkQM"
bot = telebot.TeleBot(token)

# Set up breaks, queued users, and shift start dictionaries
breaks = {}
queued_users = []
shift_starts = {}
shift_durations = {}

# Set up break policy and shift length
break_policy = 2


# Define start message command handler
@bot.message_handler(commands=['start'])
def start(message: Message):
    user_id = message.from_user.first_name
    bot.reply_to(message, f"Welcome! {user_id}. Please use following commands:\n/start_shift -  To start the shift.\n/end_shift - To end the shift.\n/start_break - To start the break.\n/end_break - To end the break.")

# Define start break command handler
@bot.message_handler(commands=['start_break'])
def start_break(message: Message):
    user_id = message.from_user.id
    if user_id not in shift_starts:
        bot.reply_to(message, f"Hi {message.from_user.first_name}! You cannot start a break before starting your shift.")
    elif user_id in breaks:
        bot.reply_to(message, f"Hi {message.from_user.first_name}! You are already on break.")
    else:
        if len(breaks) < break_policy:
            breaks[user_id] = datetime.now(est)
            bot.reply_to(message, f"Hi {message.from_user.first_name}! You have started your break. You can end your break by /end_break")

        else:
            queued_users.append(user_id)
            bot.reply_to(message, f"Hi {message.from_user.first_name}! There are already 2 employees on break. You have been added to the queue. Your number is {len(queued_users)}")

# Define end break command handler
@bot.message_handler(commands=['end_break'])
def end_break(message: Message):
    user_id = message.from_user.id
    if user_id not in shift_starts:
        bot.reply_to(message, f"Hi {message.from_user.first_name}! You cannot end a break before starting your shift.")
    elif user_id in breaks:
        start_time = breaks.pop(user_id)
        elapsed_time = datetime.now(est) - start_time
        bot.reply_to(message, f"Hi {message.from_user.first_name}! You have ended your break. You were on break for {elapsed_time.seconds//60} minutes.")
        now = datetime.now(est)
        current = now.strftime("%H:%M:%S")
        currentDate = now.strftime("%m/%d/%Y")
        start = start_time.strftime("%H:%M:%S")
        values = ([currentDate, f"{message.from_user.first_name} {message.from_user.last_name}", message.from_user.username, message.from_user.id, start, current],)
        value_range_body = {'values': values}
        service.spreadsheets().values().append(spreadsheetId=spreadsheet_id,valueInputOption='USER_ENTERED',range=worksheet_name + cell_range_insert,body=value_range_body).execute()
        if queued_users:
            next_user_id = queued_users.pop(0)
            bot.send_message(message.chat.id, f"{bot.get_chat_member(next_user_id, next_user_id).user.first_name} {bot.get_chat_member(next_user_id, next_user_id).user.last_name},  @{bot.get_chat_member(next_user_id, next_user_id).user.username}, you may now take a break.")
            telebot.logger.info(f"Sent message to {next_user_id}")
            telebot.apihelper.timeout = 60
            bot.send_message(message.chat.id, f"Reply /start_break. You have one minute.")
            bot.register_next_step_handler_by_chat_id(next_user_id, check_reply)
    else:
        bot.reply_to(message, f"Hi {message.from_user.first_name}! You are not on break.")

# Define check reply function
def check_reply(message: Message):
    user_id = message.chat.id
    if user_id in queued_users:
        queued_users.remove(user_id)
        if message.text == "/start_break":
            start_break(message)
        else:
            bot.send_message(user_id, "Invalid command.")
        if queued_users:
            next_user_id = queued_users.pop(0)
            message = f"Hi {bot.get_chat_member(next_user_id, next_user_id).user.first_name}! It is your turn for a break. Reply with /start_break to start."
            bot.send_message(next_user_id, message)
            telebot.logger.info(f"Sent message to {next_user_id}")
            telebot.apihelper.timeout = 60
            bot.send_message(next_user_id, "You have one minute to reply.")
            bot.register_next_step_handler_by_chat_id(next_user_id, check_reply)
    else:
        bot.send_message(user_id, f"Hi {message.from_user.first_name}! You are no longer in the queue. Your break has been started. You can end your break by /end_break")
        start_break(message)

# Define start shift command handler
@bot.message_handler(commands=['start_shift'])
def start_shift(message: Message):
    user_id = message.from_user.id
    if user_id in shift_starts:
        bot.reply_to(message, f"Hi {message.from_user.first_name}! You have already started your shift.")
    else:
        shift_starts[user_id] = datetime.now(est)
        bot.reply_to(message, f"Hi {message.from_user.first_name}! You have started your shift.")

@bot.message_handler(commands=['end_shift'])
def end_shift(message: Message):
    user_id = message.from_user.id
    if user_id not in shift_starts:
        bot.reply_to(message, f"Hi {message.from_user.first_name}! You have not started your shift yet.")
    else:
        start_time = shift_starts.pop(user_id)
        elapsed_time = datetime.now(est) - start_time
        shift_durations[user_id] = elapsed_time
        total_shift_time = sum([t.seconds for t in shift_durations.values()])
        bot.reply_to(message, f"Hi {message.from_user.first_name}! You have ended your shift. Total shift time is {total_shift_time//3600} hours and {(total_shift_time%3600)//60} minutes.")
        now = datetime.now(est)
        current = now.strftime("%H:%M:%S")
        currentDate = now.strftime("%m/%d/%Y")
        start = start_time.strftime("%H:%M:%S")
        values = ([currentDate, f"{message.from_user.first_name} {message.from_user.last_name}", message.from_user.username, message.from_user.id, start, current],)
        value_range_body = {'values': values}
        service.spreadsheets().values().append(spreadsheetId=spreadsheet_id,valueInputOption='USER_ENTERED',range=worksheet_name_shift + cell_range_insert_shift,body=value_range_body).execute()


print("Bot is running")
bot.polling()