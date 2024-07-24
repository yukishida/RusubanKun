import config
import socket
import threading
import queue
from flask import Flask, request, abort

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage
)

#------------------------設定----------------------------
PORT = xxxx #ソケット通信で使用するポート番号
flask_port = xxxx #Flask用のポート番号
SERVER = '0.0.0.0' #全てのIPアドレスを許可
set_timeout = 5
#--------------------------------------------------------

HEADER = 64
ADDR = (SERVER, PORT)
FORMAT = 'utf-8'
DISCONNECT_MESSAGE = "!DISCONNECT"

message_queue = queue.Queue()
message_queue_activate = False


server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(ADDR)

def handle_client(conn, addr):
    print(f"[NEW CONNECTION] {addr} connected.")

    global message_queue_activate
    connected = True
    while connected:
        msg_length = conn.recv(HEADER).decode(FORMAT)
        if msg_length:
            
            msg_length = int(msg_length)
            msg = conn.recv(msg_length).decode(FORMAT)
            if msg == "インターホンが押されました":
                message_queue_activate = True
                print(f"[{addr}] {msg}")
                line_send_message('U9b4e512183ea49b16d498e3a57310a1f', msg)

            if msg == "timeout":
                print('timeout')
                message_queue_activate = False

            if msg == DISCONNECT_MESSAGE:
                connected = False
                message_queue_activate = False
                break


            try:
                if message_queue_activate:
                    send_to_client = message_queue.get(timeout=set_timeout)
                    conn.send(send_to_client.encode(FORMAT))
                    message_queue_activate = False
            except queue.Empty:
                continue
    conn.close()
    print('close')


def start():
    server.listen()
    print(f"[LISTENING] Server is listening on {SERVER}")
    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_client, args=(conn, addr))
        thread.start()
        print(f"[ACTIVE CONNECTIONS] {threading.activeCount() - 1}")
        
def start_server():
    start()


app = Flask(__name__)

line_bot_api = LineBotApi(config.LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(config.LINE_CHANNEL_SECRET)

@app.route("/callback", methods=['POST'])
def callback():

    signature = request.headers['X-Line-Signature']

    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)#メッセージが送られた際の操作
def handle_message(event):
    if event.reply_token == "00000000000000000000000000000000": #リプライトークンが無効な場合、終了
        return
    req  = request.json["events"][0]
    userMessage = req["message"]["text"]
    
    user_id = event.source.user_id
    message_text = event.message.text
    print(f'{user_id}から「{message_text}」を受け取りました!')

    if message_queue_activate:
        message_queue.put(message_text)
        print(message_queue)

def line_send_message(user_id, message):
    line_bot_api.push_message(user_id, TextSendMessage(text = message))

if __name__ == "__main__":
    server_thread = threading.Thread(target=start_server)
    server_thread.start()
    app.run(port=flask_port) #Flask用のポート
