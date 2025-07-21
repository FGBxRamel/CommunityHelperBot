import asyncio
import configparser as cp
import pkgutil
from datetime import date
from functools import partial
from time import mktime, strftime, strptime, time

import interactions as i

import classes.database as db
from classes.voting import Voting

db.setup()

with open('config.ini', 'r') as config_file:
    config = cp.ConfigParser()
    config.read_file(config_file)
    TOKEN = config.get('General', 'token')
    SERVER_IDS = config.get('General', 'servers').split(',')
    offer_channel_id = config.getint('Offer', 'offer_channel')
    voting_channel_id = config.getint('Voting', 'voting_channel')
    vacation_channel_id = config.getint('Vacation', 'guild_channel')


bot = i.Client(
    token=TOKEN, sync_ext=True,
    intents=i.Intents.DEFAULT | i.Intents.GUILD_MEMBERS)

scope_ids = SERVER_IDS
run = False

# NOTE Wichtel feature won't be supported anymore; it's there (docs folder), but without support
bot.load_extension("interactions.ext.sentry",
                   token=config.get("Sentry", "dsn"),
                   environment=config.get(
                       "Sentry", "environment", fallback="production")
                   )
bot.load_extension("interactions.ext.jurigged")
extension_names = [m.name for m in pkgutil.iter_modules(
    ["cmds"], prefix="cmds.")]
for extension in extension_names:
    bot.load_extension(extension)
votings_timer_started: set = set()


async def automatic_delete(oneshot: bool = False) -> None:
    if not oneshot:
        asyncio.get_running_loop().call_later(86400, run_delete)
    current_time = time()

    async def clean_offers(current_time):
        offer_channel: i.GuildText = await bot.fetch_channel(offer_channel_id)
        if offer_channel is None:
            print("The offer channel has not been found! Please check the config!")
            return
        offers = db.get_data(
            "offers", attribute="deadline, message_id, offer_id, user_id", fetch_all=True)
        for deadline, message_id, offer_id, user_id in offers:
            if deadline <= current_time:
                try:
                    message = await offer_channel.fetch_message(message_id)
                    if message is not None:
                        await message.delete()
                except TypeError:
                    continue
                db.delete_data("offers", {"offer_id": offer_id})
                offer_count = db.get_data("users", {"user_id": user_id})[1]
                db.update_data("users", "offers_count", offer_count - 1, {
                    "user_id": user_id})

    async def clean_votings(current_time):
        votings = db.get_data(
            "votings", attribute="voting_id", fetch_all=True)
        for voting_data in votings:
            voting_id = voting_data[0]
            voting = Voting(voting_id, bot)
            if voting.deadline <= int(current_time):
                await voting.close()

    async def clean_vactions():
        vacations = db.get_data(
            "vacations", attribute="ID, end_date, message_id", fetch_all=True)
        for id, end_date, message_id in vacations:
            current_date = date.today()
            end_date = date.fromtimestamp(end_date)
            delta = end_date - current_date
            if delta.days <= 0:
                vacation_channel = await bot.fetch_channel(vacation_channel_id)
                if vacation_channel is None:
                    print(
                        "The vacation channel has not been found! Please check the config!")
                    return
                try:
                    message = await vacation_channel.fetch_message(message_id)
                    if message is not None:
                        await message.delete()
                except TypeError:
                    continue
                db.delete_data("vacations", {"ID": id})

    await clean_offers(current_time)
    await clean_votings(current_time)
    await clean_vactions()


def run_delete(oneshot: bool = False):
    asyncio.get_running_loop().create_task(automatic_delete(oneshot=oneshot))


# Make task that checks the votings table for new votings to start a delete timer
# Go trough all the votings
# Call asyncio.get_running_loop().call_later(wait_time - (localtime - create time), run_delete, oneshot=True)
# Add voting ID to list so there's no duplicate timers
# The +2 on the wait time is to mitigate a problem with the computer being too fast
async def check_votings():
    while True:
        votings = db.get_data(
            "votings", attribute="voting_id", fetch_all=True)
        for voting_data in votings:
            voting = Voting(voting_data[0], bot)
            if voting.id not in votings_timer_started:
                asyncio.get_running_loop().call_later(
                    voting.wait_time - (time() - voting.create_time) + 2, partial(run_delete, oneshot=True))
                votings_timer_started.add(voting.id)
        await asyncio.sleep(30)


@i.listen()
async def on_ready():
    print("Bot is ready!")
    global run
    if not run:
        wait_time = mktime(strptime(strftime("%d.%m.%Y") +
                           " 23:59", "%d.%m.%Y %H:%M")) - time()
        asyncio.get_running_loop().call_later(wait_time, run_delete)
        asyncio.get_running_loop().create_task(check_votings())
        run = True


@i.slash_command(
    name="test",
    description="A test command to test stuff.",
)
async def test(ctx: i.SlashContext):
    await ctx.send("Test worked!")

bot.start()
