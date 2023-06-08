import pymongo
import discord
from datetime import datetime
from config import *
from pymongo.mongo_client import MongoClient

# Set up tasks
intents = discord.Intents.default()
intents.members = True
mongo_client = pymongo.MongoClient(CONNECT_STRING)
db = mongo_client[DATABASE_NAME]
collection = db[COLLECTION_NAME]
client = discord.Client(intents=intents)

# Returns all unique names
def getNames():
    return collection.distinct('name')

# Utilizes a private dictionary that is stored in config.py
def getDiscordId(name : str):
    return DISCORD_IDS.get(name.lower())

# @param name is in format of FirstName LastName (Ex: john doe)
# @param amount is in format of a decimal value (Ex: 18.75)
# @param location is a string of Restaurant Name (Ex: Hai Di Lao)
# @param date is a date formated datetime object
# @param tax_rate is a decimal value(Ex: 0.1025) meaning a 10.25% Tax at that location
# @param tip is a decimal value of that persons portion of the tip (Ex : 6.25)
# @param paid is a boolean value of if that person already paid that tab (Default = False)
def createRecord(name : str, amount : float, location : str, date : datetime, tax_rate : float, tip : float, paid : bool = False):
    total = round(round(amount, 2) * (1 + tax_rate) + round(tip, 2) , 2)
    
    record = {  'name': name.lower(),
                'amount': round(amount,2),
                'location': location.lower(),
                'date': date,
                'tax_rate': tax_rate,
                'tip': round(tip, 2) ,
                'total': total,
                'paid': paid
            }   
    return record

def insertRecords(records):
    collection.insert_many(records)
    
@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))
    
def getUnpaidBalances():
    collection.find({'paid' : False})
    # Sum up balances per person

@client.event
async def on_message(message):
    if message.author == client.user :
        return
    # If its a DM
    if not message.guild:
        # If its the Banker
        if message.author == BANKER_ID:
            try:
                if message.content == "invoices":
                    # Eventually make a function that will allow me to either 
                    # 1. Select a previous name
                    # 2. Add a new name

                    prompt0 =  "Time to Send Invoices! \n \
                    Please enter the full name of the place y'all ate at:"
                    await message.channel.send(prompt0)
                    location = await client.wait_for('message', check=lambda message: message.author == ctx.author)

                    prompt1 = "Please enter the date you ate here (Ex: 03/29/2023):"
                    await message.channel.send(prompt1)
                    date_unformated = await client.wait_for('message', check=lambda message: message.author == ctx.author)

                    date = datetime.strptime(date_unformated, "%m/%d/%Y")

                    prompt2 = "Please enter how many people ate:"
                    await message.channel.send(prompt2)
                    amount_of_people = await client.wait_for('message', check=lambda message: message.author == ctx.author)
                    
                    prompt3 = "Please enter the total amount of tip:"
                    await message.channel.send(prompt3)
                    tip_unsplit = await client.wait_for('message', check=lambda message: message.author == ctx.author)

                    tip = int(tip_unsplit)/int(amount_of_people)

                    prompt4 = "Please enter the tax rate of the location (Ex: 0.1025):"
                    await message.channel.send(prompt4)
                    tax_rate = await client.wait_for('message', check=lambda message: message.author == ctx.author)
                    records = []
                    for i in range(int(amount_of_people)):
                        prompt5 = "Please enter the full name of the person you wish to send the invoice to:"
                        await message.channel.send(prompt5)
                        name = await client.wait_for('message', check=lambda message: message.author == ctx.author)

                        prompt6 = "Please enter the total amount (Pre-Tax) that person spent \n"
                        await message.channel.send(prompt6)
                        amount = await client.wait_for('message', check=lambda message: message.author == ctx.author)

                        records.append(createRecord(name, amount, location, date, tax_rate, tip, False))

                    insertRecords(records)
                    post_prompt = "Invoices created and added to database!"
                    await message.channel.send(post_prompt)

            except discord.errors.Forbidden:
                pass
            
client.run(BOT_SECRET)