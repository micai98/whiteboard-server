#!/usr/bin/env python
# *_* coding: utf-8 *_*

"""
whiteboard websocket server
"""

__author__ = "micai"
__version__ = "0.1.1"

import random
import time

import eventlet
import socketio

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
    code = ""
    lastchar = len(ROOMCODE_CHARS)-1
    while len(code) < min_length or code in roomdict:
        code += ROOMCODE_CHARS[random.randint(0, lastchar)]
    return code

# prints a message in specified users' chatboxes
def chat_print(text:str, to=None , type:int=MSG_SYSINFO):
    """prints a message in specified users' chatboxes"""
    msg = {
        "timestamp": timenow(),
        "variant": type,
        "content": text
    }

    sio.emit("msg_broadcast", data=msg, to=to)

# processes string as a chat command, returns -1 if command doesn't exist. the prefix should be removed before being passed to this function
def process_command(sid:str, text:str):
    """processes string as a chat command, returns -1 if command doesn't exist. the prefix should be removed before being passed to this function"""
    args = text.split(" ")
    cmd = args.pop(0)
    global clearvotes, usercount

    if(cmd == "info"):
        chat_print(f"Server version: {__version__} | Users online: {usercount}", to=sid)
        return 0
    
    if(cmd == "say"):
        content = " ".join(args)
        if len(content) > 0: 
            msg = {
                "timestamp": timenow(),
                "variant": MSG_USERMSG,
                "user": sid,
                "content": content
            }
            sio.emit("msg_broadcast", msg)
        else:
            print(f"> ignoring empty message attempt ({sid})")
        return 0
    
    if(cmd == "clear"):
        clearvotes += 1
        chat_print(f"{sid} voted to clear the canvas ({clearvotes}/{usercount})")
        if(clearvotes >= usercount):
            clearvotes = 0
            chat_print("Cleared the canvas")
            sio.emit("canvas_clear")
        return 0
    
    # all commands should return a value, if the code reached this point that means the user entered an invalid command
    chat_print(f"Unknown command \"{cmd}\"", to=sid)

    return -1
        

@sio.event
def connect(sid, environ, auth):
    global usercount, clearvotes
    usercount += 1
    print('> connect: ', sid, " auth: ", auth)
    chat_print(f"joining: {sid}", MSG_USERJOIN)

@sio.event
def disconnect(sid):
    global usercount, clearvotes
    usercount -= 1
    clearvotes = 0
    print(f'> disconnect: (socket: {sid})')
    chat_print(f"leaving: {sid}", MSG_USERLEAVE)

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
    #print(sid, data)
    sio.emit("draw_line", data=data, skip_sid=sid)

# process user commands (this includes chat messages, since that's technically a command as well)
@sio.event
def command(sid, data):
    print(sid, data)
    process_command(sid, data)
    
    

if __name__ == '__main__':
    frame(f" Starting server \r sv_host = {sv_host} \n sv_port = {sv_port} ")
    eventlet.wsgi.server(eventlet.listen((sv_host, sv_port)), app)