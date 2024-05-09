class User:
    def __init__(self, name:str):
        self.name = name
        self.room = ''

class Room:
    def __init__(self, host:str):
        self.host:str = host
        self.users:list = []
        self.clearvotes:list = []