
import os
import shutil
import sys

from enum import Enum
import colors
import io
import time
import datetime
import json
from typing import List
from pprint import pprint

import speech_recognition as sr
from custom_recognizer import CustomRecognizer
import playsound

import numpy as np
import soundfile as sf
import openai
import tqdm

from helpers import Logger, RedirectStdStreams
import socket

import warnings
warnings.filterwarnings("ignore")


from subprocess import Popen, PIPE

cur_dir = f"{__file__[:len(__file__)-__file__[::-1].find('/')]}"
CD = f"cd {cur_dir}"

api_key = os.getenv("OPENAI_API_KEY")

if api_key is None:
    try:
        with open(cur_dir+ ".api_key", "r") as api_file:
            api_key = api_file.read()[:-1]
    except FileNotFoundError as FNFE:
        raise FNFE

openai.api_key = api_key

hostname = socket.gethostname()


DEBUG = 1

# commands
AUDIO_INPUT = "/sr"
AUDIO_OUTPUT = "/tts"
EXIT = "/quit"
ADD = "/add"
HELP = "/help"

WORKSPACE = cur_dir + "workspace/"
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
            AUDIO_INPUT = False,
            AUDIO_OUTPUT = False,
            lang="de", # en; see gtts-cli --all
            timeout=None,
            tmp_dir=".tmp/",
            energy_threshold=100, # min volume to consider for recording
            examples={},
            log: bool=False,
            name: str="Omega",
            **kwargs
            ):

        self.lang = lang
        self.AUDIO_INPUT = AUDIO_INPUT
        self.AUDIO_OUTPUT = AUDIO_OUTPUT
        self.name = name

        self.R = CustomRecognizer()
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

        if os.path.isdir(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)
        os.mkdir(tmp_dir)

    def setup_system(self, system_messages: List[str] = ["You are a virtual assistant."]):
        self.messages = [
            eval(line) for line in system_messages
        ]
        if self.log_history:
            self.logfile.writelines([str(line)+"\n" for line in self.messages])

    def post_process(self, response):
        """
        Splits response into text and command parts
        """
        parts = []
        r = response.replace("\n", "")
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


    def listen_loop(self, activ: Trigger = Trigger.continuous, mic_index: int=1) -> str:

        # devnull = open(os.devnull, 'w')

        # with RedirectStdStreams(stdout=devnull, stderr=devnull):
        with sr.Microphone(device_index=mic_index) as source:
            self.R.adjust_for_ambient_noise(source)

            audio = self.R.listen_from_keyword_on(source, timeout=self.timeout)

            audio = audio.get_wav_data()

            input_wav = self.tmp_dir + "input.wav"

            tmp = open(input_wav, "wb")
            tmp.write(audio)
            tmp.close()

            tmp = open(input_wav, "rb")

            # wav_bytes = source.get_wav_data(convert_rate=16000)

            transcript = openai.Audio.transcribe("whisper-1", tmp)["text"]
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
                print()
                if not got_return:
                    if not self.AUDIO_INPUT:
                        user_input = input(">> "+colors.cyan("USER")+ "(✏️  ): ")
                        if user_input.startswith("!"):
                            # execute command
                            proc = Popen([user_input[1:]], shell=True)
                            proc.wait()
                            continue
                    else:
                        print(">> "+colors.cyan("USER")+"(🎤 ): ")

                        user_input = self.listen_loop()
                        print(user_input)
                else:
                    print(user_input)


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
                        continue
                    elif command == AUDIO_OUTPUT:
                        self.AUDIO_OUTPUT = not self.AUDIO_OUTPUT
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
                        response = openai.ChatCompletion.create(
                          # model="gpt-3.5-turbo",
                          model="gpt-4",
                          messages=self.messages,
                        )
                    except openai.error.RateLimitError:
                        response = openai.ChatCompletion.create(
                          model="gpt-3.5-turbo",
                          # model="gpt-4",
                          messages=self.messages,
                        )

                    response = response["choices"][0]["message"]["content"]


                    response_parts = self.post_process(response)

                    print()
                    print(">> " + colors.red(self.name)+ ":"+"\n")

                    self.messages += [{"role": "assistant", "content": ""}]

                    got_return = False
                    for i, (part, is_command, echo) in enumerate(response_parts):

                        # iteratively add response to history
                        self.messages[-1]["content"] = self.messages[-1]["content"] + "\n" + part

                        if is_command:
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
                                user_input = f">> "+colors.blue("AUTO")+f": Thanks, but the {ordinal(i)} command in your reply returned the following error:\n{err}"
                            elif out:
                                got_return = True
                                user_input = f">> "+colors.blue("AUTO")+f": Your command returned: {out}."
                            else:
                                got_return = False

                        else:
                            # message
                            print(colors.magenta(f"{part}"))

                            if self.AUDIO_OUTPUT:
                                self.speak(part)

                        # stop executing the rest of the commands/messages
                        if got_return:
                            break

                    if self.log_history:
                        self.logfile.write(str(self.messages[-1])+"\n")

            except KeyboardInterrupt as KI:
                print("Interrupting ...")
                got_return = False
                # continue
                raise


    def speak(self, msg):
        tmp_response = self.tmp_dir + "tmp_out.mp3"
        msg = msg.replace('"', "'")
        proc = Popen([f'gtts-cli "{msg}" -l {self.lang} --output {tmp_response}'], shell=True).wait()
        reply = self.tmp_dir + "out.mp3"
        Popen([f"ffmpeg -i {tmp_response} -loglevel quiet -filter:a 'atempo=1.25' -vn {reply}"], shell=True).wait()
        playsound.playsound(reply)
        os.remove(reply)



def main():

    lang = "de"  # "en", "de"
    name = "Omega"

    if not os.path.exists(f"examples/{name}_{lang}.jsonl"):
        p = "instructions"
    else:
        p = "examples"

    with open(f"{p}/{name}_{lang}.jsonl", "r") as instructions:
        agi_system = instructions.readlines()
        agi_system = [l[:-1] for l in agi_system]

    # print(agi_system)

    Bot = ChatBot(
        lang=lang,
        system_messages=agi_system,
        log=True,
    )

    # now = str(datetime.datetime.now())
    # logfile = "chat_history/"+ now + ".txt"
    # sys.stdout = Logger(logfile)

    Bot.run()

if __name__ == "__main__":
    main()
