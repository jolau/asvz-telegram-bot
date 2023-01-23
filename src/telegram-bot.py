#!/home/pi/asvz-telegram-bot/src/.venv/bin/python3

import argparse
import logging
import multiprocessing
import re
import threading
import time

import selenium
from selenium import webdriver
from pyvirtualdisplay import Display
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from telegram import Update, MessageEntity
from telegram.constants import MessageEntityType
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import asvz_bot

#chromedriver = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="I'm a bot, please talk to me!"
    )


async def enroll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f'Hello {update.effective_user.first_name}, I will enroll you now!')
    logging.info(update.message.text)

    # Extract the URL from the message text
    url = re.search(r'https://schalter\.asvz\.ch/tn/lessons/(\d+)', update.message.text)

    if url:
        # If a URL was found, extract the number from it and enroll in the lecture
        lesson_id = url.group(1)
        lesson_url = "{}/tn/lessons/{}".format(asvz_bot.LESSON_BASE_URL, lesson_id)
        logging_queue = multiprocessing.Queue()
        enroller = asvz_bot.AsvzEnroller('/usr/lib/chromium-browser/chromedriver', lesson_url, creds, logging_queue)
        #enroller.enroll()
        t = threading.Thread(target=enroller.enroll)
        t.start()

        # Wait for the enroller to finish and send the log messages to the user
        while t.is_alive() or not logging_queue.empty():
            logging.info("Waiting for enroller to finish...")
            while not logging_queue.empty():
                log_record = logging_queue.get()
                await update.message.reply_text(log_record.getMessage())
            time.sleep(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-org",
        "--organisation",
        choices=list(asvz_bot.ORGANISATIONS.keys()),
        help="Name of your organisation.",
    )
    parser.add_argument("-u", "--username", type=str, help="Organisation username")
    parser.add_argument("-p", "--password", type=str, help="Organisation password")
    parser.add_argument(
        "--save-credentials",
        default=False,
        action="store_true",
        help="Store your login credentials locally and reused them on the next run",
    )
    parser.add_argument("-t", "--token", type=str, help="Telegram bot token")

    args = parser.parse_args()

    # Create an instance of the ASVZBot class and log in to your account
    creds = None
    try:
        creds = asvz_bot.CredentialsManager(
            args.organisation, args.username, args.password, args.save_credentials
        ).get()
    except asvz_bot.AsvzBotException as e:
        logging.error(e)
        exit(1)

    # Create the bot
    app = ApplicationBuilder().token(args.token).build()

    start_handler = CommandHandler('start', start)
    enroll_handler = MessageHandler(filters.TEXT
                                    & (filters.Entity(MessageEntityType.URL)
                                       | filters.Entity(MessageEntityType.URL))
                                    & (~filters.COMMAND), enroll)

    app.add_handler(start_handler)
    app.add_handler(enroll_handler)

    app.run_polling()


