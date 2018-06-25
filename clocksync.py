from threading import Thread
import time
import random
import pickle
import socket
import struct
import select
import sys
import os
import netifaces

BULLY_REQUEST       = 0
BULLY_ANSWER        = 1
BULLY_ANNOUNCE      = 2
BERKELEY_REQUEST    = 3
BERKELEY_RESPONSE   = 4
BERKELEY_ADJUST     = 5

INTERVAL    = 0.5
TIMEOUT     = 2.0


MULTICAST_GROUP = '224.0.0.0'
PORT            = 1234
SERVER_ADDRESS  = ('', PORT)

class Packet:
    def __init__(self, type_msg, content):
        self.type_msg = type_msg
        self.content = content


class Node:
    currClock   = 0
    delay       = 0
    isCoord     = False
    ip_coord    = ''
    myAddr      = ''
    nodeList    = []

    def clock(self):
        while True:
            self.currClock += self.delay
            time.sleep(INTERVAL)

    def handleUDPPacket(self, sock):
        data, addr = sock.recvfrom(1024)
        msg = pickle.loads(data)
        if addr[0] == self.myAddr:
            return None
        if msg.type_msg == BULLY_REQUEST:
            print('Requisicao bully recebido com pid', msg.content)
            if os.getpid() > int(msg.content):
                print('Enviando de volta pid', os.getpid())
                sock.sendto(pickle.dumps(Packet(BULLY_ANSWER, os.getpid())), addr)
                self.startBully(self.sock)
                if self.isCoord == True:
                    self.startBerkeley(self.sock)
        elif msg.type_msg == BULLY_ANSWER:
            print('Resposta da requisicao bully recebida com pid', int(msg.content), 'de', addr)
            self.isCoord = False
            self.ip_coord = addr[0]
        elif msg.type_msg == BULLY_ANNOUNCE:
            print('Novo mestre: ', msg.content)
            self.ip_coord = msg.content
            self.isCoord = False
        elif msg.type_msg == BERKELEY_REQUEST:
            print('Recebida requisicao de berkeley de relogio ', int(msg.content))
            diff = self.currClock - int(msg.content)
            print('Enviando diferenca do relogio', diff, 'Relogio:', self.currClock)
            msg = Packet(BERKELEY_RESPONSE, str(diff))
            sock.sendto(pickle.dumps(msg), addr)
        elif msg.type_msg == BERKELEY_RESPONSE:
            print('Recebida diferenca do relogio', int(msg.content), 'de', addr)
            self.nodeList.append((addr, msg.content))
        elif msg.type_msg == BERKELEY_ADJUST:
            print('Recebido ajuste de relogio: ', int(msg.content))
            print('Alterando relogio de', self.currClock, 'para', self.currClock + int(msg.content))
            self.currClock = self.currClock + int(msg.content)

    def annouceVictory(self, sock):
        print('Anuncia vitoria')
        msg = Packet(BULLY_ANNOUNCE, self.myAddr)
        sock.sendto(pickle.dumps(msg), (MULTICAST_GROUP, PORT))

    def startBully(self, sock):
        pid = str(os.getpid())
        print('Enviando requisicao bully com pid: ', pid)
        msg = Packet(BULLY_REQUEST, pid)
        sock.sendto(pickle.dumps(msg), (MULTICAST_GROUP, PORT))
        print('Aguardando respostas...')
        remaining_time = time.time() + TIMEOUT
        self.isCoord = True
        while True:
            systemTime = time.time()
            if(systemTime >= remaining_time):
                break
            r, w, e = select.select([sock], [], [sock], remaining_time - systemTime)
            if not r:
                break
            else:
                self.handleUDPPacket(sock)
        if self.isCoord == True:
            print("Sou o novo coordenador!")
            self.annouceVictory(sock)
            self.isCoord = True
        else:
            print("Nao sou o coordenador")
            self.isCoord = False

    def startBerkeley(self, sock):
        print('Iniciando o algoritmo de Berkeley...')
        print('Enviando relogio', self.currClock)
        msg = Packet(BERKELEY_REQUEST, self.currClock)
        sock.sendto(pickle.dumps(msg), (MULTICAST_GROUP, PORT))
        remaining_time = time.time() + TIMEOUT
        while True:
            systemTime = time.time()
            if(systemTime <= remaining_time):
                r, w, e = select.select(
                    [sock], [], [sock], remaining_time - systemTime)
            else:
                break
            if not r:
                break
            else:
                self.handleUDPPacket(sock)

        print('Lista de escravos:')
        average = 0.0
        for addr, content in self.nodeList:
            average += int(content)
        average = int(average / (len(self.nodeList) + 1))
        for addr, content in self.nodeList:
            msg = Packet(BERKELEY_ADJUST, str(average - int(content)))
            print('Ajusta relogio de', addr, ':', 'em', average - int(content))
            sock.sendto(pickle.dumps(msg), addr)
        print('Alterando o relogio do mestre de', self.currClock, 'para', self.currClock + average)
        self.currClock += average
        self.nodeList.clear()

    def run(self):
        print('Escolha a interface de rede a ser usada:')
        for i, val in enumerate(netifaces.interfaces()):
            print(i, '-', val)
        while True:
            print('Digite:')
            try:
                opt = int(sys.stdin.readline())
                if opt >= len(netifaces.interfaces()) or opt < 0:
                    raise Exception()
            except Exception:
                print('Entrada invalida')
            else:
                break
        self.myAddr = str(netifaces.ifaddresses(netifaces.interfaces()[opt])[2][0]['addr'])
        print('Utilizando o ip ', self.myAddr)

        while True:
            print('Defina um delay para o relógio(em ms):')
            try:
                self.delay = int(sys.stdin.readline())
                if self.delay <= 0:
                    raise Exception()
            except Exception:
                print('Entrada invalida')
            else:
                break

        Thread(target=self.clock).start()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(SERVER_ADDRESS)
        group = socket.inet_aton(MULTICAST_GROUP)
        mreq = struct.pack('4sL', group, socket.INADDR_ANY)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        inputs = [self.sock, sys.stdin]
        outputs = []
        while True:
            print("Aguardando acao...")
            readable, writable, exceptional = select.select(inputs, outputs, inputs)
            for io in readable:
                if io == self.sock:
                    self.handleUDPPacket(self.sock)
                elif io == sys.stdin:
                    self.startBully(self.sock)
                    sys.stdin.readline()
                    if self.isCoord == True:
                        self.startBerkeley(self.sock)


if __name__ == '__main__':
    node = Node()
    node.run()
