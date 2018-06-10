from threading import Thread
import time
import random
import pickle
import socket
import struct
import select
import sys
import os
import fcntl
import netifaces


BULLY_REQUEST = 0
BULLY_ANSWER = 1
BULLY_ANNOUNCE = 2


MULTICAST_GROUP = '226.1.1.1'
PORT = 1234
SERVER_ADDRESS = ('', PORT)


class Packet:
    def __init__(self, type_msg, content):
        self.type_msg = type_msg
        self.content = content


class Bully:
    currClock = 0
    interval = 1
    coord = False
    ip_coord = ''
    myaddr = ''
    wait_asnwer = False
    temp_coor = False

    def clock(self, threadName, delay):
        currClock = 0
        while True:
            print(threadName, ' - ', currClock)
            currClock += delay
            time.sleep(self.interval)
            if currClock >= 20:
                break

    def handleUDPPacket(self, sock):
        data, addr = sock.recvfrom(1024)
        msg = pickle.loads(data)
        if addr[0] == self.myaddr:
            print('Own packet blocked')
            return
        if msg.type_msg == BULLY_REQUEST and not self.wait_asnwer:
            print('Received bully request with pid', msg.content)
            if os.getpid() > int(msg.content):
                print('Sending back my pid', os.getpid())
                sock.sendto(pickle.dumps(
                    Packet(BULLY_ANSWER, os.getpid())), addr)
        elif msg.type_msg == BULLY_ANSWER:
            print('Received packet-> Type: ', msg.type_msg,
                  '. Content: ', msg.content, '. From:', addr)
            coord = False
            self.temp_coor = False
            ip_coord = addr[0]
        elif msg.type_msg == BULLY_ANNOUNCE:
            print('New master: ', msg.content)
            ip_coord = msg.content
            coord = False

    def annouceVictory(self, sock):
        print('Annouces victory')
        msg = Packet(BULLY_ANNOUNCE, self.myaddr)
        sock.sendto(pickle.dumps(msg), (MULTICAST_GROUP, PORT))

    def sendBullyRequest(self, sock):
        pid = str(os.getpid())
        print('Sending BullyRequest with pid: ', pid)
        msg = Packet(BULLY_REQUEST, pid)
        sock.sendto(pickle.dumps(msg), (MULTICAST_GROUP, PORT))

        print('Waiting asnwers...')
        wait_asnwer = True
        self.temp_coor = True
        timeout = 2.0
        r_time = 0.0
        while True:
            b_time = time.time()
            timeout = timeout - r_time
            if(timeout <= 0.0):
                break
            r, w, e = select.select([sock], [], [sock], timeout)
            if not r:
                break
            for io2 in r:
                self.handleUDPPacket(io2)
            r_time = time.time() - b_time
        wait_asnwer = False
        if self.temp_coor == True:
            print("I'm the new coordinator")
            self.annouceVictory(sock)
            coord = True
        else:
            print("I'm not the coordinator")
            coord = False

    def run(self):
        print('Escolha a interface de rede a ser usada:')
        for i, val in enumerate(netifaces.interfaces()):
            print(i, '-', val)

        print('Digite:')
        opt = sys.stdin.readline()
        self.myaddr = str(netifaces.ifaddresses(
            netifaces.interfaces()[int(opt)])[2][0]['addr'])
        print('Utilizando o ip ', self.myaddr)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.sock.bind(SERVER_ADDRESS)
        group = socket.inet_aton(MULTICAST_GROUP)

        mreq = struct.pack('4sL', group, socket.INADDR_ANY)
        self.sock.setsockopt(
            socket.IPPROTO_IP,
            socket.IP_ADD_MEMBERSHIP,
            mreq)

        inputs = [self.sock, sys.stdin]
        outputs = []
        while True:
            print("Waiting...")
            readable, writable, exceptional = select.select(
                inputs, outputs, inputs)
            for io in readable:
                if io == self.sock:
                    self.handleUDPPacket(self.sock)
                elif io == sys.stdin:
                    self.sendBullyRequest(self.sock)
                    sys.stdin.readline()


bully = Bully()
bully.run()


'''
t = []

delay = random.randint(1, 10)
t.append((1, Thread(target=clock, args=('thread1', 1))))

delay = random.randint(1, 10)
t.append((2, Thread(target=clock, args=('thread2', 2))))

for x in t:
	x[1].start()

for x in t:
	x[1].join()
	print(x[0], ' finished!')
'''
