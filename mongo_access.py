import re
from datetime import datetime

from bson.decimal128 import Decimal128
from pymongo.mongo_client import MongoClient

from config import *

mongo_client = MongoClient(CONNECT_STRING)
db = mongo_client[DATABASE_NAME]
invoice_collection = db[INVOICE_COLLECTION]
credit_collection = db[CREDIT_COLLECTION]
names_collection = db[NAMES_COLLECTION]


# Returns all unique names
def getNames():
    return names_collection.distinct("name")


def getNameRecord(person: str, key_type: str = "id"):
    key_types = ["id", "name"]
    if key_type not in key_types:
        raise ValueError("Invalid key type. Expected one of: %s" % key_types)

    if key_type == "id":
        search = {"discord_id": str(person)}
    elif key_type == "name":
        search = {"name": str(person)}
    return names_collection.find_one(search)


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
    total = round(
        round(float(subtotal), 2) * (1 + float(tax_rate)) + round(float(tip), 2), 2
    )

    record = {
        "name": name.lower(),
        "discord_id": discord_id,
        "subtotal": Decimal128(str(round(subtotal, 2))),
        "location": location.lower(),
        "date": date,
        "tax_rate": Decimal128(str(tax_rate)),
        "tip": Decimal128(str(round(tip, 2))),
        "total": Decimal128(str(total)),
        "paid": paid,
        "balance": Decimal128(str(total)),
    }
    return record


def insertRecords(records):
    invoice_collection.insert_many(records)


def getUnpaidBalances():
    pipeline = [
        {"$match": {"paid": False}},
        {"$group": {"_id": "$name", "balance": {"$sum": "$balance"}}},
    ]
    return invoice_collection.aggregate(pipeline)


def getBalanceRecord(person, key_type: str = "id"):
    key_types = ["id", "name"]
    match_type = ""
    group_type = ""
    if key_type not in key_types:
        raise ValueError("Invalid key type. Expected one of: %s" % key_types)

    if key_type == "id":
        match_type = "discord_id"
        group_type = "$discord_id"
    else:
        match_type = "name"
        group_type = "$name"

    match = {"$match": {"paid": False, match_type: person}}
    group = {"$group": {"_id": group_type, "balance": {"$sum": "$balance"}}}
    pipeline = [match, group]
    if invoice_collection.count_documents({"paid": False, match_type: person}) == 0:
        return None
    else:
        return invoice_collection.aggregate(pipeline).next()


def payOffBalance(person, amount: Decimal128, key_type: str = "id"):
    key_types = ["id", "name"]
    search = {}
    amount = amount.to_decimal()

    if key_type not in key_types:
        raise ValueError("Invalid key type. Expected one of: %s" % key_types)

    if key_type == "id":
        search = {"discord_id": str(person), "paid": False}
    elif key_type == "name":
        search = {"name": str(person), "paid": False}

    # TODO: Raise error if invalid ID or name
    records = invoice_collection.find(search).sort("date", -1)
    for record in records:
        if amount >= record["balance"].to_decimal():
            # Update record
            invoice_collection.find_one_and_update(
                {"_id": record["_id"]},
                {"$set": {"paid": True, "balance": Decimal128("0")}},
            )
            amount -= record["balance"].to_decimal()
        elif amount > 0:
            # Partially update some record with the amount they paid off
            invoice_collection.find_one_and_update(
                {"_id": record["_id"]},
                {"$inc": {"balance": Decimal128(-amount)}},
            )
            amount = 0
            break
    # TODO: Make it so extra amount gets put into Credit Table


def getCredit(person, key_type="id"):
    key_types = ["id", "name"]
    search = {}

    if key_type not in key_types:
        raise ValueError("Invalid key type. Expected one of: %s" % key_types)

    if key_type == "id":
        search = {"discord_id": str(person)}
    elif key_type == "name":
        search = {"name": person}
    if credit_collection.count_documents(search):
        return credit_collection.find_one(search)["credit"]
    return None


def addCredit(person: str, credit: Decimal128, key_type="id"):
    key_types = ["id", "name"]
    search = {}

    if key_type not in key_types:
        raise ValueError("Invalid key type. Expected one of: %s" % key_types)

    if key_type == "id":

        record = getNameRecord(person, key_type="id")
        print(record)
        search = {"discord_id": person, "name": record["name"]}
    elif key_type == "name":
        search = {"discord_id": None, "name": person}
    print("TEST1")
    data = {"$inc": {"credit": credit}}
    credit_collection.update_one(search, data, upsert=True)
