#!/usr/bin/env python
# *_* coding: utf-8 *_*

"""
whiteboard websocket server
"""

__author__ = "micai"
__version__ = "0.2"

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
roomdict = {
    'DUMMY': Room('nobody')
}

usercount = 0

# generates a random unique room code
def gen_room_code(min_length:int=4):
    """generates a random unique room code"""
    code = ""
    lastchar = len(ROOMCODE_CHARS)-1
    while len(code) < min_length or code in roomdict:
        code += ROOMCODE_CHARS[random.randint(0, lastchar)]
    return code

# prints a message in specified users' chatboxes
def chat_print(text:str, to="" , type:int=MSG_SYSINFO):
    """prints a message in specified users' chatboxes"""
    msg = {
        "timestamp": timenow(),
        "variant": type,
        "content": text
    }

    sio.emit("msg_broadcast", data=msg, to=to)

def get_user_name(sid:str):
    return userdict[sid].name

def get_user_roomcode(sid:str):
    return userdict[sid].room

def room_create(host:str):
    code = gen_room_code()
    roomdict[code] = Room(host=host)
    print(f" + ROOM CREATED: {code} by {host}")
    return code

def room_delete(roomcode:str):
    print(f" + ROOM DELETED: {roomcode}")
    if roomcode in roomdict:
        roomdict.pop(roomcode)
    sio.close_room(roomcode)

def room_user_add(roomcode:str, sid:str):
    room:Room = roomdict[roomcode]
    room.users.append(sid)
    sio.enter_room(sid, roomcode)

    user:User = userdict[sid]
    if user.room in roomdict:
        room_user_remove(user.room, sid)
    user.room = roomcode

def room_user_remove(roomcode:str, sid:str):
    room:Room = roomdict[roomcode]
    if sid in room.users:
        room.users.remove(sid)
    if sid in room.clearvotes:
        room.clearvotes.remove(sid)
    
    user:User = userdict[sid]
    user.room = ''
    
    # as of now, there's no point keeping empty rooms around, so they will be automatically deleted once the last user leaves
    if len(room.users) == 0:
        room_delete(roomcode)

# processes string as a chat command, returns -1 if command doesn't exist. the prefix should be removed before being passed to this function
def process_command(sid:str, text:str):
    """processes string as a chat command, returns -1 if command doesn't exist. the prefix should be removed before being passed to this function"""
    args = text.split(" ")
    cmd = args.pop(0)
    user:User = userdict[sid]

    if not user:
        print(f" > INVALID USER ISSUED A COMMAND: {sid} {text}")
        return
    
    if not user.room in roomdict:
        print(f" > USER IN INVALID ROOM ISSUED A COMMAND: {sid} {text}")
        return

    if cmd == "info":
        chat_print(f"Server version: {__version__} | Users online: {usercount}", to=sid)
        return 0
    
    if cmd == "say":
        content = " ".join(args)
        if len(content) > 0: 
            msg = {
                "timestamp": timenow(),
                "variant": MSG_USERMSG,
                "user": user.name,
                "content": content
            }
            sio.emit("msg_broadcast", msg, to=user.room)
        else:
            print(f"> ignoring empty message attempt ({sid})")
        return 0
    
    if cmd == "list":
        room:Room = roomdict[user.room]
        i:int = 0
        chat_print(f"Users in room {user.room}:", to=sid)
        for uid in room.users:
            chat_print(f"{i} - {get_user_name(uid)}", to=sid)
            i += 1

        return 0

    if cmd == "clear":
        room:Room = roomdict[user.room]

        votes = len(room.clearvotes)
        users = len(room.users)

        if sid in room.clearvotes:
            room.clearvotes.remove(sid)
            chat_print(f"{user.name} cancelled vote to clear canvas")
        else:
            votes += 1
            room.clearvotes.append(sid)
            chat_print(f"{user.name} wants to clear the canvas ({votes}/{users})")
        
            if votes >= users:
                room.clearvotes.clear()
                chat_print("Cleared the canvas")
                sio.emit("canvas_clear", to=user.room)

        return 0
    
    # all commands should return a value, if the code reached this point that means the user entered an invalid command
    chat_print(f'Unknown command \"{cmd}\"', to=sid)

    return -1
        
def validate_user(sid, auth):
    try:
        if auth:
            if 'user_name' in auth:
                if len(auth['user_name']) > 0:
                    return True
    except Exception:
        pass
    return False

@sio.event
def connect(sid, environ, auth):
    global usercount, clearvotes
    usercount += 1
    print(' > connect: ', sid, " auth: ", auth)

    if validate_user(sid, auth):
        userdict[sid] = User(auth['user_name'])
        response = {
            "accepted": True,
            "message": "Accepted",
            "username": userdict[sid].name
        }
        
        sio.emit("connect_response", to=sid, data=response)
        print("  user is valid")

    else:
        print("  validation failed")
        response = {
            "accepted": False,
            "message": "Validation failed",
            "username": ""
        }
        sio.emit("connect_response", to=sid, data=response)
        sio.disconnect(sid)
        

@sio.event
def disconnect(sid):
    global usercount, clearvotes
    usercount -= 1
    clearvotes = 0
    print(f' > disconnect: (socket: {sid})')

    if sid in userdict:
        roomcode:str = get_user_roomcode(sid)
        if roomcode in roomdict:
            print('  removing user from room')
            chat_print(f"leaving: {userdict[sid].name}", type=MSG_USERLEAVE, to=roomcode)
            room_user_remove(roomcode, sid)

        print('   removing associated userdict entry')
        
        userdict.pop(sid)
    else:
        print('   user had no userdict entry')

# test event
@sio.event
def ping(sid):
    print(f'pong! {sid}')

# sent by clients when they're ready to join a room or create one
@sio.event
def client_join(sid, data):
    if not data:
        sio.disconnect(sid)
        print(f"   {sid} invalid join attempt (no data provided)")
        return

    print(f" > client joining: sid={sid} data={data}")

    # if valid room code was specified join already existing room
    roomcode = ''

    if 'room' in data and data['room'] in roomdict:
            print(f" - {sid} joining existing room {data}")
            roomcode = data['room']
            room_user_add(roomcode, sid)
            sio.emit("canvas_request_state", to=roomcode, skip_sid=sid)
    
    # if specified room code doesn't exist or none was specified, create and join a new room
    else:
        roomcode = room_create(sid)
        print(f" - {sid} creating NEW room {data} CODE = {roomcode}")
        room_user_add(roomcode, sid)
        # client is in "loading" state until the canvas state is received, since the room is new and the client is alone, there's 
        # nobody to receive canvas state from, so we send them an empty canvas to tell the client it's good to go
        sio.emit("canvas_receive_state", data="NEW_ROOM_EMPTY_CANVAS", to=sid)
        print(roomdict)
    
    # check if the room was successfuly created and then welcome the user
    if roomcode in roomdict:
        sio.emit("room_welcome", data=roomcode, to=sid)
        chat_print(f'joining: {userdict[sid].name}', type=MSG_USERJOIN, to=roomcode)

    

# sent by clients as a response to canvas_request_state. forwards the state of the canvas to other clients in order to synchronize them
@sio.event
def canvas_state(sid, data):
    roomcode:str = get_user_roomcode(sid)
    if roomcode in roomdict:
        sio.emit("canvas_receive_state", to=roomcode, data=data)



# drawing
@sio.event
def draw_line(sid, data):
    roomcode = get_user_roomcode(sid)
    if roomcode != '':
        sio.emit("draw_line", data=data, skip_sid=sid, to=roomcode)

# process user chat commands (this includes chat messages)
@sio.event
def command(sid, data):
    print(sid, data)
    process_command(sid, data)
    
    

if __name__ == '__main__':
    frame(f" Starting server \r sv_host = {sv_host} \n sv_port = {sv_port} ")
    eventlet.wsgi.server(eventlet.listen((sv_host, sv_port)), app)