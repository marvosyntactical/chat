
import youtube_dl
import vlc
import time

def play_youtube_music(url):
    # Create a VLC media player instance
    player = vlc.MediaPlayer()

    # Use youtube-dl to extract the audio URL from the YouTube video URL
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        audio_url = info['formats'][0]['url']

    # Load the audio URL into the VLC player and play it
    media = vlc.Media(audio_url)
    player.set_media(media)
    player.play()

    # Wait until the music finishes playing
    while player.is_playing():
        time.sleep(1)

    # Stop the player and release resources
    player.stop()
    player.release()


if __name__ == "__main__":
    youtube_music_url = "https://www.youtube.com/watch?v=5XZGVcHysNk"
    play_youtube_music(youtube_music_url)

