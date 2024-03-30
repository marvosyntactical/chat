
import os
import shutil
import sys
import gi

from enum import Enum
import colors
import io
import time
import datetime
import json
from typing import List
from pprint import pprint
import keyboard

import speech_recognition as sr
from custom_recognizer import CustomRecognizer
# from speech_recognition import Recognizer
import playsound

import soundfile as sf
from openai import OpenAI
from anthropic import Anthropic

from helpers import Logger, RedirectStdStreams, eleven_labs_speech, Spinner, init_alsa
import socket
import re
import queue
import threading

import warnings
warnings.filterwarnings("ignore")

from subprocess import Popen, PIPE

curr_dir = f"{__file__[:len(__file__)-__file__[::-1].find('/')]}"
CD = f"cd {curr_dir}"

anthropic_api_key = os.getenv("OPENAI_API_KEY")

if anthropic_api_key is None:
    anthropic_filename = curr_dir+ ".anthropic_api_key"
    try:
        with open(anthropic_filename, "r") as api_file:
            anthropic_api_key = api_file.read()[:-1]
    except FileNotFoundError as FNFE:
        print(f"OpenAI Key must be provided at ")
        raise FNFE

anthropic_client = Anthropic(api_key=anthropic_api_key)

openai_api_key = os.getenv("OPENAI_API_KEY")

if openai_api_key is None:
    openai_filename = curr_dir+ ".openai_api_key"
    try:
        with open(openai_filename, "r") as api_file:
            openai_api_key = api_file.read()[:-1]
    except FileNotFoundError as FNFE:
        print(f"OpenAI Key must be provided at ")
        raise FNFE

openai_client = OpenAI(api_key=openai_api_key)



openai_api_key = os.getenv("OPENAI_API_KEY")

if openai_api_key is None:
    openai_filename = curr_dir+ ".openai_api_key"
    try:
        with open(openai_filename, "r") as api_file:
            openai_api_key = api_file.read()[:-1]
    except FileNotFoundError as FNFE:
        print(f"OpenAI Key must be provided at ")
        raise FNFE

openai_client = OpenAI(api_key=openai_api_key)

eleven_labs_api_key = os.getenv("ELEVENLABS_API_KEY")
if eleven_labs_api_key is None:
    eleven_filename = curr_dir+ ".eleven_api_key"
    try:
        with open(eleven_filename, "r") as api_file:
            eleven_labs_api_key = api_file.read()[:-1]
    except FileNotFoundError as FNFE:
        raise FNFE


hostname = socket.gethostname()

DEBUG = 1

default_audio_in = True
default_audio_out = True

# commands
AUDIO_INPUT = "/sr"
AUDIO_OUTPUT = "/tts"
EXIT = "/quit"
ADD = "/add"
HELP = "/help"

WORKSPACE = curr_dir + "workspace/"
if not os.path.isdir(WORKSPACE):
    os.mkdir(WORKSPACE)

COMMANDS = {
    AUDIO_INPUT: "Activate Speech recognition instead of terminal input.",
    AUDIO_OUTPUT: "Activate  Text-to-Speech in addition to terminal output.",
    EXIT: "Quit the chat session.",
    HELP: "Display this help message",
    ADD: "(Deprecated) Add chat to examples.",
}


# ordinal helper function
def ordinal(i: int):
    r = i % 10
    if r==1:
        suffix = "st"
    elif r==2:
        suffix = "nd"
    elif r==3:
        suffix = "rd"
    else:
        suffix = "th"
    return str(i) + suffix

# voice activation
class Trigger(Enum):
    duration = 1
    continuous = 2
    keyword = 3


# main class
class ChatBot:

    def __init__(
            self,
            AUDIO_INPUT = default_audio_in,
            AUDIO_OUTPUT = default_audio_out,
            lang="de", # en; see gtts-cli --all
            timeout=10,
            tmp_dir=".tmp/",
            energy_threshold=50, # min volume to consider for recording
            examples={},
            log: bool=False,
            name: str="Omega",
            tts_server: str = "eleven",
            mic_index: int = 0, # 2==pi, 0==ubuntu
            stream_msg: bool = True,
            stream_audio: bool = True,
            **kwargs
        ):

        self.stream_msg = stream_msg
        self.stream_audio = stream_audio

        self.mic_index = mic_index
        self.lang = lang
        self.AUDIO_INPUT = AUDIO_INPUT
        self.AUDIO_OUTPUT = AUDIO_OUTPUT
        self.name = name
        self.tts_server = tts_server

        self.R = CustomRecognizer()
        # self.R = sr.Recognizer()
        self.R.energy_threshold = energy_threshold

        self.timeout = timeout
        self.examples = examples
        self.log_history = log
        if log:
            now = str(datetime.datetime.now())
            self.logf = "chat_history/" + now + ".jsonl"
            self.logfile = open(self.logf, "a")

        self.setup_system(**kwargs)

        # # print(f"ChatBot Init: initializing empty temporary directory {tmp_dir}")

        self.tmp_dir = tmp_dir

        # if os.path.isdir(self.tmp_dir):
        #     shutil.rmtree(self.tmp_dir)
        # os.mkdir(tmp_dir)

        if self.stream_audio:
            assert self.stream_msg, f"Can only stream audio if streaming text message also, currently."
            self.speak_listen_queue = queue.Queue()
            self.speak_thread = threading.Thread(target=self._speak_listen_worker)
            self.speak_thread.daemon = True
            self.speak_thread.start()

    def setup_system(self, system_messages: List[str] = ["You are a virtual assistant."]):
        self.messages = []
        # Anthropic doesnt have system messages, only a global system parameter
        # for line in system_messages:
        #     evaln = eval(line)
        #     self.messages += [evaln]
        self.sys_msg = ""
        for line in system_messages:
            evaln = eval(line)
            self.sys_msg += evaln["content"] + "\n"
        self.sys_msg = self.sys_msg[:-1]

        if self.log_history:
            self.logfile.writelines([str(line)+"\n" for line in self.messages])

    def post_process(self, r):
        """
        Splits response into text and command parts
        """
        parts = []
        # r = response.replace("\n", "")
        idx = 0
        is_command = False
        echo = False
        while idx != -1:
            idx = r.find("```")

            if idx == 0:
                # starts with a command
                is_command = True
                r = r[idx+3:]
                continue
            elif idx != -1:
                # backticks found
                if "ECHO" in r[:idx]:
                    echo = True
                start = r[:idx]
                r = r[idx+3:]

            else:
                # no backticks found
                start = r

            parts += [(start, is_command, echo)]
            is_command = not is_command
            echo = False

        return parts


    def listen_loop(self, activ: Trigger = Trigger.continuous) -> str:

        with RedirectStdStreams():
            with Spinner(f"Listening "):
                # Wait for keypress
                # keyboard.wait('ctrl+q')
                with sr.Microphone(device_index=1) as source:

                    self.R.adjust_for_ambient_noise(source)

                    audio = self.R.listen_from_keyword_on(source, timeout=self.timeout)
                    # audio = self.R.recognize_whisper(source, timeout=self.timeout)
                    # audio = self.R.listen(source, timeout=self.timeout)
                    # audio = self.R.record(source, duration=5)
                    # audio = self.R.listen(source, phrase_time_limit=self.timeout)

                    audio = audio.get_wav_data()

                    input_wav = self.tmp_dir + "input.wav"

                    tmp = open(input_wav, "wb")
                    tmp.write(audio)
                    tmp.close()

                    tmp = open(input_wav, "rb")

                    # wav_bytes = source.get_wav_data(convert_rate=16000)

                    transcript = openai_client.audio.transcriptions.create(model="whisper-1", file=tmp).text
                    # audio_array, sampling_rate = sf.read(wav_stream)
                    # audio_array = audio_array.astype(np.float32)
                    tmp.close()

        # alternative
        # Popen(["arecord -q -d 5 -f S16_LE"], shell=True).wait()

        return transcript

    def run(self) -> None:
        print(f"\n\t\t\t=========> CHAT with {self.name} <=========")
        user_input = ""
        got_return = False
        while True:
            try:
                if not got_return:
                    if not self.AUDIO_INPUT:
                        user_input = input(">> "+colors.cyan("USER")+ "(✏️  ): ")
                        if user_input.startswith("!"):
                            # execute command
                            proc = Popen([user_input[1:]], shell=True)
                            proc.wait()
                            continue
                    else:
                        print(">> "+colors.cyan("USER")+"(🎤 ): ", end="")
                        if self.stream_audio:
                            self.speak_listen_queue.put(0)
                        else:
                            user_input = self.listen_loop()
                            print(user_input)
                else:
                    print(user_input)

                if self.stream_audio:
                    self.transcribed_msg = None
                    while True:
                        # wait for self.transcribed_msg to be set by _speak_listen_worker
                        time.sleep(1)
                        if self.transcribed_msg is not None:
                            user_input = self.transcribed_msg
                            print(user_input)
                            break

                # Popen(["ffmpeg", "-i", tmp_in, "-af", '"highpass=f=200, lowpass=f=3000"', tmp_out)
                # look for special keywords
                commands_given = list(set(COMMANDS).intersection(set(user_input.split(" "))))
                if commands_given:
                    command = commands_given.pop()
                    if command == HELP:
                        print(f"Available Commands:")
                        for command in COMMANDS:
                            print(f"\t{command}\t: {COMMANDS[command]}")
                        continue
                    elif command == AUDIO_INPUT:
                        self.AUDIO_INPUT = not self.AUDIO_INPUT
                        print(f"Speech recognition on")
                        continue
                    elif command == AUDIO_OUTPUT:
                        self.AUDIO_OUTPUT = not self.AUDIO_OUTPUT
                        print(f"TTS using {self.tts_server} on")
                        continue
                    elif command == EXIT:
                        print("Goodbye.")
                        self.logfile.close()
                        break
                    elif command == ADD:
                        print("\n\tChat added to examples. Goodbye.")
                        self.logfile.close()
                        shutil.copy(self.logf, f"examples/{self.name}_{self.lang}.jsonl")
                        break
                else:
                    inp = {"role": "user", "content": user_input}

                    self.messages += [inp]

                    if self.log_history:
                        self.logfile.write(str(inp)+"\n")

                    # Make OPENAI API CALL
                    try:
                        if not self.stream_msg:
                            with Spinner(f"Thinking "):
                                response = anthropic_client.messages.create(
                                    model="claude-3-opus-20240229",
                                    system=self.sys_msg,
                                    max_tokens=1024,
                                    messages=self.messages
                                ).content[0].text
                        else:
                            # streaming message
                            response = ""
                            prev_delim = 0
                            print()
                            print(">> " + colors.red(self.name)+ ":"+"\n")
                            with anthropic_client.messages.stream(
                                    model="claude-3-opus-20240229",
                                    system=self.sys_msg,
                                    max_tokens=1024,
                                    messages=self.messages
                                ) as stream:
                                for text in stream.text_stream:
                                    if self.stream_audio:
                                        # speak individual sentences
                                        delims = re.compile(r"(!|\.|\?| \- |\: )")
                                        if delims.search(text):
                                            # delimiter found: speak in background
                                            self.speak_listen_queue.put(response[prev_delim:])
                                            prev_delim = len(response)
                                    response += text
                                    print(colors.magenta(text), end="", flush=True)

                                if self.stream_audio:
                                    # speak last sentence
                                    self.speak_listen_queue.put(response[prev_delim:])
                            print()

                        response_parts = self.post_process(response)

                        if not self.stream_msg:
                            print()
                            print(">> " + colors.red(self.name)+ ":"+"\n")

                        self.messages += [{"role": "assistant", "content": ""}] # initialize assistant response
                    except KeyboardInterrupt:
                        print("\n<Thought interrupted by user>")
                        self.messages += [{"role": "assistant", "content": "<Interrupted by user.>"}]
                        continue

                    got_return = False
                    command_count = 0
                    for i, (part, is_command, echo) in enumerate(response_parts):

                        # iteratively add response to history
                        self.messages[-1]["content"] = self.messages[-1]["content"] + "\n" + part

                        if is_command:
                            command_count += 1

                            if part.startswith("bash"):
                                part = part[4:]
                            print(colors.red(f" {self.name}@ideas~$ {part}"))

                            proc = Popen([CD + " && " + part], stderr=PIPE, shell=True)
                            proc.wait()
                            err = proc.stderr.read().decode()

                            if proc.stdout is not None:
                                out = proc.stdout.read().decode()
                                print(out)
                            else:
                                out = None

                            print(err)

                            if echo:
                                user_input = f">> "+colors.blue("AUTO")+f": Your command returned:\n{out}"
                                break

                            if err:
                                got_return = True
                                user_input = f">> "+colors.blue("AUTO")+f": Thanks, but the {ordinal(command_count)} command in your reply returned the following error:\n{err}"
                            elif out:
                                got_return = True
                                user_input = f">> "+colors.blue("AUTO")+f": Your command returned: {out}."
                            else:
                                got_return = False

                        else:
                            # message
                            if not self.stream_msg:
                                print(colors.magenta(f"{part}"))

                            if self.AUDIO_OUTPUT and part and not self.stream_audio:
                                self.speak(part)

                        # stop executing the rest of the commands/messages
                        if got_return:
                            break

                    if self.log_history:
                        self.logfile.write(str(self.messages[-1])+"\n")

                # if self.stream_audio: self.speak_listen_queue.join()

            except KeyboardInterrupt as KI:
                print("Interrupting ...")
                got_return = False
                # continue
                raise

    def _speak_listen_worker(self):
        # for audio streaming
        while True:
            sentence = self.speak_listen_queue.get()
            if sentence != 0:
                # speak
                self.speak(sentence)
            else:
                # listen
                self.transcribed_msg = self.listen_loop()
            self.speak_listen_queue.task_done()

    def speak(self, msg):
        # if DEBUG: print(f"Attempting to speak msg '{msg}'")
        if self.tts_server == "google":
            tmp_response = self.tmp_dir + "tmp_out.mp3"
            msg = msg.replace('"', "'")
            with Spinner(f"Generating Speech"):
                proc = Popen([f'gtts-cli "{msg}" -l {self.lang} --output {tmp_response}'], shell=True).wait()
            reply = self.tmp_dir + "out.mp3"
            with Spinner(f"Speaking"):
                Popen([f"ffmpeg -i {tmp_response} -loglevel quiet -filter:a 'atempo=1.25' -vn {reply}"], shell=True).wait()
            playsound.playsound(reply)
            os.remove(reply)
        elif self.tts_server == "eleven":
            eleven_labs_speech(
                msg,
                voice_index=1,
                eleven_labs_api_key=eleven_labs_api_key
            )
        elif self.tts_server == "openai":
            # TODO
            tmp_response = self.tmp_dir + "tmp_out.mp3"
            response = openai_client.audio.speech.create(
                model="tts-1",
                voice="nova",
                input=msg
            )
            response.stream_to_file(tmp_response)

            playsound.playsound(tmp_response)
            # Popen(["mpg123", "-q", tmp_response])

            os.remove(tmp_response)
        else:
            raise NotImplementedError(self.tts_server)



def main():


    # TODO argparse/config

    lang = "en"  # "en", "de"
    name = "Opus"
    thresh = 50
    tts = "openai" # google, eleven, openai

    if not os.path.exists(f"examples/{name}_{lang}.jsonl"):
        p = "instructions"
    else:
        p = "examples"

    instruction_file = f"{p}/{name}_{lang}.jsonl"

    with open(instruction_file, "r") as instructions:
        system = instructions.readlines()
        system = [l[:-1] for l in system]

    Bot = ChatBot(
        lang=lang,
        system_messages=system,
        energy_threshold=thresh,
        log=True,
        name=name,
        tts_server=tts
    )

    # now = str(datetime.datetime.now())
    # logfile = "chat_history/"+ now + ".txt"
    # sys.stdout = Logger(logfile)

    Bot.run()

if __name__ == "__main__":
    main()
