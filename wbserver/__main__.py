#!/usr/bin/env python
# *_* coding: utf-8 *_*

"""
whiteboard websocket server
"""

__author__ = "micai"
__version__ = "0.3"

import random
import time

import eventlet
import socketio

from . import objects
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

usercount = 0

# generates a random unique room code
def gen_room_code(min_length:int=4):
    """generates a random unique room code"""
    code = ""
    lastchar = len(ROOMCODE_CHARS)-1
    while len(code) < min_length or code in objects.rooms:
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

# processes string as a chat command, returns -1 if command doesn't exist. the prefix should be removed before being passed to this function
def process_command(sid:str, text:str):
    """processes string as a chat command, returns -1 if command doesn't exist. the prefix should be removed before being passed to this function"""
    args = text.split(" ")
    cmd = args.pop(0)
    user:User = get_user(sid)

    if not user:
        print(f" > INVALID USER ISSUED A COMMAND: {sid} {text}")
        return
    
    if not user.room in objects.rooms:
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
        room:Room = objects.rooms[user.room]
        i:int = 0
        chat_print(f"Users in room {user.room}:", to=sid)
        for uid in room.uids:
            user = room.get_user_by_uid(uid)
            if user.sid == room.host:
                chat_print(f"{uid} (HOST) - {user.name}", to=sid)
            else:
                chat_print(f"{uid} - {user.name}", to=sid)
        return 0

    if cmd == "clear":
        room:Room = objects.rooms[user.room]

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
    
    if cmd == "forceclear":
        room:Room = objects.rooms[user.room]
        if sid != room.host: 
            chat_print("You don't have permission to use this command", to=sid, type=MSG_SYSERROR)
            return 0
        
        chat_print("Cleared the canvas (forced by host)")
        sio.emit("canvas_clear", to=room.roomcode)
        return 0

    # all commands should return a value, if the code reached this point that means the user entered an invalid command
    chat_print(f'Unknown command \"{cmd}\"', to=sid)

    return -1
        
def validate_user(sid, auth):
    try:
        if auth:
            if 'user_name' in auth:
                namelen = len(auth['user_name'])
                if namelen >= USER_NAMELEN_MIN and namelen <= USER_NAMELEN_MAX:
                    return True
    except Exception as e:
        print(" > EXCEPTION WHILE VALIDATING USER")
        print(e)
    return False

@sio.event
def connect(sid, environ, auth):
    global usercount
    usercount += 1
    print(' > connect: ', sid, " auth: ", auth)

    if validate_user(sid, auth):
        user = User(sid, auth['user_name'])
        user.add_to_dict()
        response = {
            "accepted": True,
            "message": "Accepted",
            "username": user.name
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
    global usercount
    usercount -= 1
    print(f' > disconnect: (socket: {sid})')

    if sid in objects.users:
        user:User = get_user(sid)
        roomcode:str = get_user(sid).room
        if roomcode in objects.rooms:
            print('  removing user from room')
            chat_print(f"leaving: {user.name}", type=MSG_USERLEAVE, to=roomcode)
            get_room(roomcode).user_remove(sid)

        print('   removing associated objects.users entry')
        user.delete()

    else:
        print('   user had no objects.users entry')

# sent by clients when they're ready to join a room or create one
@sio.event
def client_join(sid, data):
    if not data:
        sio.disconnect(sid)
        print(f"   {sid} invalid join attempt (no data provided)")
        return

    print(f" > client joining: sid={sid} data={data}")

    
    roomcode = ''
    room:Room = None

    # if valid room code was specified join already existing room
    if 'room' in data and data['room'] in objects.rooms:
        print(f" - {sid} joining existing room {data}")
        roomcode = data['room']
        room = get_room(roomcode)
        room.user_add(sid)
        sio.emit("canvas_request_state", to=roomcode, skip_sid=sid)
    
    # if specified room code doesn't exist or none was specified, create and join a new room
    else:
        roomcode = gen_room_code()
        room = Room(roomcode, sid)
        room.add_to_dict()
        room.user_add(sid)
        print(f" - {sid} creating NEW room {data} CODE = {roomcode}")
        # client is in "loading" state until the canvas state is received, since the room is new and the client is alone, there's 
        # nobody to receive canvas state from, so we send them an empty canvas to tell the client it's good to go
        sio.emit("canvas_receive_state", data="NEW_ROOM_EMPTY_CANVAS", to=sid)
        print(objects.rooms)
    
    # check if the room was successfuly created and then welcome the user
    if roomcode in objects.rooms:
        sio.enter_room(sid, roomcode)
        sio.emit("room_welcome", to=sid, data=roomcode)
        sio.emit("room_update", to=roomcode, data=room.gen_update_data())
        chat_print(f'joining: {get_user(sid).name}', type=MSG_USERJOIN, to=roomcode)
    else:
        # if something goes wrong disconnect the client to prevent weird limbo connections
        sio.disconnect(sid)

# sent by clients as a response to canvas_request_state. forwards the state of the canvas to other clients in order to synchronize them
@sio.event
def canvas_state(sid, data):
    roomcode:str = get_user(sid).room
    if roomcode in objects.rooms:
        sio.emit("canvas_receive_state", to=roomcode, data=data)

# drawing
@sio.event
def draw_line(sid, data):
    roomcode:str = get_user(sid).room
    if roomcode != '':
        sio.emit("draw_line", data=data, skip_sid=sid, to=roomcode)

# process user chat commands (this includes chat messages)
@sio.event
def command(sid, data):
    user:User = get_user(sid)
    print(sid, user.name, "@", user.room, " : ", data)
    process_command(sid, data)
    
if __name__ == '__main__':
    frame(f" Starting server \r sv_host = {sv_host} \n sv_port = {sv_port} ")
    eventlet.wsgi.server(eventlet.listen((sv_host, sv_port)), app)