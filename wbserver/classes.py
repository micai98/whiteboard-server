from . import objects

class User:
    def __init__(self, sid:str, name:str):
        self.name = name
        self.sid = sid
        self.room = ''
         # add itself to the user object dict

    def add_to_dict(self):
        objects.users[self.sid] = self

    def get_room_obj(self):
        if self.room in objects.rooms:
            return get_room(self.room)
        else:
            return None

    def delete(self):
        print(f" - USER DELETED: {self.name} ({self.sid})")
        if self.sid in objects.users:
            objects.users.pop(self.sid)


def get_user(sid:str) -> User:
    if sid in objects.users:
        return objects.users[sid]
    else:
        return None

class Room:
    def __init__(self, roomcode, host:str):
        print(f" + ROOM CREATED: {roomcode} by {host}")
        self.roomcode = roomcode
        objects.rooms[roomcode] = self # add itself to the room object dict
        self.host:str = host # room's host, basically the room's administrator
        self.users:list = [] # SIDs of connected clients
        self.clearvotes:list = [] # SIDs of clients currently voting to clear canvas
        self.uids:dict = {} # UIDs of connected clients. 
        # UIDs are hardly ever used in the server's code. 
        # They exist to give clients a convenient way to reference other clients (in console commands for instance) without exposing SIDs
        
    def add_to_dict(self):
        objects.rooms[self.roomcode] = self

    def delete(self):
        """deletes the room and removes its object dict entry"""
        print(f" + ROOM DELETED: {self.roomcode}")
        if self.roomcode in objects.rooms:
            objects.rooms.pop(self.roomcode)
        del self

    def get_uid(self, sid:str):
        """get user's UID from their SID"""
        for uid, val in self.uids.items():
            if val == sid: return uid
        return None

    def get_user_by_uid(self, uid:int):
        """get user's object from their UID"""
        if uid in self.uids:
            return get_user(self.uids[uid])
        else:
            return None

    def user_add(self, sid: str):
        user:User = get_user(sid)
        if not user: return
        
        self.users.append(sid)
        if user.room in objects.rooms:
            get_room(user.room).user_remove(sid)
        user.room = self.roomcode

        # generate UID
        uid_max = len(self.uids)+1
        for i in range(0, uid_max):
            if i in self.uids: 
                continue
            else:
                self.uids[i] = sid
                break

    def user_remove(self, sid: str):
        if sid in self.users:
            self.users.remove(sid)
        if sid in self.clearvotes:
            self.clearvotes.remove(sid)
        self.uids = {key:val for key, val in self.uids.items() if val != sid}

        user:User = get_user(sid)
        if(user): user.room = ''

        # empty rooms have no reason to exist, they will be automatically removed
        if len(self.users) == 0: self.delete()

    def gen_welcome_data(self, sid:str):
        """compiles data to be sent to a client that just joined the room"""

        return {
            "roomcode": self.roomcode,
            "uid": self.get_uid(sid)
        }

    def gen_update_data(self):
        """compiles data to be sent to clients whenever the room updates"""
        
        uiddict = {}

        for uid in self.uids:
            user:User = get_user(self.uids[uid])
            uiddict[uid] = user.name
        
        return {
            "host": self.get_uid(self.host),
            "users": uiddict,
            "usercount": len(uiddict)
        }

def get_room(roomcode:str) -> Room:
    if roomcode in objects.rooms:
        return objects.rooms[roomcode]
    else:
        return None