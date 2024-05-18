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
def chat_print(text:str, to:str , type:int=MSG_SYSINFO):
    """prints a message in specified users' chatboxes"""
    msg = {
        "timestamp": timenow(),
        "variant": type,
        "content": text
    }

    sio.emit("msg_broadcast", data=msg, to=to)

# used to print a notification whenever the room's host is changed
def chat_announce_host(host_sid:str, to:str):
    chat_print(f"{get_user(host_sid).name} is now the host", to=to, type=MSG_SYSWARNING)

# processes string as a chat command, returns -1 if command doesn't exist. the prefix should be removed before being passed to this function
def process_command(sid:str, text:str):
    """processes string as a chat command, returns -1 if command doesn't exist. the prefix should be removed before being passed to this function"""
    args = text.split(" ")
    cmd = args.pop(0).lower() # make command names case insensitive
    user:User = get_user(sid)
    room:Room = user.get_room_obj()

    # sanity checks
    if not user:
        print(f" > INVALID USER ISSUED A COMMAND: {sid} {text}")
        return -1
    
    if not room:
        print(f" > USER IN INVALID ROOM ISSUED A COMMAND: {sid} {text}")
        return -1

    # - - COMMANDS
    if cmd == "info":
        chat_print(f"Server version: {__version__} | Users online: {usercount}", to=sid)
        return 0
    
    if cmd == "say":
        content = " ".join(args)
        content_len = len(content)
        if content_len > 0 and content_len < MSG_LEN_MAX: 
            msg = {
                "timestamp": timenow(),
                "variant": MSG_USERMSG,
                "user": user.name,
                "content": content
            }
            sio.emit("msg_broadcast", msg, to=user.room)
        else:
            chat_print(f"Message too long or empty (limit: {MSG_LEN_MAX})", to=sid, type=MSG_SYSERROR)
            print(f"> ignoring empty/too long message attempt ({sid})")
        return 0
    
    if cmd == "list":
        chat_print(f"Users in room {user.room}:", to=sid)
        for uid in room.uids:
            user = room.get_user_by_uid(uid)
            if user.sid == room.host:
                chat_print(f"{uid} (HOST) - {user.name}", to=sid)
            else:
                chat_print(f"{uid} - {user.name}", to=sid)
        return 0

    if cmd == "clear":
        votes = len(room.clearvotes)
        users = len(room.users)

        if sid in room.clearvotes:
            room.clearvotes.remove(sid)
            chat_print(f"{user.name} cancelled vote to clear canvas", to=room.roomcode)
        else:
            votes += 1
            room.clearvotes.append(sid)
            chat_print(f"{user.name} wants to clear the canvas ({votes}/{users})", to=room.roomcode)
        
            if votes >= users:
                room.clearvotes.clear()
                chat_print("Cleared the canvas", to=room.roomcode, type=MSG_SYSWARNING)
                sio.emit("canvas_clear", to=user.room)

        return 0
    
    # - - ADMIN COMMANDS
    if cmd == "forceclear":
        if sid != room.host: 
            chat_print(TEXT_NOPERMS, to=sid, type=MSG_SYSERROR)
            return 0
        
        chat_print("Cleared the canvas (forced by host)", to=room.roomcode, type=MSG_SYSWARNING)
        sio.emit("canvas_clear", to=room.roomcode)
        return 0

    if cmd == "givehost":
        if sid != room.host: 
            chat_print(TEXT_NOPERMS, to=sid, type=MSG_SYSERROR)
            return 0
        
        target:User = cmd_arg_to_user(sid, room, args)
        if target:
            room.host = target.sid
            chat_announce_host(target.sid, room.roomcode)
            sio.emit("room_update", to=room.roomcode, data=room.gen_update_data())

        return 0


    if cmd == "kick":
        if sid != room.host: 
            chat_print(TEXT_NOPERMS, to=sid, type=MSG_SYSERROR)
            return 0
    
        target:User = cmd_arg_to_user(sid, room, args)
        if target:
            chat_print(f"{target.name} has been kicked", to=room.roomcode, type=MSG_SYSWARNING)
            sio.disconnect(target.sid)
        
        return 0
        
    # - -

    # all commands should return a value, if the code reached this point that means the user entered an invalid command
    chat_print(f'Unknown command \"{cmd}\"', to=sid)
    return -1

def cmd_arg_to_user(caller_sid:str, room:Room, args:list[str], pos:int=0, allowself:bool=False):
    if len(args) < 1 or not args[pos].isdigit():
        chat_print(TEXT_NOARGS, to=caller_sid, type=MSG_SYSERROR)
        return None
    
    target:User = room.get_user_by_uid(int(args[pos]))
    if target:
        if target.sid == caller_sid and allowself == False:
            chat_print(TEXT_NOSELFTARGET, to=caller_sid, type=MSG_SYSERROR)
            return None
        else:
            return target

    chat_print(TEXT_NOTARGET, to=caller_sid, type=MSG_SYSERROR)
    return None

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
            room:Room = get_room(roomcode)
            room.user_remove(sid)
            if roomcode in objects.rooms: #check if room didn't get auto-deleted after the user left
                sio.emit("room_update", to=roomcode, data=room.gen_update_data())
                if room.host == sid: # if the user who left was the host, choose a new one
                    room.host = random.choice(room.users)
                    print(f' + ROOM {roomcode} changed host to: ')
                    chat_announce_host(room.host, roomcode)

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
        # the server doesn't store canvases
        # instead it asks the host for the canvas state whenever a new user joins
        sio.emit("canvas_request_state", to=room.host, skip_sid=sid) 
    
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
        sio.emit("room_welcome", to=sid, data=room.gen_welcome_data(sid))
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
def user_draw(sid, data):
    if not data: return
    roomcode:str = get_user(sid).room
    if roomcode != '':
        sio.emit("user_draw", data=data, skip_sid=sid, to=roomcode)

@sio.event
def user_move(sid, data):
    if not data: return
    roomcode:str = get_user(sid).room
    if roomcode != '':
        uid = get_room(roomcode).get_uid(sid)
        sio.emit("user_move", data=[uid, data[0], data[1]], skip_sid=sid, to=roomcode)

# process user chat commands (this includes chat messages)
@sio.event
def command(sid, data):
    user:User = get_user(sid)
    print(sid, user.name, "@", user.room, " : ", data)
    process_command(sid, data)
    
if __name__ == '__main__':
    frame(f" Starting server \r sv_host = {sv_host} \n sv_port = {sv_port} ")
    eventlet.wsgi.server(eventlet.listen((sv_host, sv_port)), app)