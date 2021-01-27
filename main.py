import os
import io
import discord
from dotenv import load_dotenv
from sqlitedict import SqliteDict
from fuzzywuzzy import process
from datetime import datetime
import pytesseract
import requests
from PIL import Image
from PIL import ImageFilter
from discord.ext import commands

mydict = SqliteDict('./my_db.sqlite', autocommit=True)

ERROR_STRING = "//ERROR"

load_dotenv()   
TOKEN = os.getenv('DISCORD_TOKEN')

# allowed image types
imageFileTypes = ['png', 'jpg', 'jpeg']

client = discord.Client()   

# get Embed for message
def getEmbed(message_text, channelmentions):
     #Embed formatting
    embed=discord.Embed()
    embed.colour = 0x725E7A
    if (not message_text) or (message_text == ERROR_STRING):
        embed.add_field(name="Requested Channel", value="not sure what you requested", inline=False)
        return embed
    else:
        embed.add_field(name="Requested Channel", value=(message_text), inline=False)

    if len(channelmentions) > 0:
        mentions = ">>> "
        for mention in channelmentions:
            mentions += mention
            mentions += "\n"
        embed.add_field(name="Similar channels", value=(mentions or "hello"), inline=False)
    else:
        embed.add_field(name="Similar channels", value="No similar channel found", inline=False)
        
    embed.set_footer(text="Hit Like to Create a new channel")
    return embed


# Get channel mentions of channels having similar name as message
def getChannelMentions(message, message_text):
    channelList = []
    channelmention = {}
    if message_text == ERROR_STRING: 
        return []
    res = []
    for channel in message.guild.channels:
        if type(channel) != discord.channel.TextChannel:
            continue
        channelList.append(channel.name)
        channelmention[channel.name] = channel.mention
    for channel, weight in process.extract(message_text, channelList):
        if weight > 0:
            res.append(channelmention[channel])
    return res


# Display's all similar channels
async def displayChannels(message, message_text):
    channelmentions = getChannelMentions(message, message_text)
    embed = getEmbed(message_text, channelmentions)
    sent = await message.channel.send(embed=embed)
    await sent.add_reaction('\N{THUMBS UP SIGN}')
    mydict[sent.id] = list([message_text, message.author.id, False, 0])


# check if message is a image
def isImage(message):
    #checks for attachments
    if message.attachments:
        #stores url to image
        linkTemp = message.attachments[0].url
        #checks if attachment is image type
        fileType = linkTemp.split(".")
        #if it is an image type
        if fileType[-1].lower() in imageFileTypes:
            return True

    return False

# get image link
def getImageLink(message):
    return  message.attachments[0].url

#OCR Function Proccess Image and Print Text
def OCRImage(message):
    imageLink = getImageLink(message)
    response = requests.get(imageLink)
    img = Image.open(io.BytesIO(response.content))
    text = pytesseract.image_to_string(img) or ""

    if (not text) or len(text) == 0:
        return ERROR_STRING
    return text


async def deleteChannels(message, Time):
    to_delete = []

    for channel in mydict["created_channels"]:
        id, create_time = channel
        if ((datetime.now() - create_time).total_seconds()/60.0) < float(Time):
            to_delete.append(channel)

    for channel1 in to_delete:
        channel_id, create_time = channel1
        try:
            channel = client.get_channel(int(channel_id))
            await channel.delete()
            created_channels = mydict.get('created_channels', [])
            created_channels.remove(channel1)
            mydict['created_channels'] = created_channels
        except:
            continue


# On Successfull Connection
@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')

@client.event
async def on_message(message):

    if isImage(message):
        await message.add_reaction('\N{THUMBS UP SIGN}')
        mydict[message.id] = list([OCRImage(message), message.author.id, False, 1])
    
    elif message.content.startswith("!doreo-delete-channels"):
        if (len(message.content) > (len("!doreo-delete-channels")+1)) and message.content[len("!doreo-delete-channels")+1].isdigit():
            await deleteChannels(message, message.content[len("!doreo-delete-channels")+1])
        else:
            await message.channel.send("works like this\n!doreo-delete-channels <time_in_minutes>")

    elif message.content.startswith("!doreo") and len(message.content) >= 8:
        await displayChannels(message, message.content[7:])


@client.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    if reaction.message.id not in mydict:
        return
    if user.id != mydict[reaction.message.id][1]:
        return
    if mydict[reaction.message.id][2]:
        return
    mydict[reaction.message.id][2] = True

    if mydict[reaction.message.id][3] == 0:
        await reaction.message.guild.create_text_channel(mydict[reaction.message.id][0]) 
        new_channel_mention = getChannelMentions(reaction.message, (mydict[reaction.message.id][0]))[0]

        created_channels = mydict.get('created_channels', [])
        created_channels.append(tuple([new_channel_mention[2:-1], datetime.now()]))
        mydict['created_channels'] = created_channels

        await reaction.message.channel.send(f"{new_channel_mention}")
        
    elif mydict[reaction.message.id][3] == 1:
        await displayChannels(reaction.message, mydict[reaction.message.id][0])

client.run(TOKEN)
