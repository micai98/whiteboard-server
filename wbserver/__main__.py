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

def gen_room_code(min_length=4):
    code = ''
    lastchar = len(ROOMCODE_CHARS)-1
    while len(code) < min_length or code in roomdict:
        code += ROOMCODE_CHARS[random.randint(0, lastchar)]
    return code

@sio.event
def connect(sid, environ, auth):
    print('> connect: ', sid, " auth: ", auth)

@sio.event
def ping(sid):
    print(f'pong! {sid}')

@sio.event
def client_ready(sid):
    print(f"client ready: {sid}")
    sio.emit("canvas_request_state", skip_sid=sid)

@sio.event
def canvas_state(sid, data):
    sio.emit("canvas_receive_state", data)

@sio.event
def draw_line(sid, data):
    print(sid, data)
    sio.emit("draw_line", data=data, skip_sid=sid)

@sio.event
def disconnect(sid):
    print(f'> disconnect: (socket: {sid})')

if __name__ == '__main__':
    frame(f" Starting server \r sv_host = {sv_host} \n sv_port = {sv_port} ")
    eventlet.wsgi.server(eventlet.listen((sv_host, sv_port)), app)