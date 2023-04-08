import os
import openai
from subprocess import Popen

openai.api_key = os.getenv("OPENAI_API_KEY")

prompt = "a blonde soldier dancing in an enactment of  swan lake  in the style of greg rutkowski"

response = openai.Image.create(
          prompt=prompt,
          n=1,
          size="1024x1024"
)
print(response)
# image_url = response['data'][0]['url']
# Popen([f"firefox {image_url}"], shell=True)
