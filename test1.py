import pyaudio
p = pyaudio.PyAudio()

print("Let's reveal the mysteries of your audio devices:\n")
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    print(f"Index {i}: {info['name']}")
