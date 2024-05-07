import eventlet
import socketio
import random
import uuid

from .utils import *
from .constants import *
from .classes import *

sv_host = ''
sv_port = 3001
sv_cors = ['http://localhost:3000']

sio = socketio.Server(cors_allowed_origins=sv_cors)
app = socketio.WSGIApp(sio, static_files={
    '/': {'content_type': 'text/html', 'filename': 'index.html'}
})

userdict = {}
roomdict = {}
codedict = {}

usercount = 0
clearvotes = 0

# generates a random unique room code
def gen_room_code(min_length:int=4):
    """generates a random unique room code"""
    code = ''
    lastchar = len(ROOMCODE_CHARS)-1
    while len(code) < min_length or code in roomdict:
        code += ROOMCODE_CHARS[random.randint(0, lastchar)]
    return code

# sends a chat message to all connected users
def chat_all(text:str, type:int=MSG_SYSINFO):
    """sends a chat message to all connected users"""
    msgdict = {
        "timestamp": 0,
        "variant": type,
        "content": text
    }

    sio.emit("msg_broadcast", data=msgdict);

@sio.event
def connect(sid, environ, auth):
    global usercount, clearvotes
    usercount += 1
    print('> connect: ', sid, " auth: ", auth)
    chat_all(f"joining: {sid}", MSG_USERJOIN);

@sio.event
def disconnect(sid):
    global usercount, clearvotes
    usercount -= 1
    clearvotes = 0
    print(f'> disconnect: (socket: {sid})')
    chat_all(f"leaving: {sid}", MSG_USERLEAVE);

# test event
@sio.event
def ping(sid):
    print(f'pong! {sid}')

# sent by clients when they're ready to have the canvas sent to them
@sio.event
def client_ready(sid):
    print(f"client ready: {sid}")
    sio.emit("canvas_request_state", skip_sid=sid)

# sent by clients as a response to canvas_request_state. forwards the state of the canvas to other clients in order to synchronize them
@sio.event
def canvas_state(sid, data):
    sio.emit("canvas_receive_state", data)

# drawing
@sio.event
def draw_line(sid, data):
    print(sid, data)
    sio.emit("draw_line", data=data, skip_sid=sid)

# voting to clear canvas
@sio.event
def vote_clear(sid):
    global clearvotes, usercount
    clearvotes += 1
    chat_all(f"{sid} voted to clear the canvas ({clearvotes}/{usercount})")
    if(clearvotes >= usercount):
        chat_all("Cleared the canvas")
        sio.emit("canvas_clear")

# receive user's attempt to send a message, then validate and broadcast it
@sio.event
def msg_send(sid, data):
    print(sid, data)
    msg = {
        "timestamp": 0,
        "variant": MSG_USERMSG,
        "user": sid,
        "content": data
    }
    if len(data) > 0:
        sio.emit("msg_broadcast", msg)
    else:
        print(f"> ignoring empty message attempt ({sid})")
    

if __name__ == '__main__':
    frame(f" Starting server \r sv_host = {sv_host} \n sv_port = {sv_port} ")
    eventlet.wsgi.server(eventlet.listen((sv_host, sv_port)), app)