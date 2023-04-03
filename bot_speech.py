import discord
import os
import whisper
import asyncio
import pytube
import queue
from discord.ext import commands
import yt_dlp as youtube_dl

#youtube music
# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''


ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn',
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

async def play_song(url, vc):
    player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
    vc.play(player, after=lambda e: print(f'Player error: {e}') if e else None)

    await bot.get_channel(1091693907919765576).send(f'Now playing: {player.title}')
    while vc.is_playing():
        await asyncio.sleep(1)
    #await bot.get_channel(1091693907919765576).send("is connected: " , vc.is_connected())

#speech bot
#bot = discord.Client()
model = whisper.load_model("small", device="cuda")
video_urls_queue = queue.Queue()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("!"),
    description='Relatively simple music bot example',
    intents=intents,)

@bot.command(name='play', help='Add a YouTube video or playlist to the queue.')
async def play(ctx, url):
    # Check if the URL is a valid YouTube video or playlist URL
    if 'youtube.com/watch?v=' in url or 'youtube.com/playlist?list=' in url:
        # Add the video URL(s) to the queue
        if 'youtube.com/watch?v=' in url:
            video_urls_queue.put(url)
            await ctx.send(f'{url} added to the queue!')
        elif 'youtube.com/playlist?list=' in url:
            playlist = pytube.Playlist(url)
            for video_url in playlist.video_urls:
                video_urls_queue.put(video_url)
            #await ctx.send(f'{playlist.title} ({playlist.video_count} videos) added to the queue!')
        global current_url
        current_url = url
    else:
        await ctx.send('Invalid YouTube video or playlist URL.')

@bot.command(name='queue', help='Show some of the songs currently in the queue.')
async def show_queue(ctx, num_songs=5):
    song_list = []
    for i in range(min(num_songs, video_urls_queue.qsize())):
        song_url = video_urls_queue.queue[i]
        video = pytube.YouTube(song_url)
        song_list.append(video.title)
    await ctx.send('Currently in queue:\n' + '\n'.join(song_list))


#run
@bot.event
async def on_ready():
    print('Logged in as {0} ({0.id})'.format(bot.user))
    print('------')
    channel = bot.get_channel(1091693907919765577) # Replace CHANNEL_ID with your voice channel ID
    vc = await channel.connect()
    
    i = 0 
    while i <= 1000:
        if vc.is_connected() is True:
            print(i)
            await asyncio.sleep(1)
            vc.start_recording(discord.sinks.WaveSink(),  lambda *args: callback(*args, vc, video_urls_queue))
            
            if vc.recording:
                print("test1")
                await asyncio.sleep(6) # record for 5 seconds
                vc.stop_recording()
                print("test2")
        else: 
            print("not conncected")
            vc = await channel.connect()
        i+=1

async def callback(sink: discord.sinks, vc, video_urls_queue):
    for user_id, audio in sink.audio_data.items():
        audio: discord.sinks.core.AudioData = audio
        print(user_id)
        filename = "audio.wav"
        with open(filename, "wb") as f:
            f.write(audio.file.getvalue())
        text = model.transcribe(filename, language="en")["text"]
        print(f"Received: {text}")
        text = text.lower().replace(".", "").replace("!", "").replace(",", "").replace(" ","").replace("?", "").replace("'", "")
        print(f"Processed text: {text}")
        os.remove(filename)
        if  text in ["playamusic", "latemusic", "playitmusic", "startsthemusic", "letsplaymusic", "playedmusic", "startthemusic", "startmusic", "Play to music","playingmusic", "playmusic", "playthemusic", "laymusic", "laythemusic", "lateinmusic", "playedamusic", "lakemusic", "ladymusic", "latermusic", "lateatmusic", "playthenews", "playtheabuse", "latetomusic", "claythemusic"]:
            await bot.get_channel(1091693907919765576).send("!play music")
            if vc.is_paused():
                vc.resume()
            elif vc.is_playing():
                vc.stop()
                url = video_urls_queue.get()
                await play_song(url, vc)
            else:
                if video_urls_queue.empty():
                    await bot.get_channel(1091693907919765576).send("Queue empty!!!")    
                else:
                    url = video_urls_queue.get()
                    await play_song(url, vc)

        elif text in ["skippingthemusic", "skiptomusic", "skipmusic", "skipthemusic", "skipsomeone", "nextmusic"]:
            await bot.get_channel(1091693907919765576).send("!skip")
            if vc.is_playing():
                vc.stop()
                url = video_urls_queue.get()
                await play_song(url, vc)

        elif text in ["stopmusic", "stopthemusic",  "stopitplaying", "stopplaying", "stopitplay", "stopplaying", "stoptheplaying"]:
            await bot.get_channel(1091693907919765576).send("!stop") 
            if vc.is_playing():
                vc.pause()
            #classified commands (dont steal my code robbe)



bot.run("TOKEN")