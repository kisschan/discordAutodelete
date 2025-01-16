import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pytz import timezone
from collections import defaultdict
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import logging

# .envファイルから環境変数をロード
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# ログ設定
logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# JSTのタイムゾーンを定義
JST = timezone('Asia/Tokyo')

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    check_old_messages.start()

# チャンネルごとの設定を保存する辞書
channel_settings = defaultdict(lambda: {"delete_interval": 5, "delete_cutoff_minutes": 10})

@bot.command()
async def set_interval(ctx, minutes: int):
    """メッセージの削除間隔を設定します。"""
    channel_id = ctx.channel.id
    channel_settings[channel_id]["delete_interval"] = minutes

    if check_old_messages.is_running():
        check_old_messages.change_interval(minutes=minutes)
        await ctx.send(f"{ctx.channel.name} チャンネルのメッセージ削除間隔を {minutes} 分に変更しました。")
    else:
        check_old_messages.start()
        await ctx.send(f"{ctx.channel.name} チャンネルのメッセージ削除間隔を {minutes} 分に設定しました。")

@bot.command()
async def set_cutoff_minutes(ctx, minutes: int):
    """削除対象のメッセージが何分前のものか設定します。"""
    channel_id = ctx.channel.id
    channel_settings[channel_id]["delete_cutoff_minutes"] = minutes
    await ctx.send(f"{ctx.channel.name} チャンネルの削除対象を {minutes} 分以上前のメッセージに設定しました。")

@tasks.loop(minutes=1)
async def check_old_messages():
    """各チャンネルの設定に基づき古いメッセージを削除します。"""
    for channel_id, settings in channel_settings.items():
        delete_interval = settings["delete_interval"]
        delete_cutoff_minutes = settings["delete_cutoff_minutes"]

        channel = bot.get_channel(channel_id)
        if not channel:
            continue

        # 削除対象のメッセージを取得し、削除
        cutoff_time = discord.utils.utcnow() - timedelta(minutes=delete_cutoff_minutes)
        async for message in channel.history(limit=100):
            if message.created_at < cutoff_time and any(att.content_type.startswith("image/") for att in message.attachments):
                await message.delete()

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

# ダミーのHTTPサーバー
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

# HTTPサーバーを別スレッドで起動
def run_server():
    server = HTTPServer(('0.0.0.0', 8080), Handler)
    print("Starting HTTP server on port 8080...")
    try:
        server.serve_forever()
    except Exception as e:
        logging.error(f"HTTP server error: {e}")
        server.shutdown()

# メインスレッドでDiscordボットを起動し、別スレッドでHTTPサーバーを実行
if __name__ == "__main__":
    # HTTPサーバーを別スレッドで実行
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True  # メインスレッドが終了してもサーバーは終了する
    server_thread.start()

    # Discordボットを実行
    bot.run(TOKEN)
