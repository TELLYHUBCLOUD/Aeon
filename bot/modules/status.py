from time import time
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.filters import command, regex
from psutil import disk_usage

from bot import status_reply_dict_lock, download_dict, download_dict_lock, botStartTime, Interval, bot
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.message_utils import sendMessage, deleteMessage, one_minute_del, sendStatusMessage, update_all_messages
from bot.helper.ext_utils.bot_utils import get_readable_file_size, get_readable_time, turn_page, setInterval, new_task

@new_task
async def mirror_status(_, message):
    async with download_dict_lock:
        count = len(download_dict)

    if count == 0:
        currentTime = get_readable_time(time() - botStartTime)
        free = get_readable_file_size(disk_usage('/usr/src/app/downloads/').free)
        msg = '<blockquote>◥꧁ད 𝐔𝐧𝐢𝐧𝐬𝐭𝐚𝐥𝐥 𝐓𝐞𝐥𝐞𝐠𝐫𝐚𝐦! 𝐚𝐧𝐝 𝐄𝐧𝐣𝐨𝐲 𝐟𝐨𝐫 𝐋𝐢𝐟𝐞!! ཌ꧂◤</blockquote>\n'
        msg += f"\n<blockquote><b>• Bot uptime</b>: {currentTime}"
        msg += f"\n<b>• Free disk space</b>: {free}</blockquote>"

        reply_message = await sendMessage(message, msg)
        await deleteMessage(message)
        await one_minute_del(reply_message)
    else:
        await sendStatusMessage(message)
        await deleteMessage(message)
        async with status_reply_dict_lock:
            if Interval:
                Interval[0].cancel()
                Interval.clear()
                Interval.append(setInterval(1, update_all_messages))


@new_task
async def status_pages(_, query):
    await query.answer()
    data = query.data.split()
    if data[1] == "ref":
        await update_all_messages(True)
    else:
        await turn_page(data)


bot.add_handler(MessageHandler(mirror_status, filters=command(BotCommands.StatusCommand) & CustomFilters.authorized))
bot.add_handler(CallbackQueryHandler(status_pages, filters=regex("^status")))
