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
    print('We have logged in as {0.user}'.format(discord_client))
    
@client.event
async def on_message(message):
    if message.author == discord_client.user :
        return
    # If its a DM
    if not message.guild:
        # If its the Banker
        if message.author == BANKER_ID:
            try:
                if message.content == "invoice":
                    # Eventually make a function that will allow me to either 
                    # 1. Select a previous name
                    # 2. Add a new name
                    message = "Time to Send Invoices! \n \
                    Please enter the full name of the person you wish to send the invoice to:"
                    await message.channel.send(message)
                    #msg = await client.wait_for('message', check=lambda message: message.author == ctx.author)

            except discord.errors.Forbidden:
                pass
            
client.run(BOT_SECRET)