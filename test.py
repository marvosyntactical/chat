import os
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


messages = [
    {"role": "user", "content": "hello world"}
]

response = client.chat.completions.create(
  model="gpt-3.5-turbo",
  # model="gpt-4",
  messages=messages,
)

print(response)

