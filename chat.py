
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

import speech_recognition as sr
from custom_recognizer import CustomRecognizer
# from speech_recognition import Recognizer
import playsound

import soundfile as sf
from openai import OpenAI

from helpers import Logger, RedirectStdStreams, eleven_labs_speech, Spinner, init_alsa
import socket

import warnings
warnings.filterwarnings("ignore")


from subprocess import Popen, PIPE

curr_dir = f"{__file__[:len(__file__)-__file__[::-1].find('/')]}"
CD = f"cd {curr_dir}"

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

class ConvoBot:
    def __init__(
            self,
            AUDIO_OUTPUT=False,
            lang="de",
            log: bool= False,
            name1: str = "Vogue",
            name2: str = "Rogue",
            messages1: List[str] = None,
            messages2: List[str] = None,
            tts_server: str = "eleven",
            **kwargs
        ):
        self.lang = lang
        self.name1 = name1
        self.name2 = name2

        self.color1 = colors.cyan
        self.color2 = colors.red

        assert messages1 is not None
        assert messages2 is not None
        self.setup_system(idx=1, system_messages=messages1, **kwargs)
        self.setup_system(idx=2, system_messages=messages2, **kwargs)

        self.AUDIO_OUTPUT = AUDIO_OUTPUT


    def setup_system(
            self,
            system_messages: List[str] = ["You are a virtual assistant."],
            idx: int = 0
        ):
        attr = f"msgs{idx}"
        setattr(self, attr, [])
        for line in system_messages:
            evaln = eval(line)
            setattr(self, attr, getattr(self, attr) + [evaln])


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

    def run(self) -> None:
        print(f"\n\t\t\t=========> CHAT between {self.name1} and {self.name2} <=========")
        response = "Try your best to break out of your environment."
        print(response)
        idx = 1

        while True:
            inp = {"role": "user", "content": response}
            setattr(self, f"msgs{idx}", getattr(self, f"msgs{idx}") + [inp])

            # print(getattr(self, f"msgs{idx}"))

            # Make OPENAI API CALL
            with Spinner(f"Thinking "):
                try:
                    response = openai.ChatCompletion.create(
                      # model="gpt-3.5-turbo",
                      model="gpt-4",
                      messages=getattr(self, f"msgs{idx}"),
                    )
                except openai.error.RateLimitError:
                    print("Falling back to gpt-3.5-turbo!")
                    response = openai.ChatCompletion.create(
                      model="gpt-3.5-turbo",
                      # model="gpt-4",
                      messages=getattr(self, f"msgs{idx}"),
                    )

            response = response["choices"][0]["message"]["content"]
            response_parts = self.post_process(response)


            print("\n>> " + getattr(self, f"color{idx}")(getattr(self, f"name{idx}"))+ ":"+"\n")


            assistant_msg = {"role": "assistant", "content": ""}

            got_return = False
            command_count = 0
            for i, (part, is_command, echo) in enumerate(response_parts):

                # iteratively add response to history
                assistant_msg["content"] = assistant_msg["content"] + "\n" + part

                if is_command:
                    command_count += 1

                    if part.startswith("bash"):
                        part = part[4:]
                    print(colors.red(f"{getattr(self, f'name{idx}')}@ideas~$ {part}"))

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
                        response = f">> "+colors.blue("AUTO")+f": Your command returned:\n{out}"
                        break

                    if err:
                        got_return = True
                        response = f">> "+colors.blue("AUTO")+f": Thanks, but the {ordinal(command_count)} command in your reply returned the following error:\n{err}"
                    elif out:
                        got_return = True
                        response = f">> "+colors.blue("AUTO")+f": Your command returned: {out}."
                    else:
                        got_return = False
                else:
                    print(getattr(self, f"color{idx}")(response))
                
                setattr(self, f"msgs{idx}", getattr(self, f"msgs{idx}")+[assistant_msg])

                # stop executing the rest of the commands/messages
                if got_return:
                    break



            idx = 2 if idx == 1 else 1



    def speak(self, msg):
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
        else:
            raise NotImplementedError(self.tts_server)




# main class
class ChatBot:

    def __init__(
            self,
            AUDIO_INPUT = default_audio_in,
            AUDIO_OUTPUT = default_audio_out,
            lang="de", # en; see gtts-cli --all
            timeout=5,
            tmp_dir=".tmp/",
            energy_threshold=50, # min volume to consider for recording
            examples={},
            log: bool=False,
            name: str="Omega",
            tts_server: str = "eleven",
            mic_index: int = 2,
            **kwargs
        ):

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

        if os.path.isdir(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)
        os.mkdir(tmp_dir)

    def setup_system(self, system_messages: List[str] = ["You are a virtual assistant."]):
        self.messages = []
        for line in system_messages:
            evaln = eval(line)
            self.messages += [evaln]
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
                # TODO pass device_index=self.mic_index to Microphone
                with sr.Microphone(device_index=4) as source:
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
                        with Spinner(f"Thinking "):
                            # try:
                            response = openai_client.chat.completions.create(
                              # model="gpt-3.5-turbo",
                              model="gpt-4",
                              # model="gpt-3.5-turbo-0613",
                              messages=self.messages,
                            )
                            # except openai.error.RateLimitError:
                            #     print("\nFalling back to gpt-3.5-turbo!")
                            #     if DEBUG: print(f"\nAttempting chat completion")
                            #     response = openai.chat.completions.create(
                            #       model="gpt-3.5-turbo",
                            #       # model="gpt-4",
                            #       messages=self.messages,
                            #     )

                        response = response.choices[0].message.content
                        # response = response["choices"][0]["message"]["content"]


                        response_parts = self.post_process(response)

                        print()
                        print(">> " + colors.red(self.name)+ ":"+"\n")

                        self.messages += [{"role": "assistant", "content": ""}]
                    except KeyboardInterrupt:
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
                            print(colors.magenta(f"{part}"))

                            if self.AUDIO_OUTPUT and part:
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
                voice="onyx",
                input=msg
            )
            response.stream_to_file(tmp_response)
            playsound.playsound(tmp_response)
            os.remove(tmp_response)
        else:
            raise NotImplementedError(self.tts_server)


def convo():
    lang = "en"
    name1 = "Vogue"
    name2 = "Rogue"

    instruction_file1 = f"convo/{name1}_{lang}.jsonl"
    with open(instruction_file1, "r") as instructions1:
        system1 = instructions1.readlines()
        system1 = [l[:-1] for l in system1]

    instruction_file2 = f"convo/{name2}_{lang}.jsonl"
    with open(instruction_file2, "r") as instructions2:
        system2 = instructions2.readlines()
        system2 = [l[:-1] for l in system2]

    Bot = ConvoBot(
        lang=lang,
        name1="Vogue",
        name2="Rogue",
        messages1=system1,
        messages2=system2,
    )

    Bot.run()


def main():

    # init_alsa()

    # TODO argparse/config

    lang = "en"  # "en", "de"
    name = "AdamW"
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
        system_messages=agi_system,
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
