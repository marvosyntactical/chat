# copy paste from SO: https://stackoverflow.com/questions/6796492/temporarily-redirect-stdout-stderr

import os
from playsound import playsound
import requests
import sys
import time
import threading
import gi

class Spinner:
    busy = False
    delay = 0.2
    cursors = "⣾⣽⣻⢿⡿⣟⣯⣷" # "|/-\\"

    @staticmethod
    def spinning_cursor():
        while 1:
            for cursor in Spinner.cursors: yield cursor

    def __init__(self, description: str= "", delay: float = 0.1):
        print(description, end=" ")
        self.spinner_generator = self.spinning_cursor()
        if delay and float(delay): self.delay = delay

    def spinner_task(self):
        while self.busy:
            sys.stdout.write(next(self.spinner_generator))
            sys.stdout.flush()
            time.sleep(self.delay)
            sys.stdout.write('\b')
            sys.stdout.flush()

    def __enter__(self):
        self.busy = True
        threading.Thread(target=self.spinner_task).start()

    def __exit__(self, exception, value, tb):
        self.busy = False
        time.sleep(self.delay)
        if exception is not None:
            return False




class Logger(object):
    def __init__(self, logfile: str):
        self.terminal = sys.stdout
        self.log = open(logfile, "a")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        # this flush method is needed for python 3 compatibility.
        # this handles the flush command by doing nothing.
        # you might want to specify some extra behavior here.
        pass

class RedirectStdStreams(object):
    def __init__(self, stdout=open(os.devnull, "w"), stderr=open(os.devnull, "w")):
        self._stdout = stdout or sys.stdout
        self._stderr = stderr or sys.stderr

    def __enter__(self):
        self.old_stdout, self.old_stderr = sys.stdout, sys.stderr
        self.old_stdout.flush(); self.old_stderr.flush()
        sys.stdout, sys.stderr = self._stdout, self._stderr

    def __exit__(self, exc_type, exc_value, traceback):
        self._stdout.flush(); self._stderr.flush()
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr


def eleven_labs_speech(text, voice_index=0, eleven_labs_api_key=""):
    """Speak text using elevenlabs.io's API"""

    tts_headers = {
        "Content-Type": "application/json",
        "xi-api-key": eleven_labs_api_key
    }

    voices = ["ErXwobaYiN019PkySvjV", "EXAVITQu4vr4xnSDxMaL"]
    tts_url = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}".format(
        voice_id=voices[voice_index]
    )
    formatted_message = {"text": text}
    with Spinner(f"Generating Speech"):
        response = requests.post(
            tts_url, headers=tts_headers, json=formatted_message)

    if response.status_code == 200:
        speech_file = "speech.mpeg"
        with open(speech_file, "wb") as f:
            f.write(response.content)
        # wait for playsound to finish
        with Spinner(f"Speaking"):
            playsound(speech_file, block=True)
        print()
        os.remove(speech_file)
        return True
    else:
        print("Request failed with status code:", response.status_code)
        print("Response content:", response.content)
        return False

def init_alsa():
    # DEPRECATED

    gi.require_version('Gst', '1.0')
    from gi.repository import Gst

    # Initialize GStreamer
    Gst.init(None)

    # Configure the GStreamer pipeline
    pipeline_str = 'alsasrc ! null'
    pipeline = Gst.parse_launch(pipeline_str)

    # Get the ALSA source element and set its properties
    alsasrc = pipeline.get_by_name('alsasrc')
    alsasrc.set_property('device', 'hw:0')  # Set the desired audio device if needed

    # Create a bus to get error messages
    bus = pipeline.get_bus()

    # Disable error messages from ALSA
    bus.set_flushing(True)
    bus.set_flushing(False)
    bus.add_signal_watch()
    bus.enable_sync_message_emission()
    bus.connect('message', lambda bus, message: None)

    # Start the pipeline
    pipeline.set_state(Gst.State.PLAYING)

    # Your speech recognition code goes here...

    # Clean up
    pipeline.set_state(Gst.State.NULL)




if __name__ == '__main__':

    devnull = open(os.devnull, 'w')
    print('Fubar')

    with RedirectStdStreams(stdout=devnull, stderr=devnull):
        print("You'll never see me")

