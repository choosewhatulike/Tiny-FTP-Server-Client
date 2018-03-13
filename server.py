'''
    Back-end of server, using threading for multi-processing, using socket for TCP transfer
'''

import socket
import sys
import threading
import pickle
from getopt import getopt, GetoptError
from uility import *
from command import *


PORT = 20202


class MyServer:
    ACCOUNTS_path = '../ACCOUNTS.pkl'
    def __init__(self, ip="localhost", port=PORT, needlogin=False, accounts=None, rootdir=None):
        if accounts is None:
            accounts = {}
        if rootdir is None:
            rootdir = os.curdir
        self.host = (ip, port)
        self.listen_ss = None

        self.needlogin = needlogin
        self.accounts = accounts
        self.set_rootdir(rootdir)

        self.conn_lock = threading.Lock()
        self.connections = {}
        self.sessions = []
        self.is_shutdown = False

        self.cmdHandler = {"get": self.do_get,
                  "post": self.do_post,
                  "login": self.do_login,
                  "list": self.do_list,
                  "mkdir": self.do_mkdir,
                  "delete": self.do_delete,
                  "rename": self.do_rename,
                  "account": self.do_account}
    
    def start(self):
        if self.listen_ss is None:
            self.listen_ss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)        
        self.listen_ss.bind(self.host)
        self.host = self.listen_ss.getsockname()
        self.listen_ss.listen(5)
        print("start server at %s:%s" % self.host)
        try:
            while True:
                conn, addr = self.listen_ss.accept()
                self.sessions.append(addr)
                print("new session %s:%s" % addr)
                t = threading.Thread(target=self.worker_run,
                                     args=(conn,),
                                     name=str(addr))
                t.start()
        finally:
            self.shutdown()

    def shutdown(self):
        self.listen_ss.close()
        self.listen_ss = None
        self.is_shutdown = True
        self.dump_account(self.ACCOUNTS_path)
    
    def worker_run(self, conn):
        try:
            recver = recvpkg(conn)
            while True:
                if self.is_shutdown:
                    conn.close()
                    break
                pkg = next(recver)
                try:
                    new_pkg = self.handle_one(pkg)
                except (KeyError, ValueError, OSError) as e:
                    # print(e)
                    new_pkg = errorpkg(pkg.cmd, 
                            "Invalid Package, error:%s"%e.__str__())
                sendpkg(conn, new_pkg)
        except (StopIteration, socket.error):
            pass
        finally:
            print("close session %s:%s"%conn.getpeername())
            try:
                conn.close()
            except Exception:
                pass
            exit()

    def handle_one(self, pkg):
        if not pkg:
            return
        res = None
        if pkg.cmd in self.cmdHandler:
            res = self.cmdHandler[pkg.cmd](pkg)
        else:
            res = Package(OPCODE["nocmd"])
        return res

    def load_account(self, path):
        try:
            with open(path, 'rb') as f:
                self.accounts = pickle.load(f)
                print("seccessful load accounts")
            # print(self.accounts['syf'].pwd)
                
        except (OSError, pickle.PickleError) as e:
            print("invalid account file: %s"%path)

    def dump_account(self, path):
        try:
            with open(path, 'wb') as f:
                pickle.dump(self.accounts, f)
                print("seccessful dump accounts")
        except (OSError, pickle.PickleError) as e:
            print("invalid account file: %s"%path)

    def add_account(self, user):
        self.accounts[user.name] = user            

    def rm_account(self, name):
        self.accounts.pop(name)

    def set_rootdir(self, path):
        if not path:
            return
        try:
            os.chdir(path)
        except OSError as e:
            print(e)

    def check_authorization(self, addr, actions):
        name = ''
        if self.needlogin:
            with self.conn_lock:
                if addr in self.connections:
                    name = self.connections[addr]
                else:
                    return False
            if name in self.accounts:
                auth = self.accounts[name].auth
                for a in actions:
                    if a not in auth:
                        return False
                return True
            else:
                return False
        else:
            return True

    def do_account(self, pkg):
        cmd = 'account'
        action = pkg.args['action']
        if not self.check_authorization(pkg.src, 'a'):
            return noauthpkg(cmd)
        elif action == 'list':
            resmsg = ''
            with self.conn_lock:
                for u in self.accounts.values():
                    resmsg += '%s %s %s\n' % (u.name, u.pwd, u.auth)
            return Package(OPCODE['ok'], {'cmd': cmd}, resmsg.encode())
        if action == 'add':
            name = pkg.args['name']
            pwd = pkg.args['pwd']
            auth = pkg.args['auth']
            user = User(name, pwd, auth)
            with self.conn_lock:
                if name not in self.accounts:
                    self.accounts[name] = user
                    self.dump_account(self.ACCOUNTS_path)
                else:
                    return errorpkg(cmd, "account %s already exists"%name)
        elif action == 'delete':
            name = pkg.args['name']
            with self.conn_lock:
                self.accounts.pop(name)
                self.dump_account(self.ACCOUNTS_path)                
        else:
            return errorpkg(cmd, "invalid action:%s to account"%action)
        return ok_resp(cmd)

    def do_list(self, pkg):
        path = get_curdir() + pkg.args['path']
        cmd = 'list'
        if not self.check_authorization(pkg.src, 'v'):
            return noauthpkg(cmd)
        # print("list %s"% path)
        if not ispath(path):
            return errorpkg("list", "invalid path: %s"%path)
        files = os.listdir(path)
        args = {'cmd': cmd}
        args['path'] = pkg.args['path']
        file_info = ''
        for f in files:
            size = os.path.getsize(path+'/'+f)
            # file_info += '%s:%s\n'%(f,size)
            file_info += '%s\n'%f
        new_pkg = Package(OPCODE['ok'], args, file_info.encode())
        return new_pkg

    def do_get(self, pkg):
        new_pkg = None
        if not self.check_authorization(pkg.src, 'vr'):
            return noauthpkg('get')
        path = get_curdir() + pkg.args['path']
        if not ispath(path):
            return errorpkg("get", "invalid path: %s"%path)
        # print('get from %s'%path)
        new_pkg = postpkg(path, '')
        new_pkg.args.pop('dst')
        new_pkg.cmd = OPCODE['ok']
        new_pkg.args['cmd'] = 'get'
        return new_pkg

    def do_post(self, pkg):
        if not self.check_authorization(pkg.src, 'vw'):
            return noauthpkg('post')
        args = pkg.args.copy()
        args['cmd'] = 'post'
        dst = get_curdir() + pkg.args['dst']
        fn = pkg.args['filename']
        # print('post to %s'%dst)            
        # if not ispath(dst) or not isfile(fn):
        #     msg = "invalid file:%s or path:%s"%(fn, dst)
        #     return errorpkg('post', msg)
        with open(dst + '/' + fn, 'wb') as f:
            f.write(pkg.data)
        return Package(OPCODE['ok'], args)

    def do_login(self, pkg):
        new_pkg = None
        args = {'cmd': 'login'}
        if not self.needlogin:
            new_pkg = Package(OPCODE['ok'], args)
        name = pkg.args['name']
        pwd = pkg.args['pwd']
        with self.conn_lock:
            if name in self.accounts and pwd == self.accounts[name].pwd:
                new_pkg = Package(OPCODE['ok'], args)
                self.connections[pkg.src] = name
            else: 
                new_pkg = noauthpkg('login')
        return new_pkg

    def do_close(self, pkg):
        cmd = 'close'
        addr = pkg.src
        with self.conn_lock:
            if addr in self.connections:
                self.connections.pop(addr)
        return ok_resp(cmd)

    def do_delete(self, pkg):
        cmd = 'delete'
        if not self.check_authorization(pkg.src, 'vwr'):
            return noauthpkg(cmd)
        path = get_curdir() + pkg.args['path']
        if os.path.isfile(path):
            os.remove(path)
        elif os.path.isdir(path):
            remove_recurse(path)
        else:
            msg = " path %s not found" %path
            return errorpkg(cmd, msg)
        return ok_resp(cmd)

    def do_mkdir(self, pkg):
        cmd = 'mkdir'        
        if not self.check_authorization(pkg.src, 'vw'):
            return noauthpkg(cmd)
        path = get_curdir() + pkg.args['path']
        if '..' in path:
            msg = "invalid path: %s"%path
            return errorpkg(cmd, msg)
        os.mkdir(path)
        return ok_resp(cmd)

    def do_rename(self, pkg):
        cmd = 'rename'
        if not self.check_authorization(pkg.src, 'vwr'):
            return noauthpkg(cmd)
        path = get_curdir() + pkg.args['path']
        src = pkg.args['src']
        dst = pkg.args['dst']
        if not ispath(path + src) or not ispath(dst):
            msg = "invalid path name: %s or %s" %(path+src, dst)
            return errorpkg(cmd, msg)
        os.rename(path+src, path+dst)
        return ok_resp(cmd)



if __name__ == '__main__':
    try:
        opts, args = getopt(sys.argv[1:],'h:p:l',['host=','port=','rootdir=', 'account=', 'login'])
    except GetoptError as e:
        print("invalid server argument: " + e.msg)
        exit()
    needlogin = False
    root_dir = None
    account = None
    host = '127.0.0.1'
    port = PORT
    for o, v in opts:
        if o in ('-l', '--login'):
            needlogin = True
        elif o in ('--rootdir'):
            root_dir = v
        elif o in ('--account'):
            account = v
        elif o in ('-h', '--host'):
            if ishost(v):
                host = v
            else:
                print("invalid host ip: %s" %v)
                exit()
        elif o in ('-p', '--port'):
            if isport(v):
                port = v
            else:
                print("invalid port: %s" %v)
                exit()    
    _Server = MyServer(ip=host, port=port, needlogin=needlogin)
    if root_dir is not None:
        _Server.set_rootdir(root_dir)
    if account is not None:
        _Server.load_account(account)
    elif needlogin:
        _Server.load_account(_Server.ACCOUNTS_path)
    _Server.start()
