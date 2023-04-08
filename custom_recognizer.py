from typing import Optional, List
import os
import math
import collections
import time

import soundfile as sf
import io

import torch
import numpy as np

from speech_recognition import *

__all__ = ["CustomRecognizer"]

class CustomRecognizer(Recognizer):

    def listen_from_keyword_on(self, source, timeout=None, phrase_time_limit=None, keyword_model= None):
        # assert False, "got here"
        assert isinstance(source, AudioSource), "Source must be an audio source"
        assert source.stream is not None, "Audio source must be entered before listening, see documentation for ``AudioSource``; are you using ``source`` outside of a ``with`` statement?"
        assert self.pause_threshold >= self.non_speaking_duration >= 0

        seconds_per_buffer = float(source.CHUNK) / source.SAMPLE_RATE
        pause_buffer_count = int(math.ceil(self.pause_threshold / seconds_per_buffer))  # number of buffers of non-speaking audio during a phrase, before the phrase should be considered complete
        phrase_buffer_count = int(math.ceil(self.phrase_threshold / seconds_per_buffer))  # minimum number of buffers of speaking audio before we consider the speaking audio a phrase
        non_speaking_buffer_count = int(math.ceil(self.non_speaking_duration / seconds_per_buffer))  # maximum number of buffers of non-speaking audio to retain before and after a phrase

        # read audio input for phrases until there is a phrase that is long enough
        elapsed_time = 0  # number of seconds of audio read
        buffer = b""  # an empty buffer means that the stream has ended and there is no data left to read
        while True:
            frames = collections.deque()

            if keyword_model is None:
                # store audio input until the phrase starts
                while True:
                    # handle waiting too long for phrase by raising an exception
                    elapsed_time += seconds_per_buffer
                    if timeout and elapsed_time > timeout:
                        raise WaitTimeoutError("listening timed out while waiting for phrase to start")

                    buffer = source.stream.read(source.CHUNK)
                    if len(buffer) == 0: break  # reached end of the stream
                    frames.append(buffer)
                    if len(frames) > non_speaking_buffer_count:  # ensure we only keep the needed amount of non-speaking buffers
                        frames.popleft()

                    # detect whether speaking has started on audio input
                    energy = audioop.rms(buffer, source.SAMPLE_WIDTH)  # energy of the audio signal
                    if energy > self.energy_threshold: break

                    # dynamically adjust the energy threshold using asymmetric weighted average
                    if self.dynamic_energy_threshold:
                        damping = self.dynamic_energy_adjustment_damping ** seconds_per_buffer  # account for different chunk sizes and rates
                        target_energy = energy * self.dynamic_energy_ratio
                        self.energy_threshold = self.energy_threshold * damping + target_energy * (1 - damping)
            else:
                # let local keyword model recognize a keyword

                # read audio input until the keyword is said
                buffer, delta_time = self.wait_for_keyword(source, keyword_model, timeout)
                elapsed_time += delta_time
                if len(buffer) == 0: break  # reached end of the stream
                frames.append(buffer)

            # read audio input until the phrase ends
            pause_count, phrase_count = 0, 0
            phrase_start_time = elapsed_time
            while True:
                # handle phrase being too long by cutting off the audio
                elapsed_time += seconds_per_buffer
                if phrase_time_limit and elapsed_time - phrase_start_time > phrase_time_limit:
                    break

                buffer = source.stream.read(source.CHUNK)
                if len(buffer) == 0: break  # reached end of the stream
                frames.append(buffer)
                phrase_count += 1

                # check if speaking has stopped for longer than the pause threshold on the audio input
                energy = audioop.rms(buffer, source.SAMPLE_WIDTH)  # unit energy of the audio signal within the buffer
                if energy > self.energy_threshold:
                    pause_count = 0
                else:
                    pause_count += 1
                if pause_count > pause_buffer_count:  # end of the phrase
                    break

            # check how long the detected phrase is, and retry listening if the phrase is too short
            phrase_count -= pause_count  # exclude the buffers for the pause before the phrase
            if phrase_count >= phrase_buffer_count or len(buffer) == 0: break  # phrase is long enough or we've reached the end of the stream, so stop listening

        # obtain frame data
        for i in range(pause_count - non_speaking_buffer_count): frames.pop()  # remove extra non-speaking frames at the end
        frame_data = b"".join(frames)

        return AudioData(frame_data, source.SAMPLE_RATE, source.SAMPLE_WIDTH)

    def wait_for_keyword(self, source, keyword_model, timeout=None):
        # load keyword library (NOT THREAD SAFE)

        # keyword_model.SetAudioGain(1.0)
        # keyword_model.SetSensitivity(",".join(["0.4"] * len(keyword_key_word_files)).encode())
        kw_sample_rate = keyword_model.sample_rate

        """
        Specs while training keyword model:
        * sampling rate
        """

        elapsed_time = 0
        seconds_per_buffer = float(source.CHUNK) / source.SAMPLE_RATE
        resampling_state = None

        # buffers capable of holding 5 seconds of original audio
        five_seconds_buffer_count = int(math.ceil(5 / seconds_per_buffer))
        # buffers capable of holding 0.5 seconds of resampled audio
        half_second_buffer_count = int(math.ceil(0.5 / seconds_per_buffer))
        frames = collections.deque(maxlen=five_seconds_buffer_count)
        resampled_frames = collections.deque(maxlen=half_second_buffer_count)
        # keyword check interval
        check_interval = 0.05
        last_check = time.time()
        while True:
            elapsed_time += seconds_per_buffer
            if timeout and elapsed_time > timeout:
                raise WaitTimeoutError("listening timed out while waiting for keyword to be said")

            buffer = source.stream.read(source.CHUNK)
            if len(buffer) == 0:
                break # reached end of the stream
            frames.append(buffer)

            # resample audio to the required sample rate
            resampled_buffer, resampling_state = audioop.ratecv(buffer, source.SAMPLE_WIDTH, 1, source.SAMPLE_RATE, kw_sample_rate, resampling_state)
            resampled_frames.append(resampled_buffer)

            if time.time() - last_check > check_interval:
                # run keyword detection on the resampled audio
                print("passing keyword to model ...")
                inp = b"".join(resampled_frames)
                print(inp)
                inp = bytearray(inp)
                print(inp)
                arr = torch.Tensor(np.array(inp, dtype=np.float32))
                print(arr)
                inp = torch.stack([arr, arr], dim=0).unsqueeze(0)

                keyword_result = keyword_model(inp)
                print(f"model decided on class {keyword_result}")
                if keyword_result > 0:
                    break  # wake word found !
                resampled_frames.clear()
                last_check = time.time()

        return b"".join(frames), elapsed_time
