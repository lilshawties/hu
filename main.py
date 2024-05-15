import disnake
from disnake.ext import commands
import datetime
import os
from dotenv import load_dotenv
from disnake import Member, Role, VoiceState, utils, Option, OptionType
import pytz
import asyncio
import sqlite3
import traceback
import colorama
from colorama import Fore, Style
import json

# --------------------------------------------------------------------------------------------------------------
rooms = {}

# msid = 0
# msid2 = 0 
# confession_channel_id = 0
# confession_create_channel_id = 0
# embed_color = 0xfd5296 
# command_prefix = "."

with open("cfs.json", "r") as f:
		cfs_data = json.load(f)
        
cfs_count = cfs_data.get("count", 0)

load_dotenv()
TOKEN = os.getenv('TOKEN')
msid = os.getenv('MSID1')
msid2 = os.getenv('MSID2')
confession_channel_id = int(os.getenv('CFS_ID')) or 0
confession_create_channel_id = int(os.getenv('CFS_CRT_ID')) or 0
command_prefix = os.getenv('PREFIX')
embed_color = os.getenv('EMBEDCOLOR')

bot = commands.Bot(command_prefix=[command_prefix], intents=disnake.Intents.all())
bot.remove_command('help')

conn = sqlite3.connect('rooms.db')
c = conn.cursor()

c.execute('''
		CREATE TABLE IF NOT EXISTS rooms
		(owner_id INTEGER PRIMARY KEY,
		room_id INTEGER,
		room_name TEXT,
		is_hidden INTEGER,
		is_locked INTEGER,
		allowed_users TEXT,
		disallowed_users TEXT)
''')
conn.commit()
conn.close()

async def is_true_channel(ctx):
	if confession_channel_id == 0 or confession_create_channel_id == 0:
		await ctx.reply(embed=disnake.Embed(description="**Server hiện chưa được setup để tạo confession. Vui lòng liên hệ quản trị viên server hoặc người vận hành BOT để biết thêm thông tin.**", color=0xff0000))
		return False
	if ctx.channel.id == confession_create_channel_id:
		return True
	else:
		await ctx.message.delete()
		crt_channel = f"https://discord.com/channels/{ctx.guild.id}/{confession_create_channel_id}"
		temp = await ctx.send(embed = disnake.Embed(description=f"**Bạn chỉ có thể tạo confessions ở kênh {crt_channel} .**",color=0xff0000))
		await asyncio.sleep(3)
		await temp.delete()
		return False

def read_rooms():
	global rooms
	try:
		with open("rooms.txt", "r", encoding='utf-8') as f:
			for line in f:
				room_id, owner_id, created_at, name = line.strip().split(",")
				created_at = datetime.datetime.fromisoformat(created_at).astimezone(
						pytz.timezone('UTC'))
				rooms[int(room_id)] = {
						"owner": int(owner_id),
						"created_at": created_at,
						"name": name
				}
			time = datetime.datetime.now().strftime("%d/%m/%Y|%H:%M:%S")
			print(Fore.CYAN + f"INFO [{time}]:" + Style.RESET_ALL + Fore.YELLOW + f" Đã đọc file thành công!")
	except FileNotFoundError:
		with open("rooms.txt", "w") as f:
			pass

def write_rooms():
	global rooms
	with open("rooms.txt", "w", encoding='utf-8') as f:
		for room_id, room_info in rooms.items():
			f.write(
					f"{room_id},{room_info['owner']},{room_info['created_at'].astimezone(pytz.timezone('Asia/Ho_Chi_Minh')).isoformat()},{room_info['name']}\n"
			)
			time = datetime.datetime.now().strftime("%d/%m/%Y|%H:%M:%S")
			print(Fore.CYAN + f"INFO [{time}]:" + Style.RESET_ALL + Fore.YELLOW + f" Đã ghi file thành công!")

async def is_in_room(ctx):
	global rooms
	if ctx.author.voice is None or ctx.author.voice.channel is None:
		temp = await ctx.reply(
			embed=disnake.Embed(description=f"**Bạn cần ở trong phòng tự tạo để sử dụng lệnh.\nHãy sử dụng lệnh `{command_prefix}create` để tạo phòng nhé.**",color=0xff0000))
		await asyncio.sleep(3)
		await temp.delete()
		return False
	elif ctx.author.voice.channel.id in rooms:
		return True
	else:
		temp = await ctx.reply(
			embed=disnake.Embed(description=f"**Bạn cần ở trong phòng tự tạo để sử dụng lệnh.\nHãy sử dụng lệnh `{command_prefix}create` để tạo phòng nhé!**",color=0xff0000))
		await asyncio.sleep(3)
		await temp.delete()
		return False

async def in_room(ctx):
	if ctx.author.voice is None or ctx.author.voice.channel is None:
		temp = await ctx.reply(
			embed=disnake.Embed(description=f"**Bạn cần ở trong phòng tự tạo để sử dụng lệnh.\nHãy sử dụng lệnh `{command_prefix}create` để tạo phòng nhé!**",color=0xff0000))
		await asyncio.sleep(3)
		await temp.delete()
		return False
	else:
		return True
    
async def is_owner(ctx):
	global rooms
	voice_channel = ctx.author.voice.channel
	if voice_channel.id in rooms:
		if ctx.author.id == rooms[voice_channel.id]["owner"]:
			return True
		else:
			embed = disnake.Embed(description="**Bạn cần là chủ phòng để sử dụng lệnh.**", color=0xff0000)
			await ctx.reply(embed = embed, mention_author=False)
			time = datetime.datetime.now().strftime("%d/%m/%Y|%H:%M:%S")
			print(Fore.RED + f"ERROR [{time}]: "+Style.RESET_ALL +f"{ctx.author.display_name}({ctx.author}) không phải chủ của phòng(tên: {ctx.author.voice.channel.name}, id:{ctx.author.voice.channel.id} )")
			return False
	else:
		return False

async def delete_room(channel):
	global rooms
	time = datetime.datetime.now().strftime("%d/%m/%Y|%H:%M:%S")
	channelname = channel.name
	await channel.delete()
	print(Fore.CYAN + f"INFO [{time}]:" + Style.RESET_ALL + " Đã xóa phòng " + Style.RESET_ALL + Fore.YELLOW + f"{channelname}.")
	if channel.id in rooms:
		del rooms[channel.id]
		write_rooms()
	else:
		print(Fore.RED + f"ERROR [{time}]: "+Style.RESET_ALL +f"Lỗi kênh thoại {channelname} không hoạt động với lệnh.")

async def create_room(member, master_channel):
	global rooms
	guild = member.guild
	max_bitrate = guild.bitrate_limit
	created_at = datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))
	conn = sqlite3.connect('rooms.db')
	c = conn.cursor()
	c.execute('''
		SELECT * FROM rooms WHERE owner_id = ?
	''', (member.id, ))
	room_info = c.fetchone()
	if room_info is None:
		new_channel = await guild.create_voice_channel(
				f"Phòng của {member.display_name}",
				category=master_channel.category,
				position=master_channel.position + 99,
				bitrate=max_bitrate)
		avatar_url = member.avatar
		c.execute(
				'''
			INSERT INTO rooms (owner_id, room_id, room_name, is_hidden, is_locked, allowed_users, disallowed_users)
			VALUES (?, ?, ?, ?, ?, ?, ?)
		''', (member.id, new_channel.id, new_channel.name, 0, 0, '', ''))

	else:
		owner_id, room_id, room_name, is_hidden, is_locked, allowed_users, disallowed_users = room_info
		new_channel = await guild.create_voice_channel(
				room_name,
				category=master_channel.category,
				position=master_channel.position + 99,
				bitrate=max_bitrate)
		avatar_url = member.avatar
		c.execute(
				'''
			UPDATE rooms
			SET room_id = ?
			WHERE owner_id = ?
		''', (new_channel.id, member.id))

		await new_channel.set_permissions(guild.default_role,
																			view_channel=not bool(is_hidden),
																			connect=not bool(is_locked))
	conn.commit()
	conn.close()
	rooms[new_channel.id] = {
			"owner": member.id,
			"created_at": created_at,
			"name": f"Phòng của {member.name}"
    }
	embed = disnake.Embed(
		title="Các lệnh của phòng:",
		description=
		f"> `{command_prefix}allow` (al): cho phép ai đó tham gia phòng\n"
		f"> `{command_prefix}bitrate` (br): chỉnh bitrate của phòng\n"
		f"> `{command_prefix}claim` (cl): nhận chủ phòng\n"
		f"> `{command_prefix}deny` (d): không cho phép ai đó tham gia kênh thoại\n"
		f"> `{command_prefix}hide` (h): ẩn phòng\n"
		f"> `{command_prefix}info` (i): xem thông tin phòng\n"
		f"> `{command_prefix}kick` (k): ngắt kết nối ai đó khỏi phòng\n"
		f"> `{command_prefix}lock` (l): khóa phòng\n"
		f"> `{command_prefix}limit` (lm): đặt giới hạn của phòng\n"
		f"> `{command_prefix}name` (n): đổi tên phòng\n"
		f"> `{command_prefix}show` (s): hiển thi phòng\n"
		f"> `{command_prefix}transfer`: chuyển chủ phòng cho ai đó trong phòng\n"
		f"> `{command_prefix}unlock` (ul): mở khóa phòng",
		color=embed_color)
	write_rooms()
	embed.add_field(
		name="Lưu ý",
		value=
		f"- Sử dụng lệnh `{command_prefix}help` để hiển thị lại lệnh hoặc `{command_prefix}help + (lệnh)` để xem chi tiết về lệnh đó.",
		inline=False)
	embed.set_footer(
		text=
		f"{member.name} | Tạo lúc {created_at.astimezone(pytz.timezone('Asia/Ho_Chi_Minh')).strftime('%H:%M:%S %d/%m/%Y')} (UTC+7)",
		icon_url=avatar_url)
	embed.set_author(name=bot.user.display_name, icon_url=bot.user.avatar)
	await new_channel.set_permissions(member, view_channel=True, connect=True)
	await member.move_to(new_channel)
	await new_channel.send(f"Xin chào **{member.mention}**!", embed=embed,allowed_mentions=disnake.AllowedMentions.none())
	time = datetime.datetime.now().strftime("%d/%m/%Y|%H:%M:%S")
	print(Fore.CYAN + f"INFO [{time}]:" + Style.RESET_ALL + " Đã tạo phòng " + Style.RESET_ALL + Fore.YELLOW + f"{new_channel.name}" + Style.RESET_ALL + f" cho {member.display_name}({member.name}).")

async def create_room2(member, master_channel):
	global rooms
	guild = member.guild
	max_bitrate = guild.bitrate_limit
	created_at = datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))
	conn = sqlite3.connect('rooms.db')
	c = conn.cursor()
	c.execute('''
		SELECT * FROM rooms WHERE owner_id = ?
	''', (member.id, ))
	room_info = c.fetchone()
	if room_info is None:
		new_channel = await guild.create_voice_channel(
				f"Phòng của {member.display_name}",
				category=master_channel.category,
				position=master_channel.position + 99,
				bitrate=max_bitrate)
		avatar_url = member.avatar
		c.execute(
				'''
			INSERT INTO rooms (owner_id, room_id, room_name, is_hidden, is_locked, allowed_users, disallowed_users)
			VALUES (?, ?, ?, ?, ?, ?, ?)
		''', (member.id, new_channel.id, new_channel.name, 0, 0, '', ''))

	else:
		owner_id, room_id, room_name, is_hidden, is_locked, allowed_users, disallowed_users = room_info
		new_channel = await guild.create_voice_channel(
				room_name,
				category=master_channel.category,
				position=master_channel.position + 99,
				bitrate=max_bitrate)
		avatar_url = member.avatar
		c.execute(
				'''
			UPDATE rooms
			SET room_id = ?
			WHERE owner_id = ?
		''', (new_channel.id, member.id))

		await new_channel.set_permissions(guild.default_role,
																			view_channel=not bool(is_hidden),
																			connect=not bool(is_locked))
	conn.commit()
	conn.close()
	rooms[new_channel.id] = {
			"owner": member.id,
			"created_at": created_at,
			"name": f"Phòng của {member.name}"
    }
	embed = disnake.Embed(
		title="Các lệnh của phòng:",
		description=
		f"> `{command_prefix}allow` (al): cho phép ai đó tham gia phòng\n"
		f"> `{command_prefix}bitrate` (br): chỉnh bitrate của phòng\n"
		f"> `{command_prefix}claim` (cl): nhận chủ phòng\n"
		f"> `{command_prefix}deny` (d): không cho phép ai đó tham gia kênh thoại\n"
		f"> `{command_prefix}hide` (h): ẩn phòng\n"
		f"> `{command_prefix}info` (i): xem thông tin phòng\n"
		f"> `{command_prefix}kick` (k): ngắt kết nối ai đó khỏi phòng\n"
		f"> `{command_prefix}lock` (l): khóa phòng\n"
		f"> `{command_prefix}limit` (lm): đặt giới hạn của phòng\n"
		f"> `{command_prefix}name` (n): đổi tên phòng\n"
		f"> `{command_prefix}show` (s): hiển thi phòng\n"
		f"> `{command_prefix}transfer`: chuyển chủ phòng cho ai đó trong phòng\n"
		f"> `{command_prefix}unlock` (ul): mở khóa phòng",
		color=embed_color)
	write_rooms()
	embed.add_field(
		name="Lưu ý",
		value=
		f"- Sử dụng lệnh `{command_prefix}help` để hiển thị lại lệnh hoặc `{command_prefix}help + (lệnh)` để xem chi tiết về lệnh đó.",
		inline=False)
	embed.set_footer(
		text=
		f"{member.name} | Tạo lúc {created_at.astimezone(pytz.timezone('Asia/Ho_Chi_Minh')).strftime('%H:%M:%S %d/%m/%Y')} (UTC+7)",
		icon_url=avatar_url)
	embed.set_author(name=bot.user.display_name, icon_url=bot.user.avatar)
	await new_channel.set_permissions(member, view_channel=True, connect=True)
	await member.move_to(new_channel)
	await new_channel.send(f"Xin chào **{member.mention}**!", embed=embed,allowed_mentions=disnake.AllowedMentions.none())
	time = datetime.datetime.now().strftime("%d/%m/%Y|%H:%M:%S")
	print(Fore.CYAN + f"INFO [{time}]:" + Style.RESET_ALL + " Đã tạo phòng " + Style.RESET_ALL + Fore.YELLOW + f"{new_channel.name}" + Style.RESET_ALL + f" cho {member.display_name}({member.name}).")


@bot.event
async def on_ready():
	read_rooms()
	bot.start_time = datetime.datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))
	game = disnake.Game(name="a.create để tạo phòng.", type=0)
	await bot.change_presence(status=disnake.Status.online, activity=game)
	time = datetime.datetime.now().strftime("%d/%m/%Y|%H:%M:%S")
	print(Fore.CYAN + f"INFO [{time}]:" + Style.RESET_ALL + Fore.YELLOW + f" {bot.user} đã sẵn sàng!")
	print(Fore.CYAN + f"Prefix của tôi: {bot.command_prefix}")

@bot.event
async def on_voice_state_update(member, before, after):
		master_channel_id = msid 
		master_channel_id2 = msid2
		master_channel = bot.get_channel(master_channel_id)
		master_channel2 = bot.get_channel(master_channel_id2)
		try: 
			if after.channel and after.channel.id == master_channel_id:
					await create_room(member, after.channel)
			elif after.channel and after.channel.id == master_channel_id2:
					await create_room2(member, after.channel)

			if before.channel and (before.channel.category.id == master_channel.category.id or before.channel.category.id == master_channel2.category.id):
				for channel in before.channel.category.channels:
					if channel.id not in [master_channel_id, master_channel_id2] and not any(member for member in channel.members if not member.bot):
						await delete_room(channel)
		except:
			pass

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if bot.user in message.mentions:
        if message.content.startswith(f"<@{bot.user.id}>") or message.content.startswith(f"<@!{bot.user.id}>"):
                embed = disnake.Embed(
                    title="Xin chào!",
                    description=f"**Prefix của tôi**: `{command_prefix}`\n"
                                f"- **Để xem các lệnh của tôi, hãy sử dụng lệnh `{command_prefix}help` nhé!**",
                    color=embed_color
                )
                embed.set_author(name=bot.user.display_name, icon_url=bot.user.avatar)
                embed.set_thumbnail(url=bot.user.avatar)
                await message.reply(embed=embed)
    else:
        await bot.process_commands(message)

@bot.command(name="cfs", description=f"- Tạo confession\n- **Cách sử dụng**: nhập lệnh `{command_prefix}cfs + nội dung`")
@commands.check(is_true_channel)
@commands.cooldown(1, 10, commands.BucketType.user)
async def create_confession(ctx, *, content=""):
		global cfs_count
		if not content:
				await ctx.message.delete()
				embed = disnake.Embed(description=f"**Cách sử dụng**: nhập lệnh `{command_prefix}cfs + nội dung`", color=embed_color)
				temp = await ctx.send(embed=embed)
				asyncio.sleep(5)
				await temp.delete()
		else:
				cfs_count += 1
				await ctx.message.delete()
				embed = disnake.Embed(title=f"CFS #{cfs_count}", description=content, timestamp=datetime.datetime.now(datetime.UTC), color=embed_color)
				embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url)
				confession_channel = bot.get_channel(confession_channel_id)
				message = await confession_channel.send(embed=embed)
				thread = await message.create_thread(name=f"Trả lời CFS #{cfs_count}")
				await ctx.send(embed= disnake.Embed(title=f"✅ • Đã tạo Confessions **CFS #{cfs_count}**, tại https://discord.com/channels/{ctx.guild.id}/{confession_channel_id}/{message.id}", color=0x37faa2))
				await ctx.send(f"Để tạo confession, hãy sử dụng lệnh `{command_prefix}cfs + nội dung` hoặc `{command_prefix}cfsan + nội dung`(ẩn danh) nhé! <:a_emoji69:1129269646260965488>")
				cfs_data["count"] = cfs_count
				with open("cfs.json", "w") as f:
						json.dump(cfs_data, f)

@bot.command(name="cfsan", description=f"- Tạo confession ẩn danh\n- **Cách sử dụng**: nhập lệnh `{command_prefix}cfsan + nội dung`")
@commands.check(is_true_channel)
@commands.cooldown(1, 10, commands.BucketType.user)
async def create_anonymous_confession(ctx, *, content=""):
		global cfs_count
		if not content: 
				await ctx.message.delete()
				embed = disnake.Embed(description=f"**Cách sử dụng**: nhập lệnh `{command_prefix}cfs + nội dung`", color=embed_color)
				temp = await ctx.send(embed=embed)
				asyncio.sleep(5)
				await temp.delete()
		else:
				cfs_count += 1
				await ctx.message.delete()
				embed = disnake.Embed(title=f"CFS #{cfs_count}", description=content, timestamp=datetime.datetime.now(datetime.UTC), color=embed_color) 
				confession_channel = bot.get_channel(confession_channel_id)
				message = await confession_channel.send(embed=embed)
				thread = await message.create_thread(name=f"Trả lời CFS #{cfs_count}")
				await ctx.send(embed= disnake.Embed(title=f"✅ • Đã tạo Confessions **CFS #{cfs_count}**, tại https://discord.com/channels/{ctx.guild.id}/{confession_channel_id}/{message.id}", color=0x37faa2))
				await ctx.send(f"Để tạo confession, hãy sử dụng lệnh `{command_prefix}cfs + nội dung` hoặc `{command_prefix}cfsan + nội dung`(ẩn danh) nhé! <:a_emoji69:1129269646260965488>")
				cfs_data["count"] = cfs_count
				with open("cfs.json", "w") as f:
						json.dump(cfs_data, f)
        
@bot.command(name='create', aliases=['crt'], description=f"- Hiển thị liên kết để tạo phòng nhanh\n- **Cách sử dụng**: nhập lệnh `{command_prefix}create`\n- **Các lựa chọn khác**: `{command_prefix}crt`")
@commands.cooldown(1, 5, commands.BucketType.user)
async def create_room_command(ctx):
	global rooms
	guiid = ctx.guild
	master_channel_id = msid 
	master_channel_id2 = msid2
	master_channel = bot.get_channel(master_channel_id)
	master_channel2 = bot.get_channel(master_channel_id2)
	embed1=disnake.Embed(description="**Bạn hiện đang ở trong phòng riêng rồi.**", color=0xfcfe74)
	if ctx.author.voice is None or ctx.author.voice.channel is None:
		temp_message = await ctx.reply(f"**Bạn hãy kết nối vào https://discord.com/channels/{guiid}/{msid} để tạo phòng nhé!**",mention_author=False)
		await asyncio.sleep(10)
		await temp_message.delete()
		pass
	elif ctx.author.voice.channel.id and ctx.author.voice.channel.category.id == master_channel.category.id:
		temp_message = await ctx.reply(embed=embed1,mention_author=False)
		await asyncio.sleep(2)
		await temp_message.delete()
	elif ctx.author.voice.channel.id and ctx.author.voice.channel.category.id == master_channel2.category.id:
		temp_message = await ctx.reply(embed=embed1,mention_author=False)
		await asyncio.sleep(2)
		await temp_message.delete()
	else:
		temp_message = await ctx.reply(f"**Bạn hãy kết nối vào https://discord.com/channels/{guiid}/{msid} để tạo phòng nhé!**",mention_author=False)
		await asyncio.sleep(10)
		await temp_message.delete()

@bot.command(name="name", aliases=['n'], description=f"- Đổi tên phòng\n- **Cách sử dụng**: nhập lệnh `{command_prefix}name + (tên phòng)`\n- **Các lựa chọn khác**: `{command_prefix}n`")
@commands.check(is_in_room)
@commands.check(is_owner)
@commands.cooldown(2, 600, commands.BucketType.channel)
async def name(ctx, *, new_name=None):
	if new_name is None:
		await ctx.reply(embed=disnake.Embed(description=f"**Cách sử dụng**: nhập lệnh `{command_prefix}name + (tên phòng)`\n- **Các lựa chọn khác**: `{command_prefix}n`", color=embed_color)
										,mention_author=False)
		return
	voice_channel = ctx.author.voice.channel
	room_info = rooms[voice_channel.id]
	try:
		abc = await ctx.reply(embed=disnake.Embed(description="**Đang đổi tên phòng, vui lòng chờ...**",color=embed_color), mention_author=False)
		await voice_channel.edit(name=new_name)
		conn = sqlite3.connect('rooms.db')
		c = conn.cursor()
		c.execute(
				'''
				UPDATE rooms
				SET room_name = ?
				WHERE owner_id = ?
			''', (new_name, ctx.author.id))
		conn.commit()
		conn.close()
		embed=disnake.Embed(description=f"**Đã đổi tên phòng thành `{new_name}`.**", color=0x00ff00)
		await abc.edit(embed=embed)
	except disnake.errors.NotFound:
		await ctx.send(
				"Kênh thoại không tồn tại hoặc bot không có quyền truy cập.`")
	else:
		pass

@bot.command(name="kick",
						 aliases=['k'],
						 description=f"- Ngắt kết nối ai đó khỏi phòng\n- **Cách sử dụng**: nhập lệnh `{command_prefix}kick + @users`\n- **Các lựa chọn khác**: `{command_prefix}k`")
@commands.cooldown(1, 3, commands.BucketType.user)
@commands.check(is_in_room)
@commands.check(is_owner)
async def kick(ctx, *users: disnake.Member):
	if len(users) == 0:
		await ctx.reply(
				embed=disnake.Embed(description=f"**Cách sử dụng**: nhập lệnh `{command_prefix}kick + @users`\n- **Các lựa chọn khác**: `{command_prefix}k`",color=embed_color),mention_author=False)
		return
	voice_channel = ctx.author.voice.channel
	voice_channel = ctx.author.voice.channel
	room_info = rooms[voice_channel.id]
	owner = ctx.guild.get_member(room_info["owner"])
	not_in_channel = []
	kicked_users = []
	for user in users:
		if user == ctx.author:
			embed=disnake.Embed(description=f"**Bạn hiện đang là chủ phòng.**", color=0xfcfe74)
			await ctx.reply(embed=embed,mention_author=False)
		elif user.voice and user.voice.channel == voice_channel:
			await user.move_to(None)
			kicked_users.append(user.name)
		else:
			not_in_channel.append(user.name)
	if not_in_channel:
		embed=disnake.Embed(description=f"**{', '.join(not_in_channel)}** không ở trong phòng.",color=0xff0000)
		await ctx.send(embed=embed,
									 mention_author=False)
	if kicked_users:
		embed=disnake.Embed(description=f"**{', '.join(kicked_users)}** đã bị ngắt kết nối khỏi phòng.",color=0x00ff00)
		await ctx.reply(
				f"**{', '.join(kicked_users)}** đã bị ngắt kết nối khỏi phòng.",
				mention_author=False)

@bot.command(name="transfer",aliases=['trans'],
						 description=f"- Chuyển chủ phòng cho ai đó trong phòng\n- **Cách sử dụng**: nhập lệnh `{command_prefix}transfer + @user`\n- **Các lựa chọn khác: `{command_prefix}trans`")
@commands.check(is_in_room)
@commands.check(is_owner)
@commands.cooldown(1, 5, commands.BucketType.user)
async def transfer(ctx, *args):
	if len(args) == 0:
		embed=disnake.Embed(description="Hãy `@tag` người dùng trong phòng mà bạn muốn chuyển quyền sở hữu phòng cho họ.",color=0xfcfe74)
		await ctx.reply(
				embed=embed,mention_author=False
		)
		return
	if len(args) > 1:
		embed=disnake.Embed(description="**Bạn chỉ có thể chuyển quyền sở hữu phòng cho một người dùng.**",color=0xff0000)
		await ctx.reply(
				embed=embed,mention_author=False)
		return
	try:
		user = await commands.MemberConverter().convert(ctx, args[0])
	except commands.MemberNotFound:
		embed=disnake.Embed(description=f'**Không tìm thấy người dùng "{args[0]}"**',color=0xff0000)
		await ctx.send(embed=embed)
		return
	voice_channel = ctx.author.voice.channel
	room_info = rooms[voice_channel.id]
	owner = ctx.guild.get_member(room_info["owner"])
	if owner.id == user.id:
		embed=disnake.Embed(description=f"**Bạn hiện đang là chủ phòng.**", color=0xfcfe74)
		await ctx.reply(embed=embed,mention_author=False)
	else:
		if user.voice and user.voice.channel == voice_channel:
			rooms[voice_channel.id]["owner"] = user.id
			write_rooms()
			await voice_channel.set_permissions(user,view_channel=True,connect=True)
			embed=disnake.Embed(description=f"**Bạn đã chuyển quyền sở hữu của phòng cho {user.mention}.**",color=0x00ff00)
			await ctx.reply(embed=embed,mention_author=False)
		else:
			await ctx.reply(embed=disnake.Embed(description=f"**{user.name}** không ở trong phòng.",color=0xff0000),mention_author=False)

@bot.command(name="limit", aliases=['lm'], description=f"- Đặt giới hạn của phòng\n- **Cách sử dụng**: nhập lệnh `{command_prefix}limit`\n- **Các lựa chọn khác**: `{command_prefix}lm`")
@commands.check(is_in_room)
@commands.check(is_owner)
@commands.cooldown(1, 5, commands.BucketType.user)
async def limit(ctx, limit: str = None):
	voice_channel = ctx.author.voice.channel
	room_info = rooms[voice_channel.id]
	if limit is None:
		embed=disnake.Embed(description=f"**Cách sử dụng**: nhập lệnh `{command_prefix}limit + (0-99)`\n- **Các lựa chọn khác**: `{command_prefix}lm`",color=embed_color)
		await ctx.reply(embed=embed,mention_author=False)
		return
	try:
		limit = int(limit)
	except ValueError:
		await ctx.reply(embed=disnake.Embed(description=f"**Giá trị phải là một số và từ 0 đến 99.**",color=0xff0000),mention_author=False)
		return
	if 0 <= limit <= 99:
		await voice_channel.edit(user_limit=limit)
		if limit == 0:
			await ctx.reply(
					embed=disnake.Embed(description="**Bạn đã đặt giới hạn số người tham gia phòng là không giới hạn**.",color=0x00ff00),mention_author=False)
		else:
			await ctx.reply(embed=disnake.Embed(description=f"**Bạn đã đặt giới hạn số người tham gia phòng là {limit}**.",color=0x00ff00),mention_author=False)
	else:
		await ctx.send(embed=disnake.Embed(description=f"**Giá trị phải từ 0 đến 99.**",color=0xff0000))

@bot.command(name="info", aliases=['i'], description=f"- Xem thông tin phòng\n- **Cách sử dụng**: nhập lệnh `{command_prefix}info`\n- **Các lựa chọn khác**: `{command_prefix}i`")
@commands.cooldown(1, 5, commands.BucketType.user)
async def info(ctx):
	global rooms
	if ctx.author.voice is None or ctx.author.voice.channel is None:
		temp = await ctx.reply(embed=disnake.Embed(description=f"**Bạn cần ở trong phòng tự tạo để sử dụng lệnh.\nHãy sử dụng lệnh `{command_prefix}create` để tạo phòng nhé!**",color=0xff0000),mention_author=False)
		await asyncio.sleep(3)
		await temp.delete()
		pass
	elif ctx.author.voice.channel.id in rooms:
		voice_channel = ctx.author.voice.channel
		room_info = rooms[voice_channel.id]
		owner = ctx.guild.get_member(room_info["owner"])
		created_at = room_info["created_at"]
		timezone = pytz.timezone('Asia/Ho_Chi_Minh')
		created_at_utc7 = created_at.astimezone(timezone)
		timestamp = int(created_at_utc7.timestamp())
		embed = disnake.Embed(
				title="Thông tin phòng:",
				description=f"Tên phòng: **{voice_channel.name}**\n"
				f"Chủ phòng: ` {owner.name} `\n"
				f"Thời gian tạo: **<t:{timestamp}:F>**\n"
				f"Tạo cách đây: **<t:{timestamp}:R>**\n"
				f"Số người tham gia: **{len(voice_channel.members)}/{voice_channel.user_limit or 'không giới hạn'}**\n"
				f"Bitrate: **{round(voice_channel.bitrate / 1000)} kbps**",
				color=embed_color)
		await ctx.send(embed=embed)
	else:
		voice_channel = ctx.author.voice.channel
		embed = disnake.Embed(
			title="Thông tin phòng:",
			description=f"Tên phòng: **{voice_channel.name}**\n"
			f"Số người tham gia: **{len(voice_channel.members)}/{voice_channel.user_limit or 'không giới hạn'}**\n"
			f"Bitrate: **{round(voice_channel.bitrate / 1000)} kbps**",
			color=embed_color)
		await ctx.send(embed=embed) 	

@bot.command(name="lock", aliases=['l'], description=f"- Khóa phòng\n- **Cách sử dụng**: nhập lệnh `{command_prefix}lock`\n- **Các lựa chọn khác**: `{command_prefix}l`")
@commands.check(is_in_room)
@commands.check(is_owner)
@commands.cooldown(1, 5, commands.BucketType.user)
async def lock(ctx):
	voice_channel = ctx.author.voice.channel
	guild = ctx.guild
	default_role = guild.default_role
	conn = sqlite3.connect('rooms.db')
	c = conn.cursor()
	c.execute('''
		UPDATE rooms
		SET is_locked = 1
		WHERE owner_id = ?
	''', (ctx.author.id, ))
	conn.commit()
	conn.close()

	await voice_channel.set_permissions(default_role, connect=False)
	await ctx.reply(embed=disnake.Embed(description=f"**Bạn đã khóa phòng!**",color=0x00ff00), mention_author=False)


@bot.command(name="hide",
						 aliases=['ivs', 'h', 'invisible'],
						 description=f"- Ẩn phòng\n- **Cách sử dụng**: nhập lệnh `{command_prefix}hide`\n- **Các lựa chọn khác**: `{command_prefix}h` | `{command_prefix}ivs` | `{command_prefix}invisible`")
@commands.check(is_in_room)
@commands.check(is_owner)
@commands.cooldown(1, 5, commands.BucketType.user)
async def invisible(ctx):
	voice_channel = ctx.author.voice.channel
	guild = ctx.guild
	default_role = guild.default_role
	overwrites = voice_channel.overwrites
	overwrites[default_role].view_channel = False
	conn = sqlite3.connect('rooms.db')
	c = conn.cursor()
	c.execute('''
		UPDATE rooms
		SET is_hidden = 1
		WHERE owner_id = ?
	''', (ctx.author.id, ))
	conn.commit()
	conn.close()
	await voice_channel.edit(overwrites=overwrites)
	await ctx.reply(embed=disnake.Embed(description=f"**Bạn đã ẩn phòng!**",color=0x00ff00), mention_author=False)


@bot.command(name="show",
						 aliases=['vs', 'visible', 's'],
						 description=f"- Hiển thị phòng\n- **Cách sử dụng**: nhập lệnh `{command_prefix}show`\n- **Các lựa chọn khác**: `{command_prefix}s` | `{command_prefix}vs` | `{command_prefix}visible`")
@commands.check(is_in_room)
@commands.check(is_owner)
@commands.cooldown(1, 5, commands.BucketType.user)
async def visible(ctx):
	voice_channel = ctx.author.voice.channel
	guild = ctx.guild
	default_role = guild.default_role
	overwrites = voice_channel.overwrites
	overwrites[default_role].view_channel = True
	conn = sqlite3.connect('rooms.db')
	c = conn.cursor()
	c.execute('''
		UPDATE rooms
		SET is_hidden = 0
		WHERE owner_id = ?
	''', (ctx.author.id, ))
	conn.commit()
	conn.close()
	await voice_channel.edit(overwrites=overwrites)
	await ctx.reply(embed=disnake.Embed(description=f"**Bạn đã hiển thị phòng!**",color=0x00ff00), mention_author=False)

@bot.command(name="unlock", aliases=['ul'], description=f"- Mở khóa phòng\n- **Cách sử dụng**: nhập lệnh `{command_prefix}unlock`\n- **Các lựa chọn khác**: `{command_prefix}ul`")
@commands.cooldown(1, 5, commands.BucketType.user)
@commands.check(is_in_room)
@commands.check(is_owner)
async def unlock(ctx):
	voice_channel = ctx.author.voice.channel
	guild = ctx.guild
	default_role = guild.default_role
	conn = sqlite3.connect('rooms.db')
	c = conn.cursor()
	c.execute('''
		UPDATE rooms
		SET is_locked = 0
		WHERE owner_id = ?
	''', (ctx.author.id, ))
	conn.commit()
	conn.close()
	await voice_channel.set_permissions(default_role, connect=True)
	await ctx.reply(embed=disnake.Embed(description=f"**Bạn đã mở khóa phòng!**",color=0x00ff00), mention_author=False)

@bot.command(name="allow",
						 aliases=['al'],
						 description=f"- Cho phép ai đó tham gia phòng\n- **Cách sử dụng**: nhập lệnh `{command_prefix}allow + @users`\n- **Các lựa chọn khác**: `{command_prefix}al`")
@commands.check(is_in_room)
@commands.check(is_owner)
@commands.cooldown(1, 3, commands.BucketType.user)
async def allow(ctx, *args):
	if len(args) == 0:
		await ctx.reply(embed=disnake.Embed(description=f"**Cách sử dụng**: nhập lệnh `{command_prefix}allow + @users`\n- **Các lựa chọn khác**: `{command_prefix}al`",color=embed_color),mention_author=False)
	voice_channel = ctx.author.voice.channel
	room_info = rooms[voice_channel.id]
	users = []
	invalid_users = []
	for arg in args:
		try:
			user = await commands.MemberConverter().convert(ctx, arg)
			if user == ctx.author:
				await ctx.reply(embed=disnake.Embed(description="Bạn không thể tự cho phép mình.",color=0xff0000),
												mention_author=False)
			else:
				users.append(user)
		except commands.MemberNotFound:
			invalid_users.append(arg)
	for user in users:
		await voice_channel.set_permissions(user, view_channel=True, connect=True)
		conn = sqlite3.connect('rooms.db')
		c = conn.cursor()
		c.execute(
				'''
			UPDATE rooms
			SET allowed_users = allowed_users || ? || ','
			WHERE owner_id = ?
		''', (user.id, ctx.author.id))
		conn.commit()
		conn.close()

	if users:
		await ctx.reply(
				embed=disnake.Embed(description=f"**Bạn đã cho phép `{', '.join(user.name for user in users)}` tham gia kênh thoại.**",color=0x00ff00),
				mention_author=False)
	if invalid_users:
		await ctx.send(embed=disnake.Embed(description=f'**Không tìm thấy người dùng "{", ".join(invalid_users)}".**',color=0xff0000))

@bot.command(name="deny",
						 aliases=['dl', 'disallow', 'd'],
						 description=f"- Không cho phép ai đó tham gia phòng\n- **Cách sử dụng**: nhập lệnh `{command_prefix}deny + @users`\n- **Các lựa chọn khác**: `{command_prefix}d` | `{command_prefix}dl` | `{command_prefix}disallow`")
@commands.check(is_in_room)
@commands.check(is_owner)
@commands.cooldown(1, 3, commands.BucketType.user)
async def disallow(ctx, *args):
	if len(args) == 0:
		await ctx.reply(embed=disnake.Embed(description=f"**Cách sử dụng**: nhập lệnh `{command_prefix}deny + @users`\n- **Các lựa chọn khác**: `{command_prefix}d` | `{command_prefix}dl` | `{command_prefix}disallow`",color=0xfd5294),mention_author=False)
		return
	voice_channel = ctx.author.voice.channel
	room_info = rooms[voice_channel.id]
	users = []
	invalid_users = []
	for arg in args:
		try:
			user = await commands.MemberConverter().convert(ctx, arg)
			if user == ctx.author:
				await ctx.reply(embed=disnake.Embed(description="**Bạn hiện đang là chủ phòng.**",color=0xff0000),
												mention_author=False)
			else:
				users.append(user)
		except commands.MemberNotFound:
			invalid_users.append(arg)
	for user in users:
		await voice_channel.set_permissions(user, connect=False)
		conn = sqlite3.connect('rooms.db')
		c = conn.cursor()
		c.execute(
				'''
			UPDATE rooms
			SET disallowed_users = disallowed_users || ? || ','
			WHERE owner_id = ?
		''', (user.id, ctx.author.id))
		conn.commit()
		conn.close()

	if users:
		await ctx.reply(
				embed=disnake.Embed(description=f"**Bạn đã không cho phép `{', '.join(user.name for user in users)}` tham gia kênh thoại.**",color=0x00ff00),mention_author=False)
	if invalid_users:
		await ctx.send(f'Không tìm thấy người dùng "{", ".join(invalid_users)}"')

@bot.command(name="claim", aliases=['cl'], description=f"Nhận chủ phòng\n- **Cách sử dụng**: nhập lệnh `{command_prefix}claim`\n- **Các lựa chọn khác**: `{command_prefix}cl`")
@commands.check(is_in_room)
@commands.cooldown(1, 5, commands.BucketType.user)
async def claim(ctx):
	voice_channel = ctx.author.voice.channel
	room_info = rooms[voice_channel.id]
	owner = ctx.guild.get_member(room_info["owner"])
	if ctx.author.id == owner.id:
		await ctx.reply(embed=disnake.Embed(description="**Bạn hiện đang là chủ phòng.**",color=0xff0000), mention_author=False)
	else:
		if owner.voice is None or owner.voice.channel != voice_channel:
			rooms[voice_channel.id]["owner"] = ctx.author.id
			write_rooms()
			owner = ctx.guild.get_member(room_info["owner"])
			embed= disnake.Embed(description=f"**Hiện {ctx.author.mention} đã là chủ phòng mới!**", color=0x00ff00)
			await ctx.reply(embed=embed,allowed_mentions=disnake.AllowedMentions.none())
			await voice_channel.set_permissions(ctx.author, view_channel=True, connect=True)
		else:
			embed = disnake.Embed(description=f"{ctx.author.mention}** chủ phòng vẫn ở trong phòng mà.**", color=0xff0000)
			await ctx.reply(embed=embed,allowed_mentions=disnake.AllowedMentions.none())


@bot.command(name="bitrate",
						 aliases=['br'],
						 description=f"- Chỉnh bitrate của phòng\n- **Cách sử dụng**: nhập lệnh `{command_prefix}bitrate`\n- **Các lựa chọn khác**: `{command_prefix}br`")
@commands.check(is_in_room)
@commands.check(is_owner)
@commands.cooldown(1, 5, commands.BucketType.user)
async def bitrate(ctx, bitrate: str = None):
	guild = ctx.guild
	bitmax = guild.bitrate_limit / 1000
	if bitrate is None:
		await ctx.reply(
				embed=disnake.Embed(description=f"**Cách sử dụng**: nhập lệnh `{command_prefix}bitrate + (8-{round(bitmax)})`\n- **Các lựa chọn khác**: `{command_prefix}br`",color=embed_color),
				mention_author=False)
		return
	try:
		bitrate = int(bitrate)
	except ValueError:
		await ctx.reply(
				embed=disnake.Embed(description=f"Giá trị của bitrate phải là một số và từ 8 đến {round(bitmax)} kbps.",color=0xff0000),
				mention_author=False)
		return
	voice_channel = ctx.author.voice.channel
	room_info = rooms[voice_channel.id]
	if 8 <= bitrate <= bitmax:
		await voice_channel.edit(bitrate=bitrate * 1000)
		await ctx.reply(embed=disnake.Embed(description=f"**Bạn đã chỉnh bitrate thành {bitrate} kbps.**",color=0x00ff00),
										mention_author=False)
	else:
		await ctx.send(
				embed=disnake.Embed(description=f"**Bitrate phải từ 8 đến {round(bitmax)} kbps.**",color=0xff0000)
		)

@bot.command(name="infobot", aliases=['ibot', 'ibt'], description=f"- Hiện thông tin của BOT\n- **Cách sử dụng**: nhập lệnh `{command_prefix}infobot`\n- **Các lựa chọn khác**: `{command_prefix}ibt`")
@commands.cooldown(1, 5, commands.BucketType.user)
async def infobot(ctx):
	embed = disnake.Embed(
			title="Thông tin của BOT",
			description=
			f"**Độ trễ API**: `{bot.latency * 1000:.2f} ms`\n"
			f"**Prefix**: `{command_prefix}`",
			color=embed_color)
	embed.set_author(name=bot.user.display_name, icon_url=bot.user.avatar)
	await ctx.reply(embed=embed,mention_author=False)

@bot.command(name="help", description=f"- Hiển thị các lệnh của BOT\n- **Cách sử dụng**: nhập lệnh `{command_prefix}help`")
async def help(ctx, command_name: str = None):
		guild = ctx.guild
		global rooms
		if command_name is None:
				if ctx.author.voice is None or ctx.author.voice.channel is None:
					embed = disnake.Embed(
							title="Các lệnh của BOT",
							description=
							f"> `{command_prefix}cfs`: Tạo một confession mới\n"
							f"> `{command_prefix}cfsan`: Tạo một confession ẩn danh mới\n"
                        	f"> `{command_prefix}create` (crt): hiển thị liên kết để tạo phòng\n"
							f"> `{command_prefix}infobot` (ibt): hiện thông tin của BOT\n"
							f"- **Để hiển thị các lệnh của phòng, bạn cần kết nối vào một kênh thoại (voice channel).**",
							color=embed_color)
					embed.add_field(
							name="Lưu ý",
							value=
						f"- Sử dụng lệnh `{command_prefix}help` để hiển thị lại lệnh hoặc `{command_prefix}help + (lệnh)` để xem chi tiết về lệnh đó.",
							inline=False)
					embed.set_author(name=bot.user.display_name, icon_url=bot.user.avatar)
					await ctx.send(embed=embed)
				elif ctx.author.voice.channel.id in rooms:
					embed = disnake.Embed(
						title="Các lệnh của phòng:",
						description=
						f"> `{command_prefix}allow` (al): cho phép ai đó tham gia phòng\n"
						f"> `{command_prefix}bitrate` (br): chỉnh bitrate của phòng\n"
						f"> `{command_prefix}claim` (cl): nhận chủ phòng\n"
						f"> `{command_prefix}deny` (d): không cho phép ai đó tham gia kênh thoại\n"
						f"> `{command_prefix}hide` (h): ẩn phòng\n"
						f"> `{command_prefix}info` (i): xem thông tin phòng\n"
						f"> `{command_prefix}kick` (k): ngắt kết nối ai đó khỏi phòng\n"
						f"> `{command_prefix}lock` (l): khóa phòng\n"
						f"> `{command_prefix}limit` (lm): đặt giới hạn của phòng\n"
						f"> `{command_prefix}name` (n): đổi tên phòng\n"
						f"> `{command_prefix}show` (s): hiển thi phòng\n"
						f"> `{command_prefix}transfer`: chuyển chủ phòng cho ai đó trong phòng\n"
						f"> `{command_prefix}unlock` (ul): mở khóa phòng",
						color=embed_color)
					embed.add_field(name="Lưu ý",value=f"- Sử dụng lệnh `{command_prefix}help` để hiển thị lại lệnh hoặc `{command_prefix}help + (lệnh)` để xem chi tiết về lệnh đó.", inline=False)
					embed.set_author(name=bot.user.display_name, icon_url=bot.user.avatar)
					await ctx.send(embed=embed)
				else:
					embed = disnake.Embed(
							title="Các lệnh của phòng:",
							description=
							f"> `{command_prefix}info` (i): xem thông tin phòng\n"
							f"- *Gợi ý: để hiển thị đầy đủ lệnh, bạn cần kết nối vào một kênh thoại do bot tạo hoặc tạo phòng của bạn!*",
							color=embed_color)
					embed.add_field(
							name="Lưu ý",
							value=
							f"- Sử dụng lệnh `{command_prefix}help` để hiển thị lại lệnh hoặc `{command_prefix}help + (lệnh)` để xem chi tiết về lệnh đó.",
							inline=False)
					embed.set_author(name=bot.user.display_name, icon_url=bot.user.avatar)
					await ctx.send(embed=embed)
		else: 
			command = bot.get_command(command_name)
			if command is None:
				embed=disnake.Embed(description=f"**Không tìm thấy lệnh `{command_name}`, vui lòng thử lại!**",color=0xff0000)
				await ctx.send(embed=embed)
			else: 
				embed=disnake.Embed(title=f"Thông tin lệnh: `{command.name}`", description=command.description, color=embed_color)
				embed.set_author(name=bot.user.display_name, icon_url=bot.user.avatar)
				embed.set_thumbnail(url=bot.user.avatar)
				await ctx.send(embed=embed)

@bot.slash_command(name="find_room", description="Tìm phòng của một người nào đó", options=[
			Option("user", "Tên người dùng bạn muốn tìm phòng", OptionType.user, required=True),
			Option("private", "Ẩn nó?", OptionType.boolean, required=False)])
async def find_room(ctx, user: disnake.User, private: bool = False):
	guild = ctx.guild
	for channel in guild.channels:
			if isinstance(channel, disnake.VoiceChannel) and user in channel.members:
					await ctx.send(f"**Hiện {user.mention} đang ở trong https://discord.com/channels/{guild.id}/{user.voice.channel.id} !**", allowed_mentions=disnake.AllowedMentions.none(), ephemeral=private)
					return
	await ctx.send(f"**{user.mention} hiện không ở trong phòng nào.**", allowed_mentions=disnake.AllowedMentions.none(), ephemeral=private)

@bot.event
async def on_command(ctx):
		command = ctx.command.name
		user = ctx.author.name
		time = datetime.datetime.now().strftime("%d/%m/%Y|%H:%M:%S")
		print(Fore.CYAN + f"INFO [{time}][{bot.user.display_name}]:" + Style.RESET_ALL + Fore.YELLOW + f" {ctx.author.display_name}({user})"+Style.RESET_ALL + " đã gọi lệnh "+ Fore.YELLOW + f"{command}" + Style.RESET_ALL+ ".")

@bot.event
async def on_command_error(ctx, error):
	time = datetime.datetime.now().strftime("%d/%m/%Y|%H:%M:%S")
	if isinstance(error, commands.CommandNotFound):
		pass
	elif isinstance(error, commands.CheckFailure):
		pass
	elif isinstance(error, commands.CommandOnCooldown): 
		command = ctx.command.name
		embed = disnake.Embed(description=f"**Bạn phải đợi `{error.retry_after:.2f}` giây để sử dụng lại lệnh này.**", color=0xff0000)
		print(Fore.RED + f"ERROR [{time}]: "+Style.RESET_ALL +f"Lệnh {command} đang hồi.")
		try: 
			send_cooldown = await ctx.reply(embed=embed, mention_author=False)
			await asyncio.sleep(3)
			await send_cooldown.delete()
		except: 
			pass
	else:
		formatted_traceback = ''.join(
				traceback.format_exception(type(error), error, error.__traceback__))
		print(Fore.RED + f"ERROR [{time}]: "+Style.RESET_ALL +f"\n{formatted_traceback}")

bot.run(TOKEN)




