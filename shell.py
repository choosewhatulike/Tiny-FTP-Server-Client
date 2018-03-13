'''
    Back-end and CUI front-end of client
'''


import os, sys
from getopt import getopt, GetoptError
from uility import *
from command import *
import threading
try:
  import readline
except ImportError:
  import pyreadline as readline


PORT = 20202
TIMEOUT = 10
CMDlist = None
Remotedir = None
HELP_str = None
Client = None

class MyClient:
    def __init__(self):
        self.tasks = queue.Queue()
        self.is_conn = False
        self.conn_ss = None
        self.cmdlist = {'connect': self.connect,
                        'get': self.get,
                        'post': self.post,
                        'close': self.close}
        self.normalcmdlist = ['list', 'rename', 'mkdir', 'delete', 'login', 'account']

    def add_task(self, task):
        task.done.clear()        
        self.tasks.put_nowait(task)

    def run(self):
        runner = threading.Thread(target=self.handle, args=())
        runner.start()
        print("client start running")

    def shutdown(self):
        self.tasks.put_nowait(None)

    def handle(self):
        while True:
            task = self.tasks.get()
            if not task:
                return
            # print("task:%s"%task.cmd)
            try:
                if not self.is_conn and task.cmd != 'connect':
                    task.ans = Package(OPCODE['error'], {'cmd': task.cmd,
                                            'error': "No Connection"})
                elif task.cmd in self.cmdlist:
                    task.ans = self.cmdlist[task.cmd](task.args)
                elif task.cmd in self.normalcmdlist:
                    task.ans = self.normalcmd(task.cmd, task.args)
                elif task.cmd == 'close':
                    task.ans = self.close(task.args)
                else:
                    task.ans = Package(OPCODE['error'], {'cmd': task.cmd,
                                            'error': "No Such Command"})
            except socket.timeout:
                msg = "Time Out, Please retry or Reconnect"
                task.ans = Package(OPCODE['error'], {'cmd': task.cmd, 'error': msg})
                
            except (StopIteration, socket.error) as e:
                self.is_conn = False
                self.conn_ss.close()
                task.ans = Package(OPCODE['error'], {'cmd': task.cmd, 'error': e})
                # raise
            finally:
                task.done.set()
        if self.is_conn:
            try:
                self.conn_ss.close()
            except Exception:
                pass 

    def connect(self, args):
        pkg = Package(OPCODE['ok'], {'cmd': 'connect'})
        if self.is_conn:
            self.conn_ss.close()            
        hostip = args['host']
        port = args['port']
        self.host = (hostip, port)
        print("connecting: %s:%s"%self.host)
        self.conn_ss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn_ss.settimeout(TIMEOUT)                
        self.conn_ss.connect(self.host)
        self.is_conn = True
        self.recver = recvpkg(self.conn_ss)
        return pkg

    def get(self, args):
        path = args['path']
        dst = args['dst']
        pkg = getpkg(path)
        sendpkg(self.conn_ss, pkg)
        new_pkg = next(self.recver)
        if new_pkg.cmd == OPCODE['ok']:
            fn = new_pkg.args['filename']
            with open(dst+'/'+fn, 'wb') as f:
                f.write(new_pkg.data)
        return new_pkg

    def post(self, args):
        path = args['path']
        dst = args['dst']
        try:
            pkg = postpkg(path, dst)
        except OSError as e:
            pkg = errorpkg('post', e.__str__())
            return pkg
        sendpkg(self.conn_ss, pkg)
        new_pkg = next(self.recver)
        return new_pkg

    def normalcmd(self, cmd, args):
        pkg = normalpkg(cmd, args)
        sendpkg(self.conn_ss, pkg)
        new_pkg = next(self.recver)
        return new_pkg

    def close(self, args):
        self.conn_ss.close()
        self.is_conn = False
        return Package(OPCODE['ok'], {'cmd': 'close'})

class Task:
    done = threading.Event()
    def __init__(self, callback, cmd, args=None):
        if args is None:
            args = {}
        self.callback = callback
        self.cmd = cmd
        self.args = args
        self.ans = None

    def wait_done(self, timeout=None):
        return self.done.wait(timeout)    

def start():
    try:
        try:
            readcmd_obj = readline.Readline()
        except Exception:
            readcmd_obj = None
        while True:
            if readcmd_obj is None:
                cmd = input("FTP>> ")
            else:
                cmd = readcmd_obj.readline("FTP>> ")
            task = parse(cmd)
            if not task:
                continue
            _run_task(task)
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        Client.shutdown()

def parse(line):
    global CMDlist
    tokens = line.strip().split()
    if not tokens:
        return
    cmd = tokens[0]
    if cmd not in CMDlist:
        print('Unknown conmmand %s' % cmd)
        return None
    try:
        res = CMDlist[cmd](tokens)
    except GetoptError:
        print("invalid parameters")
        return None
    return res


def _run_task(task):
    Client.add_task(task)
    task.wait_done()
    task.callback(task)

def localfunc(tokens):
    cmd = ' '.join(tokens)
    os.system(cmd[1:])

def no_return(task):
    global Remotedir
    if task.ans.cmd == OPCODE['ok']:
        if task.cmd in ('connect', 'login'):
            Remotedir = ''
        print("cmd:%s done successful" % task.cmd)
    else:
        print(task.ans.args['error'])

def after_ls(task):
    if task.ans.cmd != OPCODE['ok']:
        print(task.ans.args['error'])
    elif len(task.ans.data) == 0:
        print("ERROR: No file in path")
    else:
        print(task.ans.data.decode())

def after_cd(task):
    global Remotedir
    if task.ans.cmd != OPCODE['ok']:
        print(task.ans.args['error'])
        return
    Remotedir = task.ans.args['path']
    if not Remotedir.endswith('/'):
        Remotedir += '/'
    after_ls(task)

def after_account(task):
    if task.ans.cmd == OPCODE['ok'] and task.args['action'] == 'list':
        print(task.ans.data.decode())
    else:
        no_return(task)

def my_help(tokens):
    print(HELP_str)

def login(tokens):
    opts, tokens = getopt(tokens[1:], 'n:p:', ['name=','pwd='])
    if len(tokens) > 0:
        raise GetoptError
    cmd = 'login'
    args = {}
    for o, v in opts:
        if o in ('-n', '--name'):
            args['name'] = v
        elif o in ('-p', '--pwd'):
            args['pwd'] = v
        else:
            raise GetoptError
    return Task(no_return, cmd, args)

def connect(tokens):
    host = ''
    port = 0
    opts, tokens = getopt(tokens[1:], 'p:')
    for arg, v in opts:
        if arg == '-p':
            if isport(v):
                port = int(v)
            else:
                 raise GetoptError("")
    if port == 0:
        port = PORT
    if len(tokens) == 1 and ishost(tokens[0]):
        host = tokens[0]
    else:
        raise GetoptError("")
    cmd = 'connect'
    args = {'host':host, 'port':port}
    return Task(no_return, cmd, args)

def close(tokens):
    cmd = 'close'
    args = {}
    return Task(no_return, cmd, args)

def cd(tokens):
    global Remotedir
    if len(tokens) <= 1:
        raise GetoptError('')
    tokens = 'ls ' + tokens[1]
    res = parse(tokens)
    if not res:
        return
    res.callback = after_cd
    return res

def ls(tokens):
    global Remotedir
    cmd = 'list'
    if len(tokens) == 1:
        if not Remotedir:
            arg = '.'
        else:
            arg = Remotedir
    elif len(tokens) == 2:
        arg = Remotedir + tokens[1]
    else:
        raise GetoptError("")
    args = {'path': arg}
    return Task(after_ls, cmd, args)

def mkdir(tokens):
    global Remotedir
    cmd = 'mkdir'
    if len(tokens) == 1:
        raise GetoptError('')
    arg = Remotedir + tokens[1].strip()
    if not arg:
        raise GetoptError('')
    args = {'path': arg}
    return Task(no_return, cmd, args)

def rmdir(tokens):
    return rm(tokens)

def get(tokens):
    global Remotedir
    cmd = 'get'
    src = None
    dst = get_curdir()
    if len(tokens) == 2:
        src = Remotedir + tokens[1]
    elif len(tokens) != 3:
        raise GetoptError('')
    else:
        src = Remotedir + tokens[1]
        dst += tokens[2]
    args = {'path': src, 'dst': dst}
    return Task(no_return, cmd, args)

def post(tokens):
    global Remotedir
    cmd = 'post'
    src = get_curdir()
    dst = Remotedir
    if len(tokens) == 2:
        src += tokens[1]
    elif len(tokens) == 3:
        src += tokens[1]
        dst += tokens[2]
    else:
        raise GetoptError('')
    args = {'path': src, 'dst': dst}
    return Task(no_return, cmd, args)    

def rename(tokens):
    global Remotedir
    cmd = 'rename'
    if len(tokens) != 3:
        raise GetoptError('')
    src = tokens[1]
    dst = tokens[2]
    args = {'path': Remotedir, 'src': src, 'dst': dst}
    return Task(no_return, cmd, args)    

def rm(tokens):
    global Remotedir
    cmd = 'delete'
    if len(tokens) != 2:
        raise GetoptError('')
    args = {'path': Remotedir + tokens[1]}
    return Task(no_return, cmd, args)    

def account(tokens):
    cmd = 'account'
    args = {}
    start_pos = 0
    while start_pos < len(tokens):
        if '-' in tokens[start_pos]:
            break
        start_pos += 1
    if start_pos < len(tokens):
        opts, _ = getopt(tokens[start_pos:], 'n:p:a:', ['name=','pwd=','auth='])
        tokens = tokens[:start_pos] + _
    else:
        opts = []
    if len(tokens) != 2:
        raise GetoptError('')
    args['action'] = tokens[1]
    for o, v in opts:
        if o in ('-n', '--name'):
            args['name'] = v
        elif o in ('-p', '--pwd'):
            args['pwd'] = v
        elif o in ('-a', '--auth'):
            args['auth'] = v
        else:
            raise GetoptError
    return Task(after_account, cmd, args)

def quit(tokens):
    raise KeyboardInterrupt

def init():
    global Remotedir
    global HELP_str
    global Client
    global CMDlist
    Remotedir = ''
    HELP_str = "This is the help msg"
    Client = MyClient()
    CMDlist = {
        'ls': ls,
        'help': my_help,
        'rm': rm,
        'rename': rename,
        'mkdir': mkdir,
        'rmdir': rmdir,
        'cd': cd,
        'get': get,
        'post': post,
        'connect': connect,
        'login': login,
        'account': account,
        'close': close
    }


if __name__ == '__main__':
    init()
    Client.run()
    # Client.connect({"host":"127.0.0.1", "port":PORT})
    start()
