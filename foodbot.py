import re
from datetime import datetime

import discord
from bson.decimal128 import Decimal128
from pymongo.mongo_client import MongoClient

from config import *

# Set up tasks
intents = discord.Intents.all()
mongo_client = MongoClient(CONNECT_STRING)
db = mongo_client[DATABASE_NAME]
collection = db[COLLECTION_NAME]
credit_collection = db[CREDIT_COLLECTION_NAME]
client = discord.Client(intents=intents)


# Returns all unique names
def getNames():
    return collection.distinct("name")


# Utilizes a private dictionary that is stored in config.py
def getDiscordId(name: str):
    return DISCORD_IDS.get(name.lower())


def nameFromID(id):
    return NAME_IDS.get(id)


# @param name is in format of FirstName LastName (Ex: john doe)
# @param subtotal is in format of a decimal value (Ex: 18.75)
# @param location is a string of Restaurant Name (Ex: Hai Di Lao)
# @param date is a date formated datetime object
# @param tax_rate is a decimal value(Ex: 0.1025) meaning a 10.25% Tax at that location
# @param tip is a decimal value of that persons portion of the tip (Ex : 6.25)
# @param paid is a boolean value of if that person already paid that tab (Default = False)
def createRecord(
    name: str,
    discord_id: str,
    subtotal,
    location: str,
    date: datetime,
    tax_rate: float,
    tip,
    paid: bool = False,
    balance=0,
):
    total = round(round(subtotal, 2) * (1 + tax_rate) + round(tip, 2), 2)

    record = {
        "name": name.lower(),
        "discord_id": discord_id,
        "subtotal": Decimal128(round(subtotal, 2)),
        "location": location.lower(),
        "date": date,
        "tax_rate": Decimal128(tax_rate),
        "tip": Decimal128(round(tip, 2)),
        "total": Decimal128(total),
        "paid": paid,
        "balance": Decimal128(total),
    }
    return record


def insertRecords(records):
    collection.insert_many(records)


@client.event
async def on_ready():
    print("We have logged in as {0.user}".format(client))


def getUnpaidBalances():
    pipeline = [
        {"$match": {"paid": False}},
        {"$group": {"_id": "$name", "balance": {"$sum": "$balance"}}},
    ]
    return collection.aggregate(pipeline)


async def payOffBalance(
    id: str = None, name: str = None, amount: float = None, key_type: str = "id"
):
    key_types = ["id", "name"]
    search = {}

    if key_type not in key_types:
        raise ValueError("Invalid key type. Expected one of: %s" % key_types)

    if key_type == "id":
        search = {"discord_id": id, "paid": False}
    elif key_type == "name":
        search = {"name": name, "paid": False}

    # TODO: Raise error if invalid ID or name
    records = collection.find(search).sort("date", -1)
    for record in records:
        if amount >= float(str(record["balance"])):
            # Update record
            collection.find_one_and_update(
                {"_id": record["_id"]}, {"$set": {"paid": True, "balance": 0}}
            )
            amount -= float(str(record["balance"]))
        elif amount > 0:
            # Partially update some record with the amount they paid off
            sub = Decimal128(str(-amount))
            collection.find_one_and_update(
                {"_id": record["_id"]}, {"$inc": {"balance": sub}}
            )
            amount = 0
            break
    # TODO: Make it so extra amount gets put into Credit Table


async def sendInvoices(channel, author):
    prompt0 = "Time to Send Invoices! \n \
    Please enter the full name of the place y'all ate at:"
    await channel.send(prompt0)
    location = await client.wait_for(
        "message", check=lambda message2: message2.author.id == author.id
    )

    prompt1 = "Please enter the date you ate here (Ex: 03/29/2023):"
    await channel.send(prompt1)
    date_unformated = await client.wait_for(
        "message", check=lambda message2: message2.author.id == author.id
    )

    date = datetime.strptime(date_unformated.content, "%m/%d/%Y").date()

    prompt2 = "Please enter how many people ate:"
    await channel.send(prompt2)
    amount_of_people = await client.wait_for(
        "message", check=lambda message2: message2.author.id == author.id
    )

    prompt3 = "Please enter the total amount of tip:"
    await channel.send(prompt3)
    tip_unsplit = await client.wait_for(
        "message", check=lambda message2: message2.author.id == author.id
    )

    tip = float(tip_unsplit.content) / float(amount_of_people.content)

    prompt4 = "Please enter the tax rate of the location (Ex: 0.1025):"
    await channel.send(prompt4)
    tax_rate = await client.wait_for(
        "message", check=lambda message2: message2.author.id == author.id
    )

    splitPrompt = "Is the total going to be evenly split?"
    await channel.send(splitPrompt)
    split = await client.wait_for(
        "message", check=lambda message2: message2.author.id == author.id
    )

    records = []

    if split.content.lower() == "yes" or split.content.lower() == "y":
        grandTotalPrompt = "What is the grand subtotal?"
        await channel.send(grandTotalPrompt)
        grandTotal = await client.wait_for(
            "message", check=lambda message2: message2.author.id == author.id
        )

        for i in range(int(amount_of_people.content)):
            prompt5 = "Please enter the full name of the person you wish to send the invoice to:"
            await channel.send(prompt5)
            name = await client.wait_for(
                "message", check=lambda message2: message2.author.id == author.id
            )
            records.append(
                createRecord(
                    name.content,
                    str(getDiscordId(name.content)),
                    float(grandTotal.content) / float(amount_of_people.content),
                    location.content,
                    date,
                    float(tax_rate.content),
                    tip,
                    False,
                )
            )

    else:
        for i in range(int(amount_of_people.content)):
            prompt5 = "Please enter the full name of the person you wish to send the invoice to:"
            await channel.send(prompt5)
            name = await client.wait_for(
                "message", check=lambda message2: message2.author.id == author.id
            )

            prompt6 = "Please enter the total amount (Pre-Tax) that person spent \n"
            await channel.send(prompt6)
            subtotal = await client.wait_for(
                "message", check=lambda message2: message2.author.id == author.id
            )

            records.append(
                createRecord(
                    name.content,
                    float(subtotal.content),
                    location.content,
                    date,
                    float(tax_rate.content),
                    tip,
                    False,
                )
            )

    insertRecords(records)
    post_prompt = "Invoices created and added to database!"
    await channel.send(post_prompt)


async def pingBalances(channelID):
    channel = client.get_channel(channelID)
    records = getUnpaidBalances()
    for record in records:
        name = getDiscordId(record["_id"])
        if name == None:
            name = record["_id"]
        else:
            name = "<@" + str(name) + ">"

        await channel.send(name + " owes $" + str((record["balance"])) + " !")


def getCredit(id=None, name=None, key_type="id"):
    key_types = ["id", "name"]
    search = {}

    if key_type not in key_types:
        raise ValueError("Invalid key type. Expected one of: %s" % key_types)

    if key_type == "id":
        search = {"discord_id": str(id)}
    elif key_type == "name":
        search = {"name": name}
    if credit_collection.count_documents(search):
        return credit_collection.find_one(search)["credit"]
    return None


def addCredit(person=None, credit=0.0, key_type="id"):
    key_types = ["id", "name"]
    search = {}

    if key_type not in key_types:
        raise ValueError("Invalid key type. Expected one of: %s" % key_types)

    if key_type == "id":
        search = {"discord_id": person, "name": nameFromID(int(person))}
    elif key_type == "name":
        search = {"discord_id": None, "name": person}
    data = {"$inc": {"credit": Decimal128(str(credit))}}
    credit_collection.update_one(search, data, upsert=True)


async def getIndivdualBalance(author, channel):
    name = nameFromID(author.id)

    if name is None:
        await channel.send(
            "You are not in the default name list. Please contact your banker if you believe this is an accident."
        )
        return

    if collection.count_documents({"paid": False, "name": name}) == 0:
        await channel.send(
            "<@" + str(author.id) + "> You have no outstanding balances!"
        )
        return

    pipeline = [
        {
            "$match": {
                "paid": False,
                "name": name,
            }
        },
        {"$group": {"_id": "$name", "balance": {"$sum": "$balance"}}},
    ]
    records = collection.aggregate(pipeline)
    for record in records:
        await channel.send(
            "<@" + str(author.id) + "> You owe $" + str(record["balance"]) + " !"
        )


async def payoff(message):
    try:
        person = ""
        words = message.content.split(" ")
        if len(words) == 3 and re.match(r"<@[0-9]{18}>", words[2]):
            person = words[2]
            await payOffBalance(
                str(person[2:20]), amount=float(words[1]), key_type="id"
            )

        elif len(words) == 4:
            person = words[2] + " " + words[3]
            await payOffBalance(str(person), amount=float(words[1]), key_type="name")
        await message.channel.send(person + " has paid the bank!")
    except discord.errors.Forbidden:
        pass
    except ValueError:
        await message.channel.send(
            "Error: Please enter a valid amount. Ex: !payoff 10.25"
        )


async def displayIndividualRecords(author, channel):
    records = collection.find({"discord_id": str(author.id)}).sort("date", -1).limit(5)
    for record in records:
        embed = discord.Embed(
            title=record["location"].title(), colour=0x00B0F4, timestamp=datetime.now()
        )
        embed.set_thumbnail(url="https://i.imgur.com/Eib38At.jpg")

        embed.add_field(name="Date", value=record["date"].date(), inline=False)
        embed.add_field(name="Subtotal", value=record["subtotal"], inline=False)
        embed.add_field(name="Tax Rate", value=record["tax_rate"], inline=False)
        embed.add_field(name="Tip", value=record["tip"], inline=False)
        embed.add_field(name="Grand Total", value=record["total"], inline=False)
        embed.add_field(name="Balance", value=record["balance"], inline=True)
        embed.add_field(name="Paid", value=record["paid"], inline=True)

        embed.set_footer(
            text="Food Bot by @gollam", icon_url="https://i.imgur.com/N33XA5A.jpeg"
        )

        await channel.send(embed=embed)


async def credit(message):
    words = message.content.split(" ")
    if words[1] == "balance" and len(words) == 2:
        credit = getCredit(message.author.id)
        msg = ""
        if credit:
            msg = "<@" + str(message.author.id) + "> has " + str(credit) + " in credit!"
        else:
            msg = "<@" + str(message.author.id) + "> has no credit!"

        await message.channel.send(msg)
        return

    if message.author.id == BANKER_ID:
        try:
            if words[1] == "balance" and len(words) == 3:
                credit = getCredit(words[2][2:20])
                msg = (
                    "<@"
                    + str(message.author.id)
                    + "> has "
                    + str(credit)
                    + " in credit!"
                )
                await message.channel.send(msg)
                return

            if words[1] == "add":
                if re.match(r"<@[0-9]{18}>", words[2]):
                    addCredit(words[2][2:20], float(words[3]), key_type="id")
                    await message.channel.send(
                        "Added $" + words[3] + " in credit to " + words[2]
                    )
                else:
                    addCredit(
                        words[2] + " " + words[3], float(words[4]), key_type="name"
                    )
                    await message.channel.send(
                        "Added $"
                        + words[4]
                        + " in credit to "
                        + words[2]
                        + " "
                        + words[3]
                    )
        except:
            await message.channel.send("Error in command")


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith("!payoff") and message.author.id == BANKER_ID:
        await payoff(message)
        return
    if message.content.startswith("!balance"):
        try:
            await getIndivdualBalance(message.author, message.channel)
            return
        except discord.errors.Forbidden:
            pass
    if message.content.startswith("!history"):
        try:
            await displayIndividualRecords(message.author, message.channel)
            return
        except discord.errors.Forbidden:
            pass
    if message.content.startswith("!credit"):
        try:
            await credit(message)
            return
        except discord.errors.Forbidden:
            pass

    # If its a DM
    if not message.guild:
        # If its the Banker
        if message.author.id == BANKER_ID:
            try:
                if message.content == "totals":
                    await pingBalances(CHANNEL_ID)

                if message.content == "invoices":
                    # Eventually make a function that will allow me to either
                    # 1. Select a previous name
                    # 2. Add a new name

                    await sendInvoices(message.channel, message.author)
                    await pingBalances(CHANNEL_ID)
            except discord.errors.Forbidden:
                pass
        # DM from a user that is not the banker.
        else:
            pass


client.run(BOT_SECRET)
