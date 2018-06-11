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
BERKELEY_REQUEST = 3
BERKELEY_RESPONSE = 4
BERKELEY_ADJUST = 5

interval = 0.2

MULTICAST_GROUP = '224.0.0.0'
PORT = 1234
SERVER_ADDRESS = ('', PORT)


class Packet:
    def __init__(self, type_msg, content):
        self.type_msg = type_msg
        self.content = content


class Bully:
    currClock = 10000
    delay = 0
    coord = False
    ip_coord = ''
    myaddr = ''
    wait_asnwer = False
    temp_coor = False
    berk_list = []

    def clock(self):
        while True:
            self.currClock += self.delay
            time.sleep(interval)

    def handleUDPPacket(self, sock):
        data, addr = sock.recvfrom(1024)
        msg = pickle.loads(data)
        if addr[0] == self.myaddr:
            return None
        if msg.type_msg == BULLY_REQUEST and not self.wait_asnwer:
            print('Received bully request with pid', msg.content)
            if os.getpid() > int(msg.content):
                print('Sending back my pid', os.getpid())
                sock.sendto(pickle.dumps(
                    Packet(BULLY_ANSWER, os.getpid())), addr)
        elif msg.type_msg == BULLY_ANSWER and self.wait_asnwer:
            print('Received packet-> Type: ', msg.type_msg,
                  '. Content: ', msg.content, '. From:', addr)
            self.temp_coor = False
            self.ip_coord = addr[0]
        elif msg.type_msg == BULLY_ANNOUNCE:
            print('New master: ', msg.content)
            self.ip_coord = msg.content
            self.coord = False
        elif msg.type_msg == BERKELEY_REQUEST:
            print('Received clock difference', int(msg.content), 'from', addr)
            diff = self.currClock - int(msg.content)
            print('Sending clock difference', diff, 'of clock', self.currClock)
            msg = Packet(BERKELEY_RESPONSE, str(diff))
            sock.sendto(pickle.dumps(msg), addr)
        elif msg.type_msg == BERKELEY_RESPONSE:
            self.berk_list.append((addr, msg.content))
            print('Received clock difference', int(msg.content), 'from', addr)
        elif msg.type_msg == BERKELEY_ADJUST:
            print('Received clock adjust: ', int(msg.content))
            print('Changing the clock from', self.currClock,
                  'to', self.currClock + int(msg.content))
            self.currClock = self.currClock + int(msg.content)

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
        self.wait_asnwer = True
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
        self.wait_asnwer = False
        if self.temp_coor == True:
            print("I'm the new coordinator")
            self.annouceVictory(sock)
            self.coord = True
        else:
            print("I'm not the coordinator")
            self.coord = False

    def startBerkeley(self, sock):
        print('Starting berkeley algorithm...')
        print('Sending clock', self.currClock)
        msg = Packet(BERKELEY_REQUEST, self.currClock)
        sock.sendto(pickle.dumps(msg), (MULTICAST_GROUP, PORT))
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
        print('Berkeley list:')
        media = 0.0
        for x, y in self.berk_list:
            media += int(y)
        media = int(media / (len(self.berk_list) + 1))
        for x, y in self.berk_list:
            msg = Packet(BERKELEY_ADJUST, str(media - int(y)))
            print('Adjust for', x, ':', media - int(y))
            sock.sendto(pickle.dumps(msg), x)

        print('Changing master clock from',
              self.currClock, 'to', self.currClock + media)
        self.currClock += media
        self.berk_list.clear()

    def run(self):
        print('Escolha a interface de rede a ser usada:')
        for i, val in enumerate(netifaces.interfaces()):
            print(i, '-', val)

        print('Digite:')
        opt = sys.stdin.readline()
        self.myaddr = str(netifaces.ifaddresses(
            netifaces.interfaces()[int(opt)])[2][0]['addr'])
        print('Utilizando o ip ', self.myaddr)

        print('Defina um delay para o relógio(em ms):')
        self.delay = int(sys.stdin.readline())
        Thread(target=self.clock).start()

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
                    if self.coord == True:
                        self.startBerkeley(self.sock)


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
