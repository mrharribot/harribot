#   https://realpython.com/how-to-make-a-discord-bot-python/
#   https://discordpy.readthedocs.io/en/latest/api.html?highlight=message#message
#   https://pillow.readthedocs.io/en/stable/
#
#

import discord
import re
import aiohttp
#rom wand.image import Image
import requests
from io import BytesIO
from PIL import Image
import json
import os
from dotenv import load_dotenv

client = discord.Client()

async def image_handler(channel, command):
    if not ("count" in command.keys()):
        command["count"] = 1

    url_list = await getImages(channel, command["count"])

    if(len(url_list) < command["count"]):
        print("No images!!")
        return

    if(command["function"] == "overlay"):
        resp = requests.get(url_list[0])
        if resp.status_code==200:
            base = Image.open(BytesIO(resp.content)).convert("RGBA")
            overlay = Image.open(command["img"]).convert("RGBA")

            ratio = (base.height * 0.75) / overlay.height
            #print(f"{img.size} {overlay.size} {ratio} {overlay.height} {overlay.height*ratio}")
            overlay = overlay.resize((round(overlay.size[0]*ratio), round(overlay.size[1]*ratio)))
            base.paste(overlay, (base.width-overlay.width,base.height-overlay.height), overlay )
            #base.save("plop.png", "PNG")

            with BytesIO() as im_bin:
                base.save(im_bin, 'PNG')
                im_bin.seek(0)
                await channel.send(file=discord.File(fp=im_bin, filename=command["img"]))

    elif(command["function"] == "underlay"):
        resp = requests.get(url_list[0])
        if resp.status_code==200:
            underlay = Image.open(BytesIO(resp.content)).convert("RGBA")
            base = Image.open(command["img"]).convert("RGBA")
            underlay = underlay.resize((round(command["coords"][2] - command["coords"][0]), round(command["coords"][3] - command["coords"][1])))
            inter = Image.new('RGBA', base.size, (255,255,255))
            inter.paste(underlay, (command["coords"][0],command["coords"][1]))
            inter.paste(base, (0,0), base)

            with BytesIO() as im_bin:
                inter.save(im_bin, 'PNG')
                im_bin.seek(0)
                await channel.send(file=discord.File(fp=im_bin, filename=command["img"]))

async def getImages(channel, target_count):

    url_list = []

    async for msg in channel.history(limit=50):
        for emb in msg.embeds:
            if(await(check_image(emb.url))):
                url_list.append(emb.url)
                if(len(url_list) >= target_count):
                    return url_list
        for att in msg.attachments:
            if(await(check_image(att.url))):
                url_list.append(att.url)
                if(len(url_list) >= target_count):
                    return url_list
    return url_list

async def check_image(url):

    image_mimes = ("image/png", "image/jpeg", "image/jpg")
    try:
        timeout = aiohttp.ClientTimeout(total=7)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    mime = resp.headers.get('Content-type', '').lower()
                    if any([mime == x for x in image_mimes]):
                        print(f"good, {url} was {mime}")
                        return True
                    else:
                        print(f"bad, {url} was {mime}")
                        return False
    except Exception as e:
        print(e)
        return False

@client.event
async def on_ready():
    print('Logged in as {0.user}'.format(client))

    url_list = []
    for guild in client.guilds:
        print(f"Guild name: {guild.name}")
    
@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('$'):
        msg = message.content.split()
        req = msg[0][1:]


        if(req == "help"):
            help_list = []
            for cmd in commands:
                if not ("hidden" in cmd.keys()):
                    help_list.append(f'${cmd["name"]}\t\t{cmd["description"]}')
            help_text = "```Command\tInfo\n" + "\n".join(help_list) + "```"
            await message.channel.send(help_text)
            return

        if(req == "add"):
            print(f"add command:")
            print(msg)
            if(msg[1] == "image"):
                if(msg[2] == "overlay"):
                    pass
                elif(msg[2] == "underlay"):     #add image underlay shopper [x1,x2,y1,y2] description
                    if(len(msg) < 6):
                        await message.channel.send(f"Expected 6 parameters, got {len(msg)}")
                        return
                    for cmd in commands:
                        if(cmd["name"] == msg[3]):
                            await message.channel.send(f"Command {msg[3]} already exists")
                            return
                    coords = msg[4].split(",")
                    if(len(coords) != 4):
                        await message.channel.send(f"Expected 4 coordinates, got {len(coords)}")
                        return

                    url_list = await getImages(message.channel, 1)
                    if(len(url_list) < 1):
                        await message.channel.send(f"couldn't find any image in message history!?")
                        return
                    resp = requests.get(url_list[0])
                    if resp.status_code==200:
                        img = Image.open(BytesIO(resp.content)).convert("RGBA")
                        img.save(f"{msg[3]}.png", "PNG")
                    else:
                        await message.channel.send(f"problem fetching image from url")

                    commands.append({'name':msg[3], "type":"image", "function":"underlay", "coords":[int(i) for i in coords], "img":msg[3]+".png","description":(" ".join(msg[5:]))})
                    await message.channel.send(f"Ok, added ${msg[3]}!")
                    print(f"added command {msg[3]}")
                    print(commands)
            return

        for cmd in commands:
            if(cmd["name"] == req):
                if(cmd["type"] == "image"):
                    await image_handler(message.channel, cmd)
                    return

if __name__ == "__main__":
    with open('config.json', 'r') as f:
        config = json.load(f)

    commands = config['COMMANDS']

    load_dotenv()
    client.run(os.getenv("DISCORD_TOKEN")
