import pyaudio
import wave
import numpy as np
import pandas as pd
import socket
import intercom_record
import time
import pigpio

#------------------------設定----------------------------
intercom_recording_time = 2 #インターホンを認識する時間(秒)
input_device_index = 1 #マイクのインデックス番号
RATE = 44100 #マイクのサンプリングレート
HOST = 'xxx.xxx.xxx.xxx' #サーバーのipアドレス

#音声ファイルの指定
start_recording_voice = "sound/recording_start_voice.wav" #録音開始の音声
start_recording_sound = "sound/recording_start_sound.wav" #録音開始の効果音
recording_complete_sound = "sound/recording_ok.wav" #録音成功の音声
recording_error_sound = "sound/re-record.wav" #録音失敗の音声
leave_the_package_sound = "sound/at_door.wav" #置き配指定の音声

SERVO_PIN = 18 #サーボモータを接続するピン
#--------------------------------------------------------

HEADER = 64
PORT = 5050
BUFSIZE = 4096
SOCKET_FORMAT = 'utf-8'
DISCONNECT_MESSAGE = "!DISCONNECT"

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.settimeout(5)

client.connect((HOST,PORT))

file_name = "intercom.wav"
threshold = 5.0e7
threshold2 = 5

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1

rng = int(RATE / CHUNK * intercom_recording_time)

pi = pigpio.pi()
def set_angle(angle):
    assert 0 <= angle <= 180,'角度は0から180の間でなければなりません'

    pulse_width = (angle / 180) * (2500 - 500) + 500

    pi.set_servo_pulsewidth(SERVO_PIN, pulse_width)

def send(msg):
    message = msg.encode(SOCKET_FORMAT)
    msg_length = len(message)
    send_length = str(msg_length).encode(SOCKET_FORMAT)
    send_length += b' ' * (HEADER - len(send_length))
    client.send(send_length)
    client.send(message)

def setup():
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    input_device_index = input_device_index,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK,
                    )
    return p, stream

def get_freq_indices():
    start = 0
    wf = wave.open(file_name, "rb")
    data = np.frombuffer(wf.readframes(wf.getnframes()), dtype='int16')
    wf.close()

    data = data[start:start+rng * CHUNK]
    fft_data = np.abs(np.fft.fft(data))
    freqList = np.fft.fftfreq(data.shape[0], d=1.0/RATE)

    df = pd.DataFrame(dict(freq = freqList, amp = fft_data))
    df = df[df['freq']>500]
    df = df[df['amp']>0.5e7]
    return list(df.index)

def collect_data(stream, rng, CHUNK):
    frames = []
    for i in range(rng):
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)
    d = np.frombuffer(b''.join(frames), dtype='int16')
    return d

def calc_FFTamp(frames, freq_indices, freq_indices2):
    fft_data = np.abs(np.fft.fft(frames))
    amp, amp2 = 0, 0
    for i in freq_indices:
        amp += fft_data[i]
    for i in freq_indices2:
        amp2 += fft_data[i]
    return amp, amp2

def recording():
    retry = True
    while retry:
        time.sleep(1)
        print('録音します')
        play_sound(start_recording_voice)
        play_sound(start_recording_sound)
        intercom_record.record(p, stream, intercom_recording_time, RATE, CHUNK)
        d = collect_data(stream, rng, CHUNK)
        freq_indices2 = [ f*2 for f in get_freq_indices() ]
        amp, amp2 = calc_FFTamp(d, get_freq_indices(), freq_indices2)
        if amp == 0:
            retry = True
            print('録音やり直し')
            play_sound(recording_error_sound)
        else:
            retry = False
            print('録音完了')
            play_sound(recording_complete_sound)

def play_sound(filename):
    wf = wave.open(filename, "rb")
    p = pyaudio.PyAudio()
    stream = p.open(format=p.get_format_from_width(wf.getsampwidth()), channels=wf.getnchannels(), rate=wf.getframerate(), output=True)
    data = wf.readframes(CHUNK)

    while data:
        stream.write(data)
        data = wf.readframes(CHUNK)

    stream.stop_stream()
    stream.close()
    p.terminate()

if __name__ == '__main__':
    p, stream = setup()
    recording()

    print('Watching...')
    try:
        while True:
            d = collect_data(stream, rng, CHUNK)
            freq_indices2 = [ f*2 for f in get_freq_indices() ]
            amp, amp2 = calc_FFTamp(d, get_freq_indices(), freq_indices2)
            if (amp > threshold)&(amp/amp2 > threshold2):
                print('Someone is at the door.')
                send("インターホンが押されました")

                try:
                    recv_msg = client.recv(2048).decode(SOCKET_FORMAT)
                    if(recv_msg == "置き配"):
                        print('置き配')
                        set_angle(30)
                        time.sleep(0.5)
                        set_angle(0)
                        time.sleep(0.5)
                        play_sound(leave_the_package_sound)

                except socket.timeout:
                    print('timeout')
                    send("timeout")
                print('Keep watching...')

    except KeyboardInterrupt:
        print('You terminated the program.\nThe program ends.')
        send(DISCONNECT_MESSAGE)
        stream.stop_stream()
        stream.close()
        p.terminate()
