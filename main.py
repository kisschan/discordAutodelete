import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pytz import timezone

# .envファイルから環境変数をロード
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

delete_interval = 60  # デフォルトで1時間（60分）おきにチェック
delete_cutoff_minutes = 720  # デフォルトで12時間前のメッセージを削除対象

# JSTのタイムゾーンを定義
JST = timezone('Asia/Tokyo')

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    check_old_messages.start()

@tasks.loop(minutes=delete_interval)
async def check_old_messages():
    print(f"Checking messages at {datetime.utcnow()} UTC")
    now = datetime.utcnow().replace(tzinfo=timezone('UTC')).astimezone(JST)
    cutoff = now - timedelta(minutes=delete_cutoff_minutes)

    for guild in bot.guilds:
        for channel in guild.text_channels:
            try:
                messages = []
                async for message in channel.history(before=cutoff):
                    messages.append(message)
                print(f"Found {len(messages)} messages to delete at {channel.name}.")
                for message in messages:
                    print(f"Attempting to delete message from {message.author}: {message.content}")
                    await message.delete()
                    print(f"Deleted message from {message.author}: {message.content}")
            except discord.Forbidden:
                print(f"Can't delete messages in {channel.name} due to lack of permissions.")
            except discord.HTTPException as e:
                print(f"Failed to delete message in {channel.name}: {e}")

@bot.command()
async def set_interval(ctx, minutes: int):
    """メッセージの削除間隔を設定します。"""
    global delete_interval
    delete_interval = minutes
    if check_old_messages.is_running():
        check_old_messages.change_interval(minutes=delete_interval)
        await ctx.send(f"メッセージの削除間隔を {minutes} 分に変更しました。")
    else:
        check_old_messages.change_interval(minutes=delete_interval)
        check_old_messages.start()
        await ctx.send(f"メッセージの削除間隔を {minutes} 分に設定しました。")

@bot.command()
async def set_cutoff_minutes(ctx, minutes: int):
    """削除対象のメッセージが何分前のものか設定します。"""
    global delete_cutoff_minutes
    delete_cutoff_minutes = minutes
    await ctx.send(f"削除対象を {delete_cutoff_minutes} 分以上前のメッセージに設定しました。")

@bot.command()
async def delete_messages_before(ctx, channel_id: int, minutes: int):
    """指定したチャンネルで特定の時間前のメッセージを削除します。"""
    channel = bot.get_channel(channel_id)
    if channel:
        now = datetime.utcnow().replace(tzinfo=timezone('UTC')).astimezone(JST)
        cutoff = now - timedelta(minutes=minutes)
        try:
            messages = []
            async for message in channel.history(before=cutoff):
                messages.append(message)
            print(f"Retrieved {len(messages)} messages for deletion.")
            if messages:
                for message in messages:
                    print(f"Deleting message from {message.author}: {message.content}")
                    await message.delete()
                await ctx.send(f"{len(messages)} 件のメッセージを削除しました。")
            else:
                await ctx.send("削除対象のメッセージがありません。")
        except discord.Forbidden:
            await ctx.send(f"メッセージを削除する権限がありません。")
        except discord.HTTPException as e:
            await ctx.send(f"メッセージの削除に失敗しました: {e}")

bot.run(TOKEN)

