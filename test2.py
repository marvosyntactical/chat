import speech_recognition as sr

# Duration of recording
RECORD_SECONDS = 5

# Initialize recognizer
r = sr.Recognizer()

# Select the default microphone as the audio source
with sr.Microphone() as source:
    print("Recording for 5 seconds. Start speaking...")
    # Adjust for ambient noise to improve accuracy
    r.adjust_for_ambient_noise(source, duration=1)
    # Listen to the source for the duration of RECORD_SECONDS
    audio_data = r.record(source, duration=RECORD_SECONDS)
    print("Recording stopped.")

# Now, you could do something with the audio_data, like save it or recognize it.
# Saving the recording to a WAV file
file_name = "recorded_audio.wav"
with open(file_name, "wb") as f:
    f.write(audio_data.get_wav_data())
print(f"Audio recording saved as {file_name}")

# If you want to test recognizing what was said immediately, you can do this:
try:
    print("You said: " + r.recognize_google(audio_data))
except sr.UnknownValueError:
    print("Google Speech Recognition could not understand audio")
except sr.RequestError as e:
    print(f"Could not request results from Google Speech Recognition service; {e}")

