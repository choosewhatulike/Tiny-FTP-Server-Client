'''
    The GUI front-end for client
'''

import tkinter as tk
from tkinter import messagebox as messagebox
from tkinter import simpledialog as simpledialog
from tkinter import filedialog

from uility import *
from shell import Remotedir, init, MyClient, Task, _run_task

client = None
DIRs = []

def select_one(list_box):
    s = filelist.curselection()
    if len(s) == 0 or len(s) >= 2:
        return None
    return DIRs[s[0]]

def gui_run_task(t):
    client.add_task(t)
    t.wait_done()
    t.callback(t)

def handler(cmd):
    global Remotedir
    path = Remotedir
    args = {}
    t = None
    try:
        if cmd == 'login':
            args['name'] = ety_name.get()
            args['pwd'] = ety_pwd.get()
            t = Task(gui_no_return, cmd, args)
        elif cmd == 'connect':
            args['host'] = ety_host.get()
            args['port'] = int(ety_port.get())
            t = Task(gui_no_return, cmd, args)
        elif cmd == 'mkdir':
            dn = simpledialog.askstring(title=cmd, prompt="Imput dir name")
            if not dn: return
            args['path'] = Remotedir + dn
            t = Task(gui_no_return, cmd, args)            
        elif cmd == 'delete':
            path = select_one(filelist)
            if path is None:
                messagebox.showerror(title='Error', message="invalid selection")
                return
            t = Task(gui_no_return, cmd, {'path': Remotedir + path})
        elif cmd == 'rename':
            src = select_one(filelist)
            if src is None:
                messagebox.showerror(title='Error', message="invalid selection")
                return
            dst = simpledialog.askstring(title=cmd, prompt="input your willing name")
            if not dst: return
            t = Task(gui_no_return, cmd,  {'path': Remotedir, 'src': src, 'dst': dst})
        elif cmd == 'get':
            dn = filedialog.askdirectory()
            if not dn: return
            path = select_one(filelist)
            if path is None:
                messagebox.showerror(title='Error', message="invalid selection")
                return
            t = Task(gui_no_return, cmd, {'path': Remotedir + path, 'dst': dn})
        elif cmd == 'post':
            fn = filedialog.askopenfilename()
            if not fn: return
            t = Task(gui_no_return, cmd, args={'path': fn, 'dst': Remotedir})
        elif cmd == 'list':
            t = Task(gui_after_ls, cmd, {'path': Remotedir})
        elif cmd == 'cd':
            dst = select_one(filelist)
            if dst is None:
                messagebox.showerror(title='Error', message="invalid selection")
                return
            t = Task(gui_after_cd, 'list', {'path': Remotedir + dst})
        elif cmd == 'account add':
            name = simpledialog.askstring(title='account', prompt='Add Name')
            if not name: return
            pwd = simpledialog.askstring(title='account', prompt='Enter Password')
            if not pwd: return
            auth = simpledialog.askstring(title='account', prompt='Decide Autheritation')
            if not auth: return
            t = Task(gui_after_account, 'account', {'action':'add', 'name':name, 'pwd': pwd, 'auth':auth})
        elif cmd == 'account delete':
            name = simpledialog.askstring(title='account', prompt='Delete Name')
            if not name: return
            t = Task(gui_after_account, 'account', {'action':'delete', 'name':name})
        elif cmd == 'account list':
            t = Task(gui_after_account, 'account', {'action':'list'})
        else:
            messagebox.showerror(title='Error', message="No Such Command")
            return
    except Exception as e:
        messagebox.showerror(title='Error', message="Invalid Parameter")
        raise
    if t is None:
        return
    
    gui_run_task(t)


def gui_no_return(task):
    global Remotedir
    if task.ans.cmd == OPCODE['ok']:
        if task.cmd in ('connect', 'login'):
            Remotedir = ''
        messagebox.showinfo(title='OK', message='command %s done successfully!' % task.cmd)
        if task.cmd in ('mkdir', 'delete', 'post', 'get', 'rename'):
            handler('list')
    else:
        messagebox.showerror(title='Error', message=task.ans.args['error'])

def gui_after_ls(task):
    global DIRs
    if task.ans.cmd != OPCODE['ok']:
        messagebox.showerror(title='Error', message=task.ans.args['error'])
        return
    elif len(task.ans.data) == 0:
        messagebox.showerror(title='Error', message="ERROR: No file in path")
    DIRs = task.ans.data.decode().split()
    while filelist.size() > 0:
        filelist.delete(tk.END)
    for item in DIRs:
        filelist.insert(tk.END, item)

def gui_after_cd(task):
    global Remotedir
    if task.ans.cmd != OPCODE['ok']:
        messagebox.showerror(title='Error', message=task.ans.args['error'])
        return
    Remotedir = task.ans.args['path']
    Remotedir = os.path.normpath(Remotedir)
    if not Remotedir.endswith('/'):
        Remotedir += '/'
    gui_after_ls(task)

def gui_after_account(task):
    if task.ans.cmd == OPCODE['ok'] and task.args['action'] == 'list':
        ac_root = tk.Tk(className="Account List")
        ac_list = tk.Listbox(ac_root)
        for line in task.ans.data.decode().split('\n'):
            ac_list.insert(tk.END, line)
        ac_list.pack(fill='both')
        ac_root.mainloop()
    else:
        gui_no_return(task)

def cd_back():
    global Remotedir
    t = Task(gui_after_cd, 'list', {'path': Remotedir + '..'})
    gui_run_task(t)
        
if __name__ == '__main__':
    root = tk.Tk(className="Syf's FPT")
    menubar = tk.Menu(root)
    filelist = tk.Listbox(root)
    frame_log = tk.Frame(root)
    frame_con = tk.Frame(root)
    frame_btn = tk.Frame(root)

    menubar.add_command(label='mkdir', command=lambda:handler('mkdir'))
    menubar.add_command(label='delete', command=lambda:handler('delete'))
    menubar.add_command(label='post', command=lambda:handler('post'))
    menubar.add_command(label='get', command=lambda:handler('get'))
    menubar.add_command(label='rename', command=lambda:handler('rename'))

    ac_menu = tk.Menu(menubar, tearoff=0)
    ac_menu.add_command(label='add', command=lambda:handler('account add'))
    ac_menu.add_command(label='delete', command=lambda:handler('account delete'))
    ac_menu.add_command(label='list', command=lambda:handler('account list'))
    menubar.add_cascade(label='account', menu=ac_menu)

    lb_name = tk.Label(frame_log, text='name')
    lb_pwd = tk.Label(frame_log, text='Password')
    ety_name = tk.Entry(frame_log)
    ety_pwd = tk.Entry(frame_log)
    btn_login = tk.Button(frame_log, text='login', command=lambda:handler('login'))

    lb_host = tk.Label(frame_con, text='host IP')
    lb_port = tk.Label(frame_con, text='port')
    ety_host = tk.Entry(frame_con)
    ety_port = tk.Entry(frame_con)
    btn_connect = tk.Button(frame_con, text='connect', command=lambda:handler('connect'))

    ety_host.insert(tk.END, '127.0.0.1')
    ety_port.insert(tk.END, '20202')
    
    btn_cd = tk.Button(frame_btn, text="go", command=lambda:handler('cd'))
    btn_ls = tk.Button(frame_btn, text='refresh', command=lambda:handler('list'))
    btn_back = tk.Button(frame_btn, text='back', command=cd_back)

    root.config(menu=menubar)

    frame_con.pack()
    frame_log.pack()
    filelist.pack(fill='both')
    frame_btn.pack()

    lb_host.pack(side='left')
    ety_host.pack(side='left')
    lb_port.pack(side='left')
    ety_port.pack(side='left')
    btn_connect.pack(side='right')

    lb_name.pack(side='left')
    ety_name.pack(side='left')
    lb_pwd.pack(side='left')
    ety_pwd.pack(side='left')
    btn_login.pack(side='right')

    btn_cd.pack(side='right')
    btn_ls.pack(side='right')
    btn_back.pack(side='left')

    Remotedir = '.'
    client = MyClient()
    client.run()
    
    root.mainloop()

    client.shutdown()

