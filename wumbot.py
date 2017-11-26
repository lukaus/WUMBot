import discord
import asyncio
import sys
import json

class ChannelLock:
	server 			= None 	# id of server
	info_channelid 	= "" 	# text channel in which to send status messages
	channel 		= None	# target channel object
	role 			= None	# object of created role
	members 		= [] 	# all members assigned to role
	allowed_roles	= []	# all allowed roles
	active 			= True
	old_roles		= []	# store old roles that they may be restored


class Edgelord:
	serverid 		= ""
	previous_roleid = ""
	victim 			= None
	infochannel 	= ""

locked_channels = []

client = discord.Client()

responses = None

def reload_responses():
	global responses
	filename = "responses.json"
	file = open(filename, 'r')
	responses = json.load(file)
	file.close()

happy 	= 0
sad 	= 0
problem	= 0

lastChannel = -1

async def refresh_channels():
	for channel_lock in locked_channels:
		# check the associated voice channel and unlock it if empty
		channel = client.get_channel(channel_lock.channel.id)
		if len(channel.voice_members) == 0:
			infoID = channel_lock.info_channelid
			infochannel = client.get_channel(infoID)
			message = "Unlocking empty channel " + channel_lock.channel.name 
			await client.send_message(infochannel, message)
			await client.delete_role(channel_lock.server, channel_lock.role) # this also removes the roles from users and channels
			reallow = discord.PermissionOverwrite()
			reallow.speak = None
			reallow.connect = None
			await client.edit_channel_permissions(channel_lock.channel, channel_lock.server.default_role, reallow)
			locked_channels.remove(channel_lock)

async def close_all():
	for channel_lock in locked_channels:
		await client.delete_role(channel_lock.server, channel_lock.role) # this also removes the roles from users and channels
		locked_channels.remove(channel_lock)

async def check_for_empty_channels():
	await client.wait_until_ready()
	while not client.is_closed:
		for channel_lock in locked_channels:
			# check the associated voice channel and unlock it if empty
			channel = client.get_channel(channel_lock.channel.id)
			if len(channel.voice_members) == 0:
				infoID = channel_lock.info_channelid
				infochannel = client.get_channel(infoID)
				message = "Unlocking empty channel " + channel_lock.channel.name 
				await client.send_message(infochannel, message)
				await client.delete_role(channel_lock.server, channel_lock.role) # this also removes the roles from users and channelsreallow = discord.PermissionOverwrite()
				reallow = discord.PermissionOverwrite()
				reallow.speak = None
				reallow.connect = None
				await client.edit_channel_permissions(channel_lock.channel, channel_lock.server.default_role, reallow)
				locked_channels.remove(channel_lock)
		print ("channels checked")
		await asyncio.sleep(69)

async def debug_console():
	await client.wait_until_ready()
	while not client.is_closed:
		command = input("> ")
		if command == "a":
			print (command)

		elif command == "q":
			await close_all()
			await client.logout()
			await client.close()
			sys.exit()

@client.event
async def on_ready():
	reload_responses()
	print('Logged in as')
	print(client.user.name)
	print(client.user.id)
	print('------')
	await client.change_presence(game=discord.Game(name='Say !help'))

@client.event
async def on_message(message):
	global responses
	global happy
	global problem
	global sad
	global last_channel
	global locked_channels

	if message.content.lower() in responses["fullmatch"]:
		await client.send_message(message.channel, responses["fullmatch"][message.content.lower()])
	
	if message.content.lower() in responses["happy"]["fullmatch"]:
		happy = happy + responses["happy"]["fullmatch"][message.content.lower()]
	
	if message.content.lower() in responses["sad"]["fullmatch"]:
		sad = sad + responses["sad"]["fullmatch"][message.content.lower()]

	if message.content.lower() == "god bot":
		await client.send_file(message.channel, 'god_bot.jpg')

	# Startswith commands
	if message.content.startswith('!'):
		print(message.content)
		terms = message.content.split()
		command = terms[0][1:].lower()
		toSay = ""

		if command in responses["startswith"]:
			await client.send_message(message.channel, responses["startswith"][command])

		elif command in responses["sad"]["startswith"]:
			sad = sad + responses["sad"]["startswith"][command]

		elif command in responses["happy"]["startswith"]:
			happy = happy + responses["happy"]["startswith"][command]

		# Complex commands 
		elif command == 'report':
			#toSay += "There are " + managedChannels.length + " reserved channels.\n"
			toSay += "I have been praised " + str(happy) + " times and berated " + str(sad) + " times, so I am " + str((happy - sad)) + " happy."
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


			channel_lock.channelid 		= message.author.voice_channel.id
			channel_lock.serverid 		= message.server.id
			channel_lock.server 		= message.server
			channel_lock.roleid 		= new_role.id
			channel_lock.info_channelid = message.channel.id
			channel_lock.channel 		= message.author.voice_channel
			channel_lock.role 			= new_role
			allowed_members = voice_members
			channel_lock.members 		= allowed_members
			channel_lock.active 		= True

			# lock channel to role
			perms = message.author.voice_channel.overwrites
			print(str(len(perms)))


			permissions = discord.Permissions.voice()
			permissions.update(speak=True, join_voice=True)

			permit_overwrite = discord.PermissionOverwrite()
			permit_overwrite.connect = True
			permit_overwrite.speak = True

			forbid_overwrite = discord.PermissionOverwrite()
			forbid_overwrite.connect = False
			forbid_overwrite.speak = False

			await client.edit_channel_permissions(message.author.voice_channel, new_role, permit_overwrite)
			await client.edit_channel_permissions(message.author.voice_channel, message.server.default_role, forbid_overwrite)


			locked_channels.append(channel_lock)
			toSay += "Locked channel " + message.author.voice_channel.name
			await client.send_message(message.channel, toSay)
		
		elif command == 'unlock':
			if message.author.voice_channel is None:
				toSay += "Since you are not in a voice channel, I will unlock all empty channels."
				await client.send_message(message.channel, toSay)
				await refresh_channels()
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

			toSay += "Unlocking channel " + channel_lock.channel.name
			await client.delete_role(channel_lock.server, channel_lock.role)
			reallow = discord.PermissionOverwrite()
			reallow.speak = None
			reallow.connect = None
			await client.edit_channel_permissions(channel_lock.channel, channel_lock.server.default_role, reallow)
			locked_channels.remove(channel_lock)
			await client.send_message(message.channel, toSay)
		
		elif command == 'locks':
			await refresh_channels()
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

					toSay += "Allowing "
					
					for mem in message.mentions:
						await client.add_roles(mem, ch.role)
						toSay += " : "
						toSay += mem.mention
						
						ch.members.append(mem)

					index = len(message.mentions)

					for role in message.role_mentions:
						# add role to channel permitted NYI
						toSay += " : " + role.mention
						
					toSay += " to access " + message.author.voice_channel.name
					if len(message.role_mentions) > 0:
						toSay += '\nNote: allow @role is not yet implemented and will have no effect'
					await client.send_message(message.channel, toSay)
					return
			
			toSay += "Channel is not locked."
			await client.send_message(message.channel, toSay)
		
		elif command == 'forbid':
			toSay += 'Forbidding user: <not yet implemented>'
			
			await client.send_message(message.channel, toSay)

		elif command == 'reload':
			toSay += 'Reloading data.'
			reload_responses()
			await refresh_channels()
			happy = 0
			sad = 0
			await client.send_message(message.channel, toSay)

		elif command == 'problem':
			if problem < 5:
				toSay += "Reporting problem to Lukaus"
				# alert to problem
			else:
				toSay += "The problem has been reported, quit spamming me please.\n\t\t- Lukaus"
			problem = problem + 1
			await client.send_message(message.channel, toSay)
		
		elif command == 'whoami':
			toSay += message.author.name
			await client.send_message(message.channel, toSay)

		elif command == 'whois':
			if len(message.mentions) > 0:
				for mention in message.mentions:
					toSay += mention.name + " " + mention.id + "\n"
				await client.send_message(message.channel, toSay)
		
		else:
			await client.send_message(message.channel, "Command not recognized. (!commands)")

client.loop.create_task(check_for_empty_channels())
#client.loop.create_task(debug_console())
client.run('Mzc4Mzk2MTMyNDcwMDMwMzM3.DPs1-w.PBO85h99ZNpugNpTHLJhZsIpSIs')
