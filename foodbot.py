import discord

from mongo_access import *

# Set up tasks
intents = discord.Intents.all()
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print("We have logged in as {0.user}".format(client))


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

    date = datetime.strptime(date_unformated.content, "%m/%d/%Y")

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
                    getNameRecord(name.content, key_type="name")["discord_id"],
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
                    getNameRecord(name.content, key_type="name")["discord_id"],
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
        name = getNameRecord(record["_id"], key_type="name")
        if name:
            name = "<@" + name["discord_id"] + ">"
        else:
            name = record["_id"]

        await channel.send(name + " owes $" + str((record["balance"])) + " !")


async def displayIndivdualBalance(channel, person, key_type: str = "id"):
    key_types = ["id", "name"]
    if key_type not in key_types:
        raise ValueError("Invalid key type. Expected one of: %s" % key_types)
    displayName = ""
    name_record = getNameRecord(person, key_type)
    if name_record:
        displayName = "<@" + name_record["discord_id"] + ">"
    else:
        displayName = person

    balance_record = getBalanceRecord(person, key_type)

    if balance_record:
        await channel.send(
            displayName + " You owe $" + str(balance_record["balance"]) + "!"
        )
    else:
        await channel.send(displayName + " You have no outstanding balances!")


async def payoff(message):
    try:
        person = ""
        key_type = "id"
        name = ""
        words = message.content.split(" ")
        if len(words) == 3 and re.match(r"<@[0-9]{18}>", words[2]):
            person = words[2][2:20]
            name = "<@" + person + ">"

        elif len(words) == 4:
            person = words[2] + " " + words[3]
            key_type = "name"
            name = person
        else:
            await message.channel.send(
                "Error: Please enter the payoff command. Ex: !payoff 10.25 @gollam"
            )
            return
        payOffBalance(person, Decimal128(words[1]), key_type)
        await message.channel.send(name + " has paid the bank!")
    except discord.errors.Forbidden:
        pass
    except ValueError:
        await message.channel.send(
            "Error: Please enter a valid amount. Ex: !payoff 10.25"
        )


RED_HEX = 0xFF0000
GREEN_HEX = 0x00FF00


async def displayIndividualHistory(author, channel):

    records = (
        invoice_collection.find({"discord_id": str(author.id)})
        .sort("date", -1)
        .limit(5)
    )
    hex_color = RED_HEX
    for record in records:
        if record["paid"]:
            hex_color = GREEN_HEX

        embed = discord.Embed(
            title=record["location"].title(), colour=hex_color, timestamp=datetime.now()
        )
        embed.set_thumbnail(url="https://i.imgur.com/Eib38At.jpg")

        embed.add_field(name="Date", value=record["date"].date(), inline=True)
        embed.add_field(name="Subtotal", value=record["subtotal"], inline=True)
        embed.add_field(name="Tax Rate", value=record["tax_rate"], inline=True)
        embed.add_field(name="Tip", value=record["tip"], inline=True)
        embed.add_field(name="Grand Total", value=record["total"], inline=True)
        embed.add_field(name="Balance", value=record["balance"], inline=True)
        embed.add_field(name="Paid", value=record["paid"], inline=True)

        embed.set_footer(
            text="Food Bot by @gollam", icon_url="https://i.imgur.com/N33XA5A.jpeg"
        )

        await channel.send(embed=embed)


async def credit(message):
    words = message.content.split(" ")
    if message.author.id == BANKER_ID:
        try:
            if words[1] == "balance" and len(words) == 3:
                credit = getCredit(words[2][2:20], key_type="id")
                msg = words[2] + " has " + str(credit) + " in credit!"
                await message.channel.send(msg)
                return

            if words[1] == "add":
                if re.match(r"<@[0-9]{18}>", words[3]):
                    addCredit(words[3][2:20], Decimal128(words[2]), key_type="id")
                    await message.channel.send(
                        "Added $" + words[2] + " in credit to " + words[3]
                    )
                else:
                    addCredit(
                        words[3] + " " + words[4], Decimal128(words[2]), key_type="name"
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

    if words[1] == "balance" and len(words) == 2:
        credit = getCredit(message.author.id, key_type="id")
        msg = ""
        if credit:
            msg = "<@" + str(message.author.id) + "> has " + str(credit) + " in credit!"
        else:
            msg = "<@" + str(message.author.id) + "> has no credit!"

        await message.channel.send(msg)
        return
    if words[1] == "use" and len(words) == 3:
        try:
            amount = words[2]
            credit = float(str(getCredit(message.author.id, key_type="id")))
            if credit:
                if credit >= float(amount):
                    payOffBalance(message.author.id, Decimal128(amount), key_type="id")
                    addCredit(
                        message.author.id, Decimal128("-" + amount), key_type="id"
                    )
                    await message.channel.send(
                        "<@" + str(message.author.id) + "> has paid the bank!"
                    )
                else:
                    await message.channel.send(
                        "Error: You cannot use more credit than you have!"
                    )
            else:
                await message.channel.send("Error: You do not have any credit!")

        except ValueError:
            await message.channel.send("Error reading amount, please try again!")
        except:
            await message.channel.send("Error in command, please try again!")


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith("!payoff") and message.author.id == BANKER_ID:
        await payoff(message)
        return
    if message.content == "!balance":
        try:
            await displayIndivdualBalance(
                message.channel, str(message.author.id), key_type="id"
            )
            return
        except discord.errors.Forbidden:
            pass
    if message.content.startswith("!history"):
        try:
            await displayIndividualHistory(message.author, message.channel)
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
                    # await pingBalances(CHANNEL_ID)
            except discord.errors.Forbidden:
                pass
        # DM from a user that is not the banker.
        else:
            pass


client.run(BOT_SECRET)
