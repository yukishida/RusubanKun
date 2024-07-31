import pyaudio
import wave

FORMAT = pyaudio.paInt16
CHANNELS = 1
OUTPUT_FILENAME = "intercom.wav"

def record(p, stream, record_seconds, RATE, CHUNK):
    print("Recording...")
    frames = []
    for i in range(0, int(RATE / CHUNK * record_seconds)):
        data = stream.read(CHUNK)
        frames.append(data)
    print("Finished recording.")

    # stream.stop_stream()
    # stream.close()
    # p.terminate()

    with wave.open(OUTPUT_FILENAME, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))

    print(f"Saved to {OUTPUT_FILENAME}")