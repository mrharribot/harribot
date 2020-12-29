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
from PIL import Image,ExifTags
import json
from dotenv import load_dotenv

client = discord.Client()

def parse_options(string):
    
    args = {}
    skip = False

    options = {"flip":["h","v"], "edge":["l","r","u","d"], "posx":[0,100], "posy":[0,100], "size":[0,200], "rot":[0,360]}
    lst = [i.replace(",",":").replace(";",":").split(":") for i in string + ["null"]]    #lmao
    for item, item1 in zip(lst, lst[1:]):
        if(skip):
            skip = False
            continue
        if(len(item) == 1):
            if(item[0] in options.keys()):      #find a key, check if next item is a value, we can't do any f/b trickery
                if(item1[0] in options.keys()): #if we have another key then skip, otherwise try to interpret
                    continue

                val = options[item[0]]
                if(type(val[0]) is int):        #consider refactoring this out since its identical to the block below
                    if(item1[0].isdigit()):
                        item1[0] = int(item1[0])
                        if(item1[0] >= val[0] and item1[0] <= val[1]):
                            args[item[0]] = item1[0]
                            skip = True
                elif(type(options[item[0]][0]) is str):
                    if(item1[0] in val):
                        args[item[0]] = item1[0]            #ok now we have stolen the next value we should skip next iter right?
                        skip = True
            else:          #we didn't find a key, try to interpret the value as a value! oh wow ok.
                if(item[0].isdigit()):
                    item[0] = int(item[0])
                    for cand in options:
                        if(not (cand in args)):
                            if(type(options[cand][0]) is int):
                                if(item[0] >= options[cand][0] and item[0] <= options[cand][1]):
                                    args[cand] = item[0]
                                    break
                else:
                    for cand in options: 
                        if(not(cand in args)):
                            if(item[0] in options[cand]):
                                args[cand] = item[0]
                                break

        if(len(item) == 2):
            if(item[0] in options.keys()):
                val = options[item[0]]
                if(type(val[0]) is int):
                    if(item[1].isdigit()):
                        item[1] = int(item[1])
                        if(item[1] >= val[0] and item[1] <= val[1]):
                            args[item[0]] = item[1]
                elif(type(options[item[0]][0]) is str):
                    if(item[1] in val):
                        args[item[0]] = item[1]
 
        if(len(item) > 2):
            pass
    return args

#or convenience, here is what the letter F would look like if it were tagged correctly and displayed by a program that ignores the orientation tag (thus showing the stored image):
#
#    1      2       3      4         5            6           7          8
#
#  88888  888888      88  88      8888888888  88                  88  8888888888
#  8          88      88  88      88  88      88  88          88  88      88  88
#  888      8888    8888  8888    88          8888888888  8888888888          88
#  8          88      88  88
#  8          88  888888  888888
def exif_rot(im):

    if(0x112 in im.getexif()):
        rot = im.getexif()[0x112]
        if(rot > 4):
            im = im.transpose(Image.ROTATE_90)
            rot = abs(rot - 9)
        if(rot > 2):
            im = im.transpose(Image.ROTATE_180)
            rot = rot - 2
        if(rot > 1):
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
    return (im)

    

async def image_handler(channel, command, args):
    if not ("count" in command.keys()):
        command["count"] = 1

    url_list = await getImages(channel, command["count"])

    if(len(url_list) < command["count"]):
        print("No images!!")
        return

    if(command["function"] == "overlay"):
        resp = requests.get(url_list[0])
        if resp.status_code==200:

            base = exif_rot(Image.open(BytesIO(resp.content)).convert("RGBA"))
            
            overlay = Image.open(command["img"]).convert("RGBA")
            if("flip" in args.keys()):
                if(args["flip"] == "h"):
                    overlay = overlay.transpose(Image.FLIP_TOP_BOTTOM)
                if(args["flip"] == "v"):
                    overlay = overlay.transpose(Image.FLIP_LEFT_RIGHT)

            if("size" in args.keys()):
                ratio = (base.height * (args["size"]/100) / overlay.height)
            else:
                ratio = (base.height * 0.75 / overlay.height)

            overlay = overlay.resize((round(overlay.size[0]*ratio), round(overlay.size[1]*ratio)))

            if not("posx" in args.keys()):
                args["posx"] = 100

            if not("posy" in args.keys()):
                args["posy"] = 100

            if("rot" in args.keys()):
                overlay = overlay.rotate(args["rot"])

            if not("posx" in args.keys()):
                args["posx"] = 100
            if not("posy" in args.keys()):
                args["posy"] = 100

            base.paste(overlay, (round((base.width-overlay.width)*(args["posx"]/100)),round((base.height-overlay.height)*(args["posy"]/100))), overlay )

            base.save("test.png", 'PNG')
            with BytesIO() as im_bin:
                base.save(im_bin, 'PNG')
                im_bin.seek(0)
                await channel.send(file=discord.File(fp=im_bin, filename=command["img"]))

    elif(command["function"] == "underlay"):
        resp = requests.get(url_list[0])
        if resp.status_code==200:
            underlay = exif_rot(Image.open(BytesIO(resp.content)).convert("RGBA"))
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
        args = parse_options(msg[1:])


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
                    await image_handler(message.channel, cmd, args)
                    return

if __name__ == "__main__":
    with open('config.json', 'r') as f:
        config = json.load(f)

    commands = config['COMMANDS']


    load_dotenv()
    client.run(os.getenv("DISCORD_TOKEN")
