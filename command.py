'''
    Some helper function to deal with package transfered between client and server
'''
import os
from uility import *

def getpkg(path):
    return Package('get',  {'path': path})

def postpkg(path, dst):
    data = b''
    if not isfile(path):
        return Package(500, {'cmd': 'post',
                            'path': path,
                            'error': "invalid path"})
    with open(path, 'rb') as f:
        data = f.read()
    p, fn = os.path.split(path)
    size = os.path.getsize(path)
    args = {'path': p, 
            'dst': dst, 
            'filesize':size,
            'filename': fn}
    return Package('post', args, data)

def normalpkg(cmd, args):
    return Package(cmd, args)

def errorpkg(cmd, errmsg, code='500'):
    args = {}
    args['cmd'] = cmd
    args['error'] = errmsg
    return Package(code, args)

def noauthpkg(cmd):
    return errorpkg(cmd, "Has no authorized", OPCODE['noauth'])

def ok_resp(cmd):
    return Package(OPCODE['ok'], {'cmd':cmd})

def recvpkg(conn):
    pkg = bytes()
    length = 0
    while True:
        data = conn.recv(4096)
        if not data:
            break
        pkg += data
        if length == 0:
            isfirst = False
            len_pos = pkg.find(b'\n')
            length = ntol(pkg[:len_pos])
            pkg = pkg[len_pos+1:]
        if len(pkg) >= length:
            res = pkg[:length]
            pkg = pkg[length+1:]
            recv_pkg = Package().de_datapkg(res)
            recv_pkg.dst = conn.getsockname()
            recv_pkg.src = conn.getpeername()
            # print("recv %dbytes from %s:%s"%(length, recv_pkg.src[0], recv_pkg.src[1]))
            # print(res)
            length = 0
            yield recv_pkg

def sendpkg(conn, pkg):
    host, port = conn.getpeername()
    if pkg:
        data = pkg.gen_datapkg()
        # print("send %dbytes to %s:%s"%(len(data), host, port))      
        data = lton(len(data)) + b'\n'+ data
        # print(data)  
        conn.sendall(data)
    else:
        # print("no pkg to send %s:%s"%(host,port))
        pass
