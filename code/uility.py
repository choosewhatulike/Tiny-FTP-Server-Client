'''
    Some helper function 
'''


import os
import time
try:
    import queue
except ImportError:
    import Queue as queue
import socket

class User:
    def __init__(self, name, pwd, auth):
        self.name = name
        self.pwd = pwd
        if 'a' in auth:
            auth = 'vrwa'
        elif 'r' in auth or 'w' in auth:
            if 'v' not in auth:
                auth += 'v'
        self.auth = auth
    
OPCODE = {"ok": "200",
            "error": "500",
            "nocmd": "501",
            "noauth": "401",
            "notfound":"404"}
class Package:
    def __init__(self, cmd=None, args=dict(), data=bytes()):
        self.cmd = cmd
        self.args = args
        self.data = data
        self.dst = 0
        self.src = 0

    def __str__(self):
        s = 'cmd' + self.cmd
        if len(self.args) > 0:
            s += '\nargs: ' +str(self.args)
        return s

    def gen_datapkg(self):
        pkg = "%s\n" % self.cmd
        if len(self.args) > 0:
            for arg, value in self.args.items():
                pkg += "%s: %s\n" % (arg, value)
        pkg += "\n\n"
        pkg = pkg.encode()
        if self.data:
            pkg += self.data
        return pkg

    def de_datapkg(self, pkg):
        cmd_pos = pkg.find(b'\n\n\n')
        if cmd_pos == -1:
            return None
        lines = pkg[:cmd_pos].decode().split('\n')
        cmd = lines[0]
        args = {}
        for line in lines[1:]:
            _ = line.find(': ')
            if _ == -1:
                args['error'] = "Received Invalid Package"
            else:
                args[line[:_]] = line[_+2:]
        data = b''
        if cmd_pos+3 < len(pkg):
            data = pkg[cmd_pos+3:]
        pkg = Package(cmd, args, data)
        # print(pkg)
        return pkg


def remove_recurse(path):
    if os.path.isfile(path):
        os.remove(path)
    elif os.path.isdir(path):
        for p in os.listdir(path):
            remove_recurse(path+'/'+p)
        os.rmdir(path)

def files_in_path(path):
    files = []
    unknown = queue.Queue()
    unknown.put_nowait(path)
    while not unknown.empty():
        p = unknown.get_nowait()
        if os.path.isfile(p):
            files.append(p)
        elif os.path.isdir(p):
            for f in os.listdir(p):
                unknown.put_nowait(p+'/'+f)
    return files
    
def isport(s):
    return s.isdigit() and int(s) >= 1 and int(s) <= 65535

def ishost(s):
    nums = s.split('.')
    for n in nums:
        if n.isdigit():
            num = int(n)
            if num > 255 or num < 0:
                return False
        else:
            return False
    return True

def ispath(s):
    s = os.path.abspath(s)
    if os.getcwd() not in s:
        return False
    return True

def isfile(s):
    return os.path.isfile(s)

def is_inpath(f, path):
    os.path.abspath(f)
    return path in f

def get_curdir():
    return os.getcwd() + '/'

def ntol(n):
    if not isinstance(n, bytes):
        raise TypeError
    res =  int(n.decode())
    return res

def lton(n):
    if not isinstance(n, int):
        raise TypeError
    res = str(n).encode()
    return res