from time import time
from sys import executable
from os import execl as osexecl
from asyncio import create_subprocess_exec, gather
from uuid import uuid4
from html import escape

from signal import signal, SIGINT
from aiofiles.os import path as aiopath, remove as aioremove
from aiofiles import open as aiopen
from psutil import disk_usage, cpu_percent, virtual_memory, boot_time
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.filters import command, regex

from bot import bot, config_dict, user_data, botStartTime, LOGGER, Interval, DATABASE_URL, QbInterval, scheduler, bot_name
from .helper.ext_utils.files_utils import start_cleanup, clean_all, exit_clean_up
from .helper.ext_utils.bot_utils import get_readable_file_size, get_readable_time, sync_to_async, set_commands, new_thread, new_task
from .helper.ext_utils.db_handler import DbManager
from .helper.telegram_helper.bot_commands import BotCommands
from .helper.telegram_helper.message_utils import sendMessage, editMessage, sendFile, deleteMessage, one_minute_del, five_minute_del
from .helper.telegram_helper.filters import CustomFilters
from .helper.telegram_helper.button_build import ButtonMaker
from .helper.listeners.aria2_listener import start_aria2_listener
from .modules import authorize, cancel_mirror, mirror_leech, status, torrent_search, ytdlp, shell, executor, users_settings, torrent_select, bot_settings, speedtest, images, mediainfo, broadcast, count, delete, list, clone  # noqa: F401


if config_dict['GDRIVE_ID']:
    help_string = f'''<b>NOTE: Try each command without any arguments to see more details.</b>

<blockquote expandable>/{BotCommands.MirrorCommand[0]} - Start mirroring to Google Drive.
/{BotCommands.LeechCommand[0]} - Start leeching to Telegram.
/{BotCommands.YtdlCommand[0]} - Mirror links supported by yt-dlp.
/{BotCommands.YtdlLeechCommand[0]} - Leech links supported by yt-dlp.
/{BotCommands.CloneCommand[0]} - Copy files/folders to Google Drive.
/{BotCommands.CountCommand} - Count files/folders in Google Drive.
/{BotCommands.ListCommand} - Search in Google Drive(s).
/{BotCommands.UserSetCommand} - Open the settings panel.
/{BotCommands.MediaInfoCommand} - View MediaInfo from a file or link.
/{BotCommands.StopAllCommand[0]} - Cancel all active tasks.
/{BotCommands.SearchCommand} - Search for torrents using API or plugins.
/{BotCommands.StatusCommand[0]} - Show the status of all downloads.
/{BotCommands.StatsCommand[0]} - Display machine stats hosting the bot.</blockquote>
'''
else:
    help_string = f'''<b>NOTE: Try each command without any arguments to see more details.</b>

<blockquote expandable>/{BotCommands.LeechCommand[0]} - Start leeching to Telegram.
/{BotCommands.YtdlLeechCommand[0]} - Leech links supported by yt-dlp.
/{BotCommands.UserSetCommand} - Open the settings panel.
/{BotCommands.MediaInfoCommand} - View MediaInfo from a file or link.
/{BotCommands.StopAllCommand[0]} - Cancel all active tasks.
/{BotCommands.SearchCommand} - Search for torrents using API or plugins.
/{BotCommands.StatusCommand[0]} - Show the status of all downloads.
/{BotCommands.StatsCommand[0]} - Display machine stats hosting the bot.</blockquote>
'''


@new_thread
async def stats(_, message):
    total, used, free, disk = disk_usage('/')
    memory = virtual_memory()
    currentTime = get_readable_time(time() - botStartTime)
    osUptime = get_readable_time(time() - boot_time())
    cpuUsage = cpu_percent(interval=0.5)
    limit_mapping = {
        'Torrent'  : config_dict.get('TORRENT_LIMIT',  '∞'),
        'Gdrive'   : config_dict.get('GDRIVE_LIMIT',   '∞'),
        'Ytdlp'    : config_dict.get('YTDLP_LIMIT',    '∞'),
        'Direct'   : config_dict.get('DIRECT_LIMIT',   '∞'),
        'Leech'    : config_dict.get('LEECH_LIMIT',    '∞'),
        'Clone'    : config_dict.get('CLONE_LIMIT',    '∞'),
        'Mega'     : config_dict.get('MEGA_LIMIT',     '∞'),
        'User task': config_dict.get('USER_MAX_TASKS', '∞')}
    system_info = f'<blockquote><code>• Bot uptime :</code> {currentTime}\n'\
        f'<code>🤖 Sys uptime :</code> {osUptime}\n'\
        f'<code>🖥️ CPU usage  :</code> {cpuUsage}%\n'\
        f'<code>🧨 RAM usage  :</code> {memory.percent}%\n'\
        f'<code>💿 Disk usage :</code> {disk}%\n'\
        f'<code>🪫 Free space :</code> {get_readable_file_size(free)}\n'\
        f'<code>💯 Total space:</code> {get_readable_file_size(total)}</blockquote>\n\n'
            
    limitations = '<blockquote><b>LIMITATIONS</b></blockquote>\n\n'
    
    for k, v in limit_mapping.items():
        if v == '':
            v = '∞'
        elif k != 'User task':
            v = f'{v}GB/Link'
        else:
            v = f'{v} Tasks/user'
        limitations += f'<code>• {k:<11}:</code> {v}\n'

    stats = system_info + limitations
    reply_message = await sendMessage(message, stats, photo='Random')
    await deleteMessage(message)
    await one_minute_del(reply_message)

@new_thread
async def start(client, message):
    if len(message.command) > 1 and message.command[1] == "private":
        await deleteMessage(message)
    elif len(message.command) > 1 and len(message.command[1]) == 36:
        userid = message.from_user.id
        input_token = message.command[1]
        if DATABASE_URL:
            stored_token = await DbManager().get_user_token(userid)
            if stored_token is None:
                return await sendMessage(message, '<b>This token is not for you!</b>\n\nPlease generate your own.')
            if input_token != stored_token:
                return await sendMessage(message, 'Invalid token.\n\nPlease generate a new one.')
        if userid not in user_data:
            return await sendMessage(message, 'This token is not yours!\n\nKindly generate your own.')
        data = user_data[userid]
        if 'token' not in data or data['token'] != input_token:
            return await sendMessage(message, '<b>This token has already been used!</b>\n\nPlease get a new one.')
        token = str(uuid4())
        token_time = time()
        data['token'] = token
        data['time'] = token_time
        user_data[userid].update(data)
        if DATABASE_URL:
            await DbManager().update_user_tdata(userid, token, token_time)
        msg = 'Your token has been successfully generated!\n\n'
        msg += f'It will be valid for {get_readable_time(int(config_dict["TOKEN_TIMEOUT"]), True)}'
        return await sendMessage(message, msg)
    elif await CustomFilters.authorized(client, message):
        help_command = f"/{BotCommands.HelpCommand}"
        start_string = f'<blockquote>This bot can mirror all your links|files|torrents to Google Drive or any rclone cloud or to telegram.\n<b>Type {help_command} to get a list of available commands</b></blockquote>'
        await sendMessage(message, start_string, photo='Random')
    else:
        await sendMessage(message, 'You are not a authorized user!\n Yᴏᴜ Cᴀɴ Usᴇ Mᴇ ᴀᴛ \n <a href="https://t.me/TELLYCLOUD_Bots"><b>☬𝐓𝐄𝐋𝐋𝐘𝐂𝐋𝐎𝐔𝐃 𝐁𝐎𝐓𝐒™☬</b></a> ', photo='Random')
    await DbManager().update_pm_users(message.from_user.id)


async def restart(client, message):
    restart_message = await sendMessage(message, '<blockquote>Restarting...</blockquote>')
    if scheduler.running:
        scheduler.shutdown(wait=False)
    for interval in [QbInterval, Interval]:
        if interval:
            interval[0].cancel()
    await sync_to_async(clean_all)
    proc1 = await create_subprocess_exec('pkill', '-9', '-f', '-e', 'gunicorn|xria|xnox|xtra|xone')
    proc2 = await create_subprocess_exec('python3', 'update.py')
    await gather(proc1.wait(), proc2.wait())
    async with aiopen(".restartmsg", "w") as f:
        await f.write(f"{restart_message.chat.id}\n{restart_message.id}\n")
    osexecl(executable, executable, "-m", "bot")


async def ping(_, message):
    start_time = int(round(time() * 1000))
    reply = await sendMessage(message, '<blockquote>Starting ping...</blockquote>')
    end_time = int(round(time() * 1000))
    value=(end_time - start_time)
    await editMessage(reply, f'{value} ms.')


@new_task
async def AeonCallback(_, query):
    message = query.message
    user_id = query.from_user.id
    data = query.data.split()
    if user_id != int(data[1]):
        return await query.answer(text="This message not your's!", show_alert=True)
    elif data[2] == "logdisplay":
        await query.answer()
        async with aiopen('log.txt', 'r') as f:
            logFileLines = (await f.read()).splitlines()
        def parseline(line):
            try:
                return "[" + line.split('] [', 1)[1]
            except IndexError:
                return line
        ind, Loglines = 1, ''
        try:
            while len(Loglines) <= 3500:
                Loglines = parseline(logFileLines[-ind]) + '\n' + Loglines
                if ind == len(logFileLines): 
                    break
                ind += 1
            startLine = "<pre language='python'>"
            endLine = "</pre>"
            btn = ButtonMaker()
            btn.callback('Close', f'aeon {user_id} close')
            reply_message = await sendMessage(message, startLine + escape(Loglines) + endLine, btn.column(1))
            await query.edit_message_reply_markup(None)
            await deleteMessage(message)
            await five_minute_del(reply_message)
        except Exception as err:
            LOGGER.error(f"TG Log Display : {str(err)}")
    elif data[2] == "private":
        await query.answer(url=f"https://t.me/{bot_name}?start=private")
    else:
        await query.answer()
        await deleteMessage(message)


@new_task
async def log(_, message):
    buttons = ButtonMaker()
    buttons.callback('Log display', f'aeon {message.from_user.id} logdisplay')
    reply_message = await sendFile(message, 'log.txt', buttons=buttons.column(1))
    await deleteMessage(message)
    await five_minute_del(reply_message)


@new_task
async def bot_help(client, message):
    reply_message = await sendMessage(message, help_string)
    await deleteMessage(message)
    await one_minute_del(reply_message)


async def restart_notification():
    if await aiopath.isfile(".restartmsg"):
        with open(".restartmsg") as f:
            chat_id, msg_id = map(int, f)
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text='<blockquote> ▂▃▅▇█▓▒░ BOT STARTED ░▒▓█▇▅▃▂</blockquote>')
        except Exception:
            pass
        await aioremove(".restartmsg")


async def main():
    await gather(start_cleanup(), torrent_search.initiate_search_tools(), restart_notification(), set_commands(bot))
    await sync_to_async(start_aria2_listener, wait=False)
    bot.add_handler(MessageHandler(start, filters=command(BotCommands.StartCommand)))
    bot.add_handler(MessageHandler(log, filters=command(BotCommands.LogCommand) & CustomFilters.sudo))
    bot.add_handler(MessageHandler(restart, filters=command(BotCommands.RestartCommand) & CustomFilters.sudo))
    bot.add_handler(MessageHandler(ping, filters=command(BotCommands.PingCommand) & CustomFilters.authorized))
    bot.add_handler(MessageHandler(bot_help, filters=command(BotCommands.HelpCommand) & CustomFilters.authorized))
    bot.add_handler(MessageHandler(stats, filters=command(BotCommands.StatsCommand) & CustomFilters.authorized))
    bot.add_handler(CallbackQueryHandler(AeonCallback, filters=regex(r'^aeon')))
    LOGGER.info("Bot Started!")
    signal(SIGINT, exit_clean_up)

bot.loop.run_until_complete(main())
bot.loop.run_forever()
