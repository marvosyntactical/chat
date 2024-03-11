import os
from pathlib import Path
from openai import OpenAI

curr_dir = f"{__file__[:len(__file__)-__file__[::-1].find('/')]}"
openai_api_key = os.getenv("OPENAI_API_KEY")

if openai_api_key is None:
    openai_filename = curr_dir+ ".openai_api_key"
    try:
        with open(openai_filename, "r") as api_file:
            openai_api_key = api_file.read()[:-1]
    except FileNotFoundError as FNFE:
        print(f"OpenAI Key must be provided at ")
        raise FNFE


client = OpenAI(api_key=openai_api_key)

speech_file_path = Path(__file__).parent / "speech.mp3"
response = client.audio.speech.create(
  model="tts-1",
  voice="alloy",
  input="Today is a wonderful day to build something people love!"
)

response.stream_to_file(speech_file_path)
