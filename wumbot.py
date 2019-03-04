import discord
import asyncio
import sys
import json
import logging
import random
import time
import os

LOGGING_FILENAME = 'wumbot.log'

class ChannelLock:
        server                  = None  # id of server
        channel                 = None  # target channel object
        
        info_channelid  = ""    # text channel in which to send status messages
        
        old_perms               = None  # store old permiossion overwrites that they may be restored
        old_voice_limit = 0
        
        role                    = None  # object of created role
        allowed_roles   = []    # all allowed roles added by wumbot
        members                 = []    # all members assigned to role

class Edgelord:
        serverid                = ""
        previous_roleid = ""
        victim                  = None
        infochannel     = ""

locked_channels = []

client = discord.Client()

responses = None
admins = None

def load_global_admins():
        global admins
        filename = "administrators.json"
        file = open(filename, 'r')
        admins = json.load(file)
        file.close()

def reload_data():
        global admin_ids
        global forbidden_channels
        global responses
        filename = "responses.json"
        file = open(filename, 'r')
        responses = json.load(file)
        file.close()
        load_global_admins()
        admin_file = open('admins.json', 'r')
        ignore_file = open('ignore_channels.json', 'r')
        admin_ids = json.load(admin_file)
        forbidden_channels = json.load(ignore_file) 
        admin_file.close()
        ignore_file.close()

# gamble stuff
bank = {} # maps user id to their credits
gamble_timer = {} # maps user id to their last gamble
gamble_cooldown = 69
#load these from json file
bank_filename = "bank.json"
bank_file = open(bank_filename, 'r')
bank = json.load(bank_file)
bank_file.close()
for key in bank:
        gamble_timer[key] = 0

banklog_f = open("banklog.json", 'r')
banklog = json.load(banklog_f)
banklog_f.close()

admin_file = open('admins.json', 'r')
ignore_file = open('ignore_channels.json', 'r')
admin_ids = json.load(admin_file)
forbidden_channels = json.load(ignore_file) 
admin_file.close()
ignore_file.close()

random.seed(os.getpid() * time.perf_counter())

def bank_sort(vals, names):
        for i in range(1, len(vals)):
                j = i-1 
                key = vals[i]
                temp = names[i]
                while (vals[j] > key) and (j >= 0):
                        vals[j+1] = vals[j]
                        names[j+1] = names[j]
                        j -= 1
                vals[j+1] = key
                names[j+1] = temp
        vals.reverse()
        names.reverse()

#CS map list
de_maps = ["Cobblestone", "Dust II", "Inferno", "Mirage", "Nuke", "Train", "Cache", "Overpass"]

#roulette stuff
barrel = [0, 0, 0, 0, 0, 1]
hammer = 0

def get_hammer():
        global hammer
        hammer = hammer + 1
        if hammer > 5:
                hammer = 0
        return hammer

def roll_dice(msg, exp = False):
    try:
        cur = "+"
        comps = []
        for c in msg:
            if c == " ":
                continue
            if c == "+" or c == "-":
                comps.append(cur)
                cur = c
            else:
                cur += c
        comps.append(cur)

        tot = 0
        retstr = ""
        for c in comps:
            op = 1
            if c[0] == "-":
                op = -1

            c = c[1:]
            if c[0] == "d":
                c = "1" + c
            if "d" in c:
                # dice roll
                nd = c.split('d')
                n = int(nd[0])
                if n > 500:
                    n = 1
                d = int(nd[1])
                if exp == True and d > 1:
                    add_roll = True
                    roll_again = False 
                    roll = int(random.randint(1,d))
                    if roll == d:
                        roll_again = True
                    while add_roll == True or roll_again == True:
                        if op == 1:
                            retstr += " + "
                        else:
                            retstr += " - "
                        retstr += "[" + str(roll)
                        if roll == d:  
                            retstr += "!" 
                        retstr += "]" 
                        tot += roll * op
                        if roll_again == True:
                            roll = int(random.randint(1,d))
                            add_roll = True
                            if roll == d:
                                roll_again == True
                            else:
                                roll_again = False
                        else:
                            add_roll = False

                else:
                    for x in range(0, n):
                        if op == 1:
                            retstr += " + "
                        else:
                            retstr += " - "
                        roll = random.randint(1,d) * op
                        retstr += "[" +str(roll)+"]"
                        tot += roll 
            else:
                if op == 1:
                    retstr += " + "
                else:
                    retstr += " - "
                retstr += c
                tot += int(c) * op
            retstr += "\n"
        return retstr[3:] + "\n = " + str(tot),tot
    except:
        return "Invalid parameters. Use something like '!r <NdD> <+|-> <n>', or '!re' for exploding dice.\nIE '!re 1d12 + 2 - 1d20'", 0 



happy   = 0
sad     = 0
problem = 0
uptime_sec = 0

lastChannel = -1
status_channels = {}

async def refresh_channels(alert):
    for channel_lock in locked_channels:
        # check the associated voice channel and unlock it if empty
        infoID = channel_lock.info_channelid
        infochannel = client.get_channel(infoID)
        if len(channel_lock.channel.voice_members) == 0:
            await unlock_channel(channel_lock)
            message = "Unlocking empty channel " + channel_lock.channel.name 
            if alert is True:
                print("Removed empty channel.")
            await client.send_message(infochannel, message)

async def unlock_channel(channel_lock):
    infoID = channel_lock.info_channelid
    infochannel = client.get_channel(infoID)
    await client.delete_role(channel_lock.server, channel_lock.role) # this also removes the roles from users and channels
    for role in channel_lock.allowed_roles:
        await client.delete_channel_permissions(channel_lock.channel_lock, role)
    for pair in channel_lock.old_perms:
        await client.edit_channel_permissions(channel_lock.channel, pair[0], pair[1])
    await client.edit_channel(channel_lock.channel, user_limit=channel_lock.old_voice_limit)        
    locked_channels.remove(channel_lock)


async def close_all():
        for channel_lock in locked_channels:
                await client.delete_role(channel_lock.server, channel_lock.role) # this also removes the roles from users and channels
                locked_channels.remove(channel_lock)

async def check_for_empty_channels():
        global bank
        global banklog
        global uptime_sec
        await client.wait_until_ready()
        while not client.is_closed:
                await refresh_channels(True)
                # update bank
                for server in client.servers:
                        for channel in server.channels:
                                if channel != server.afk_channel:
                                        for member in channel.voice_members:
                                                if member.id not in bank:
                                                        bank[member.id] = 5
                                                        gamble_timer[member.id] = 0
                                                bank[member.id] += 1
                #write bank to file
                with open('bank.json', 'w') as fp:
                        json.dump(bank, fp)
                with open('banklog.json', 'w') as blfp:
                        json.dump(banklog, blfp)
                sys.stdout.write('.')
                sys.stdout.flush()
                await asyncio.sleep(69)
                uptime_sec += 69

@client.event
async def on_ready():
        reload_data()
        print('Logging in:')
        print(client.user.name)
        print(client.user.id)
        print('-=-=-=-=-=-=-=-=-=-=-')
        await client.change_presence(game=discord.Game(name='Say !help'))

@client.event
async def on_message(message):
        # Ignore bots
        if message.author.bot:
            if message.channel.name == 'beedo' and message.content != 'Beedo':
                await client.delete_message(message)
                return
        global barrel
        global admin_ids
        global forbidden_channels
        global hammer
        global check_channel_task
        global responses
        global admins
        global happy
        global problem
        global sad
        global last_channel
        global locked_channels
        global status_channels
        global bank
        global banklog
        global gamble_timer
        global de_maps
        global gamble_cooldown

        if message.channel.id in forbidden_channels:
            return

        if message.channel.name == 'beedo':
            if(message.content.lower() != "beedo"):
                await client.delete_message(message)
                await client.send_message(message.channel, "Beedo")
            return

        is_global_admin = False
        # Check if user is global admin (this list should be small and not take long to check)
        if message.author.id in admin_ids:
            is_global_admin = True

        if message.content.lower() in responses["fullmatch"]:
                await client.send_message(message.channel, responses["fullmatch"][message.content.lower()])
        
        if message.content.lower() in responses["happy"]["fullmatch"]:
                happy = happy + responses["happy"]["fullmatch"][message.content.lower()]
        
        if message.content.lower() in responses["sad"]["fullmatch"]:
                sad = sad + responses["sad"]["fullmatch"][message.content.lower()]

        if message.content.lower() == "god bot":
                await client.send_file(message.channel, 'god_bot.jpg')
        
        if message.content.startswith("gar "):
            send = ""
            big = True
            for char in message.content[4:]:
                big = not big
                if big: # big if true
                    send += char.upper()
                else:
                    send += char.lower()
            await client.send_file(message.channel, 'gar.png')
            await client.send_message(message.channel, send)
            await client.delete_message(message)

        if message.content.startswith("/r ") or message.content.startswith("/re "):
            exp = False
            if message.content.startswith("/re "):
                exp = True
            
            


        if message.content.startswith("/r"):
            message.content = "!r" + message.content[2:]

        # Startswith commands
        if message.content.startswith('!'):
                print(message.content)
                # terms are each word that appear in the message. Term[0] is the command, etc
                terms = message.content.split()
                command = terms[0][1:].lower() # trim the ! off of the first term to get the command ('!help' -> 'help')
                toSay = ""

                if command in responses["startswith"]:
                        await client.send_message(message.channel, responses["startswith"][command])

                elif command in responses["sad"]["startswith"]:
                        sad = sad + responses["sad"]["startswith"][command]

                elif command in responses["happy"]["startswith"]:
                        happy = happy + responses["happy"]["startswith"][command]

                elif command == 'emote':
                    emote_msg = None
                    for i in range(1,12):
                        with open('emote/'+str(i)+'.txt', 'r') as this_emote:
                            line = this_emote.read()
                            if emote_msg == None:
                                emote_msg = await client.send_message(message.channel, line)
                            else:
                                await asyncio.sleep(0.75)
                                await client.edit_message(emote_msg, line)
                    return
                
                #roll a dX = !roll 6
                elif command == 'r' or command == "re" or command == "roll":
                        if(command == "re"):
                            await client.send_message(message.channel, roll_dice("".join(terms[1:]), True)[0])
                        else:
                            await client.send_message(message.channel, roll_dice("".join(terms[1:]), False)[0])
                        return
                # cs map
                elif command == 'maps':
                        random.shuffle(de_maps)
                        if len(terms) < 2 or terms[1].isdigit() == False or int(terms[1]) > len(de_maps):
                                for map in de_maps:
                                        toSay += map + ", "
                        elif int(terms[1]) == 0:
                                await client.send_message(message.channel, "CS:GO to the polls")
                                return
                        else:
                                num_maps = int(terms[1])
                                iter = 0
                                while iter < num_maps:
                                        toSay += de_maps[iter] + ", "
                                        iter += 1
                        toSay = toSay[:-2]
                        await client.send_message(message.channel, toSay)

                elif command == 'coinflip':
                        coin = random.randint(1,2)
                        if coin == 1:
                                await client.send_message(message.channel, "Heads.")
                        else:
                                await client.send_message(message.channel, "Tails.")

                #gambling
                elif command == 'riches':

                        # gather data
                        buck_list = []
                        name_list = []
                        richer = 0
                        your_credit = bank[message.author.id]

                        for member in message.server.members:
                                if member.id in bank:
                                        buck_list.append(bank[member.id])
                                        name_list.append(member.display_name)
                        bank_sort(buck_list, name_list)

                        # Determine how many to show
                        to_show = 3
                        if len(terms) > 1:
                            try:
                                to_show = int(terms[1])
                                if to_show > len(buck_list):
                                    to_show = len(buck_list)
                            except ValueError:
                                if terms[1] == "all":
                                    to_show = len(buck_list) 
                        for i in range(0, len(buck_list)):
                                if buck_list[i] > your_credit:
                                        richer += 1
                        #display data
                        toSay = "There are " + str(richer) + " people with more wealth than your " + str(bank[message.author.id])
                        if to_show >= 2:
                                toSay += "\nThe richest "+str(to_show)+" people are:\n```"
                                for x in range(0, to_show):
                                    toSay += "{}\t-\t{}\n".format(buck_list[x], name_list[x])
                                toSay += "```" 
                        else:
                                toSay += "\nThe richest person is:\n```{}\t-\t{}```".format(buck_list[0], name_list[0])
                        toSay += "I have payed out " + str(banklog[0]) + " and recieved " + str(banklog[1]) + " due to failed wagers."
                        await client.send_message(message.channel, toSay)

                elif command == 'gamble':
                        #validate command 
                        if len(terms) != 2:
                                await client.send_message(message.channel, "Syntax is: \n\t!gamble <amount>\n\t ex: !gamble 20\n\t*See '!gamble help'*")
                                return
                        if  terms[1].isdigit() == False:
                                if terms[1].lower() == 'help':
                                        await client.send_message(message.channel, "!gamble <wager> allows you to wager your WUMBucks against me. If your roll (between 1 and 100) is above 55, you will earn double your wager. A roll of exactly 100 will earn you 4 times your wager. Otherwise, I will keep it all.\nYou can only gamble once every 5 minutes, and you earn a free WUMBuck every 69 seconds you spend in a voice channel (other than an AFK channel).\n'!bank' will display your balance. Good luck!")
                                        return
                                elif terms[1].lower() == 'all':
                                        terms[1] = bank[message.author.id]
                                        print(type(terms[1]), str(terms[1]))
                                else:
                                        await client.send_message(message.channel, "Syntax is: \n\t!gamble <amount>\n\t ex: !gamble 20\n\t*See '!gamble help'*")                                
                                        return
                        if int(terms[1]) < 1:
                                await client.send_message(message.channel, "Nice try... Must be a positive integer.\n\t ex: !gamble 20\n\t*See '!gamble help'*")
                        if message.author.id not in bank:
                                bank[message.author.id] = 5
                                gamble_timer[message.author.id] = 0
                                toSay = "No balance detected for " + message.author.display_name +", initializing user's bank with a 5 WUMBuck credit."
                                banklog[0] += 5
                                await client.send_message(message.channel, toSay)
                        # process command
                        if (time.time() < (gamble_timer[message.author.id] + gamble_cooldown)):
                                cooldown = (gamble_timer[message.author.id] + gamble_cooldown) - time.time()
                                await client.send_message(message.channel, "You have gambled too recently. Please wait exactly " + str(cooldown) + " seconds.")
                                return
                        gamble_timer[message.author.id] = time.time()
                        wager = int(terms[1])
                        if wager > bank[message.author.id]:
                                toSay = "A " + str(wager) + " WUMBuck wager exceeds your balance of " + str(bank[message.author.id]) + "..."
                                await client.send_message(message.channel, toSay)
                                return
                        bank[message.author.id] -= wager
                        gamble_roll = random.randint(1, 100)
                        if gamble_roll > 55:
                                if gamble_roll == 100:
                                        toSay = "You rolled: " + str(gamble_roll) + "\nCritical hit! Quadruple earnings! " + message.author.display_name + " wagered " + str(wager) + " WUMBucks and won back " + str((wager*4))+ "!!!!"
                                        bank[message.author.id] += wager * 4
                                        banklog[0] += wager * 4
                                else:
                                        toSay = "You rolled: " + str(gamble_roll) + "\nWinner! " + message.author.display_name + " doubled a wager of " + str(wager) + " WUMBucks!"
                                        bank[message.author.id] += wager * 2
                                        banklog[0] += wager * 2
                        else:
                                toSay = "You rolled: " + str(gamble_roll) + "\n" + message.author.display_name + " wagered " + str(wager) + " WUMBucks and lost..."
                        banklog[1] += wager
                                
                        await client.send_message(message.channel, toSay)
                elif command == 'transfer':
                    if terms[1].isdigit() == False:
                        await client.send_message(message.channel, "Syntax is '!transfer <amount> @person'")
                        return
                    wager = int(terms[1])
                    if len(message.mentions) != 1:
                        await client.send_message(message.channel, "Please specify one person to transfer to. (@them)")
                        return
                    recip = message.mentions[0]
                    if recip.id == message.author.id:
                        await client.send_message(message.channel, "ok done genius")
                        return
                    toSay = ""
                    if wager <= 0:
                        await client.send_message(message.channel, "Wager must be a positive integer.")
                        return
                    if message.author.id not in bank:
                        bank[message.author.id] = 5
                        gamble_timer[message.author.id] = 0
                        banklog[0] += 5
                        toSay = "No balance detected for " + message.author.display_name +", initializing user's bank with a 5 WUMBuck credit."
                        await client.send_message(message.channel, toSay)
                    if wager > bank[message.author.id]:
                        await client.send_message(message.channel, "You only have " + str(bank[message.author.id]) + " available to transfer.")
                        return
                    if recip.id not in bank:
                        bank[recip.id] = 5
                        gamble_timer[recip.id] = 0
                        banklog[0] += 5
                        toSay = "No balance detected for " + recip.display_name +", initializing user's bank with a 5 WUMBuck credit."
                        await client.send_message(message.channel, toSay)
                    # finally, everything is acceptable. DO THE TRANSFER
                    bank[message.author.id] -= wager
                    bank[recip.id] += wager
                    await client.send_message(message.channel, "Transferring " + str(wager) + " from " + message.author.display_name + " to " + recip.display_name + ".")
                   
                elif command == 'bank':
                        if message.author.id not in bank:
                                        bank[message.author.id] = 5
                                        gamble_timer[message.author.id] = 0
                                        toSay = "No balance detected for " + message.author.display_name +", initializing user's bank with a 5 WUMBuck credit."
                                        banklog[0] += 5
                                        await client.send_message(message.channel, toSay)
                        toSay = message.author.display_name + " has a balance of " + str(bank[message.author.id]) + " WUMBucks."
                        await client.send_message(message.channel, toSay)
                        return
                # Roulette
                elif command == "roulette":
                        roll = get_hammer()
                        print(roll)
                        print(barrel)
                        if barrel[roll] == 1:
                                await client.send_message(message.channel, "Bang. You're dead.")
                                random.shuffle(barrel)
                        else:
                                await client.send_message(message.channel, "*click*")
                elif command == "spin":
                        roll = get_hammer()
                        random.shuffle(barrel)
                        print(roll)
                        print(barrel)
                # Complex commands 
                elif command == "vim":
                        await client.send_file(message.channel, 'vim.png')
                elif command == "garfield" or command == "07/27/1978":
                        await client.send_file(message.channel, 'garfield.png')
                elif command == 'report':
                        #toSay += "There are " + managedChannels.length + " reserved channels.\n"
                        emotion = happy - sad
                        toSay += "I have been praised " + str(happy) + " times and berated " + str(sad) + " times, so I am " + str(abs(emotion))
                        if emotion >= 0:
                                toSay += " happy."
                        else:
                                toSay += " sad."
                        await client.send_message(message.channel, toSay)
                
                elif command == 'lock':
                        
                        if message.author.voice_channel is None:
                                toSay += "You must be in a voice channel to lock one."
                                await client.send_message(message.channel, toSay)
                                return
                        for ch in locked_channels:
                                if ch.channel.id == message.author.voice_channel.id:
                                        toSay += "Channel is already locked."
                                        await client.send_message(message.channel, toSay)
                                        return
                        
                        #create ChannelLock
                        channel_lock = ChannelLock()
                        
                        #create new role with default permissions and move it to the bottom
                        role_name = "WUMBOT_GENERATED_ROLE_" + str(len(locked_channels))
                        new_role = await client.create_role(message.server, name=role_name)
                        voice_members = message.author.voice_channel.voice_members
                        for mem in voice_members:
                                await client.add_roles(mem, new_role)


                        channel_lock.channelid          = message.author.voice_channel.id
                        channel_lock.serverid           = message.server.id
                        channel_lock.server             = message.server
                        channel_lock.roleid             = new_role.id
                        channel_lock.info_channelid = message.channel.id
                        channel_lock.channel            = message.author.voice_channel
                        channel_lock.role                       = new_role
                        allowed_members = voice_members
                        channel_lock.members            = allowed_members
                        channel_lock.old_voice_limit= message.author.voice_channel.user_limit
                        channel_lock.old_perms          = message.author.voice_channel.overwrites

                        # lock channel to role
                        permit_overwrite = discord.PermissionOverwrite()
                        permit_overwrite.connect = True
                        permit_overwrite.speak = True


                        forbid_overwrite = discord.PermissionOverwrite()
                        forbid_overwrite.connect = False
                        forbid_overwrite.speak = False



                        for pair in channel_lock.old_perms:
                                await client.edit_channel_permissions(message.author.voice_channel, pair[0], None)
                        await client.edit_channel(message.author.voice_channel, user_limit=0)

                        await client.edit_channel_permissions(message.author.voice_channel, new_role, permit_overwrite)
                        await client.edit_channel_permissions(message.author.voice_channel, message.server.default_role, forbid_overwrite)


                        locked_channels.append(channel_lock)
                        toSay += "Locked channel " + message.author.voice_channel.name
                        await client.send_message(message.channel, toSay)
                
                elif command == 'unlock':
                        if message.author.voice_channel is None:
                                toSay += "Since you are not in a voice channel, I will unlock all empty channels."
                                await client.send_message(message.channel, toSay)
                                await refresh_channels(False)
                                return
                        
                        channel_lock = None
                        for ch in locked_channels:
                                print (ch.channel.name + " vs " + message.author.voice_channel.name)
                                if ch.channel.id == message.author.voice_channel.id:
                                        channel_lock = ch
                                        
                        if channel_lock == None:
                                toSay += "Channel is not locked."
                                await client.send_message(message.channel, toSay)
                                return

                        await unlock_channel(channel_lock)
                        toSay = "Unlocking channel " + channel_lock.channel.name 
                        await client.send_message(message.channel, toSay)
                
                elif command == 'locks':
                        await refresh_channels(False)
                        if len(locked_channels) > 0:
                                toSay += '__**Current locks:**__\n'
                                for ch in locked_channels:
                                        toSay += "\t" + ch.channel.name + ", Allowed users:\n"
                                        for mem in ch.members:
                                                toSay += "\t\t - " + mem.nick + "\n"
                        else:
                                toSay += "There are currently no locked channels."
                        await client.send_message(message.channel, toSay)
                
                elif command == 'allow':
                        if message.author.voice_channel is None:
                                toSay += "You must be in a locked channel to allow members to it."
                                await client.send_message(message.channel, toSay)
                                return

                        for ch in locked_channels:
                                if ch.channel.id == message.author.voice_channel.id:
                                        if len(message.role_mentions) == 0 and len(message.mentions) == 0:
                                                toSay += "You must specify who to allow. (!allow *<@role/member>*)"
                                                await client.send_message(message.channel, toSay)
                                                return

                                        toSay += "Allowing "
                                        
                                        for mem in message.mentions:
                                                await client.add_roles(mem, ch.role)
                                                toSay += " : "
                                                toSay += mem.mention
                                                
                                                foundMember = None
                                                for svmems in ch.members:
                                                        if svmems == mem:
                                                                foundMember = svmems 
                                                if foundMember == None:
                                                        ch.members.append(mem)

                                        index = len(message.mentions)
                                        permit_overwrite = discord.PermissionOverwrite()
                                        permit_overwrite.connect = True
                                        permit_overwrite.speak = True

                                        for role in message.role_mentions:
                                                # add role to channel permitted NYI
                                                await client.edit_channel_permissions(ch.channel, role, permit_overwrite)
                                                ch.allowed_roles.append(role)
                                                toSay += " : " + role.mention
                                                
                                        toSay += " to access " + message.author.voice_channel.name

                                        await client.send_message(message.channel, toSay)
                                        return
                        
                        toSay += "Channel is not locked."
                        await client.send_message(message.channel, toSay)
                
                elif command == 'forbid':
                        if message.author.voice_channel is None:
                                toSay += "You must be in a locked channel to forbid members from it."
                                await client.send_message(message.channel, toSay)
                                return

                        for ch in locked_channels:
                                if ch.channel.id == message.author.voice_channel.id:
                                        if len(message.role_mentions) == 0 and len(message.mentions) == 0:
                                                toSay += "You must specify who to forbid. (!forbid *<@role/member>*)"
                                                await client.send_message(message.channel, toSay)
                                                return

                                        toSay += "Forbidding "
                                        
                                        for mem in message.mentions:
                                                await client.remove_roles(mem, ch.role)
                                                toSay += " : "
                                                toSay += mem.mention
                                                
                                                foundMember = None
                                                for svmems in ch.members:
                                                        if svmems == mem:
                                                                ch.members.remove(svmems)

                                        index = len(message.mentions)

                                        for role in message.role_mentions:
                                                if role in ch.allowed_roles:
                                                        await client.delete_channel_permissions(ch.channel, role)
                                                        ch.allowed_roles.remove(role)
                                                        # remove role to channel permitted NYI
                                                        toSay += " : " + role.mention
                                                else:
                                                        await client.send_message(message.channel, role.mention + " currently is not allowed.")
                                                
                                        toSay += " to access " + message.author.voice_channel.name
                                        await client.send_message(message.channel, toSay)
                                        return
                        
                        toSay += "Channel is not locked."
                        await client.send_message(message.channel, toSay)

                elif command == 'limit':
                        if terms[1]:
                                for ch in locked_channels:
                                        if ch.channel.id == message.author.voice_channel.id:
                                                
                                                toSay += "Limiting channel " + message.author.voice_channel.name + " to " + str(terms[1]) + " members."
                                                await client.edit_channel(message.author.voice_channel, user_limit=terms[1])
                                                await client.send_message(message.channel, toSay)
                                                return

                                toSay += "Channel is not locked"
                                await client.send_message(message.channel, toSay)
                        else:
                                toSay += "Provide a number to which to set member limit (!limit *<n>*)"
                                await client.send_message(message.channel, toSay)
                
                elif command == 'unlimit':
                        for ch in locked_channels:
                                if ch.channel.id == message.author.voice_channel.id:
                                        
                                        toSay += "Unlimiting connections to " + message.author.voice_channel.name + "."
                                        await client.edit_channel(message.author.voice_channel, user_limit=0)
                                        await client.send_message(message.channel, toSay)
                                        return

                        toSay += "Channel is not locked"
                        await client.send_message(message.channel, toSay)

                elif command == 'problem':
                        if problem < 5:
                                toSay += "Reporting problem to Lukaus"
                                # alert to problem
                                print("Problem reported by " + message.author.name)
                        else:
                                toSay += "The problem has been reported, quit spamming me please.\n\t\t- Lukaus"
                        problem = problem + 1
                        await client.send_message(message.channel, toSay)
                
                elif command == 'whoami':
                        toSay += message.author.name + "#" + message.author.discriminator
                        await client.send_message(message.channel, toSay)

                elif command == 'whois':
                        if len(message.mentions) > 0:
                                for mention in message.mentions:
                                        toSay += mention.name + "\n"
                                await client.send_message(message.channel, toSay)

                #Server admin commands
                elif command == "status_channel" and message.author.top_role.permissions.administrator:
                        status_channels.update({message.server.id: message.channel})
                        toSay += "Setting this as WUMBot status channel for server."                    
                        await client.send_message(message.channel, toSay)

                #Global Admin commands
                elif command == 'quit' and is_global_admin:
                        toSay += "WUMBot is going offline, unlocking all locked channels."
                        for server in status_channels:
                                await client.send_message(status_channels[server], toSay)
                        await close_all()
                        client.logout()
                        client.close()
                        await check_channel_task.cancel()
                        sys.exit()

                elif command == 'reload' and is_global_admin:
                        toSay += 'Reloading data.'
                        reload_data()
                        await refresh_channels(False)
                        happy = 0
                        sad = 0
                        await client.send_message(message.channel, toSay)

                else:
                        await client.send_message(message.channel, "Command not recognized. (!commands)")

logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = logging.FileHandler(filename=LOGGING_FILENAME, encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

check_channel_task = client.loop.create_task(check_for_empty_channels())

filename = "token.json"
file = open(filename, 'r')
tokenObj = json.load(file)
file.close()
client.run(tokenObj['token'])
