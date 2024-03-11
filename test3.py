import pyaudio
import wave
import playsound
import os

# Audio recording parameters
FORMAT = pyaudio.paInt16  # Audio format (16-bit PCM)
CHANNELS = 1  # Number of audio channels (1 for mono, 2 for stereo)
RATE = 44100  # Sample rate
CHUNK = 1024  # Frames per buffer
RECORD_SECONDS = 5  # Duration of recording
WAVE_OUTPUT_FILENAME = "output.wav"  # Output file name
if os.path.isfile(WAVE_OUTPUT_FILENAME):
    print(f"Playing sound {WAVE_OUTPUT_FILENAME}")
    playsound.playsound(WAVE_OUTPUT_FILENAME)

DEVICE_INDEX = 4


# Initialize PyAudio
p = pyaudio.PyAudio()

# Open stream
stream = p.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    frames_per_buffer=CHUNK,
    input_device_index=DEVICE_INDEX
)

print("Recording...")

frames = []

# Start recording
for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
    data = stream.read(CHUNK)
    frames.append(data)

print("Finished recording.")

# Stop and close the stream
stream.stop_stream()
stream.close()
# Terminate the PortAudio interface
p.terminate()

# Save the recorded data as a WAV file
wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
wf.setnchannels(CHANNELS)
wf.setsampwidth(p.get_sample_size(FORMAT))
wf.setframerate(RATE)
wf.writeframes(b''.join(frames))
wf.close()

