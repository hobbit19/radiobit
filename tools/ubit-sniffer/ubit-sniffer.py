"""
Python2.x client for the Micro:Bit sniffer firmware.

Still some work to do: add a cool display mode for raw packets.
"""

import serial
import argparse
from time import sleep, time
from struct import pack

class TargetError(Exception):
    """
    Bad Target.
    """
    def __init__(self):
        Exception.__init__(self)

class ChannelError(Exception):
    """
    Wrong channel
    """
    def __init__(self):
        Exception.__init__(self)

class ESBSniffer(object):
    """
    EnhancedShockBurst/ShockBurst/BLELL sniffer interface.

    This class drives the Micro:Bit running our middleware to sniff
    various types of packets.

    A *send* method is also provided, allowing you to send specifically
    crafted packets through the middleware (but expect timing issues).
    """

    def __init__(self, device, timeout=5):
        """
        Initialize our device, default mode and rate.
        """
        self.dev = serial.Serial(device, 115200, timeout=1)
        self.mode = 0 # 0 - sniff, 1 - follow
        self.channel = 0
        self.rate = 1
        self.addr = '0000000000'.decode('hex')

    def _send(self, buf):
        """
        Send buffer to middleware.
        """
        enc_buf = '%02x'%len(buf) + buf.encode('hex')
        #print enc_buf
        self.dev.write(enc_buf)

    def read(self, size):
        """
        Read size bytes from uart.
        """
        out = ''
        while len(out) < size:
            out += self.dev.read(size - len(out))
            #print out
        return out

    def close(self):
        self.dev.close()

    def _ack(self, op):
        """
        Acknowledge op.
        """
        #self.dev.flush()
        ack = ''
        while (ack != op):
            ack = self.read(1)
        #print 'ack %s (%s)' % (ack,op)

    def flush(self):
        self.dev.flush()

    def reset(self, raw=0, rate=1):
        self.flush()
        self._send('r'+chr(rate)+chr(raw))
        self._ack('r')
        self.mode = 0

    def set_rate(self, rate):
        """
        Set rate
        """
        self._send('b'+chr(rate))
        self._ack('b')
        self.rate = rate

    def set_channel(self, channel):
        """
        Set channel
        """
        self._send('c'+chr(channel))
        self._ack('c')
        self.channel = channel

    def set_address(self, address):
        """
        Set address
        """
        addr = pack('>I', (address >> 8))
        group = pack('>B', address&0x00000000FF)
        self._send('f'+addr+group)
        self._ack('f')
        self.mode = 1
        self.addr = addr+group

    def lock_channel(self):
        """
        Set channel lock
        """
        self._send('m\x02')
        self._ack('m')

    def ping(self):
        """
        If address has been set, tune the sniffer to the correct
        channel the device has been found on.
        """
        self._send('t')
        self._ack('t')
        channel = ord(self.read(1))
        if channel != 101:
            self.channel = channel
            return channel
        else:
            return None

    def receive(self):
        """
        Receive packets
        """
        self._send('p')
        pkt = self.read(1)
        if pkt=='p':
            size = self.read(1)
            if size != '':
                size = ord(size)
                if size>0:
                    data = self.read(size)
                    return data
                else:
                    return None
            else:
                return None
        else:
            return None

    def send(self, data):
        """
        Send data
        """
        self._send('s'+chr(len(data))+data)
        return (self.read(1) == 's')

if __name__ == '__main__':


    parser = argparse.ArgumentParser(
        description='Micro:bit Enhanced ShockBurst Sniffer'
    )
    parser.add_argument(
        '--device', '-d',
        type=str,
        dest='device',
        action='store',
        default='/dev/ttyACM0',
        help='Serial device to use (/dev/ttyACM0 by default)'
    )
    parser.add_argument(
        '--target', '-t',
        dest='target',
        required=False,
        help='Target MAC'
    )
    parser.add_argument(
        '--channel', '-c',
        dest='channel',
        type=int,
        required=False,
        help='Channel to sniff on'
    )
    parser.add_argument(
        '--data-rate','-b',
        dest='rate',
        type=int,
        default=1,
        required=False,
        help='Set data rate, 0: 1MBit | 1: 2MBit | 2: 250Kbit | 3: BLE LinkLayer'
    )
    parser.add_argument(
        '--raw', '-r',
        dest='raw',
        action='store_true',
        required=False,
        help='Sniff raw packets (SB, ESB, BLE LinkLayer)'
    )
    args = parser.parse_args()
    try:
        print '\033[1muBit sniffer uses device %s\033[0m' % args.device
        print '\033[1minitializing device ...\033[0m'
        sniffer  = ESBSniffer(args.device)
        sniffer.reset(raw=args.raw,rate=args.rate)
        channel = 1
        rates = ['1Mbit', '2Mbit','250Kbit','BLE LL']
        print '\033[1mSelecting rate: %s\033[0m' % rates[args.rate]

        if args.channel is not None:
            if args.channel >= 0 and args.channel <= 100:
                sniffer.set_channel(args.channel)
                sniffer.lock_channel()
            else:
                raise ChannelError()

        if args.target is not None:
            target = int(args.target, 16)
            if target<0xffffffffff:
                sniffer.set_address(target)
                print '\033[1mStarting following target \033[92m%s\033[0m\033[1m ...\033[0m\033[0m' % hex(target)
            else:
                raise TargetError()
        else:
            print '\033[1mStarting sniffing ...\033[0m'

        print ''
        while True:
            pkt = sniffer.receive()
            if pkt is not None:
                if sniffer.mode == 0:
                    channel = ord(pkt[0])
                    addr = pkt[1:6]
                    data = pkt[6:]
                    print '\033[92m%03d\033[0m \033[95m%02x%02x%02x%02x%02x >\033[0m\033[0m %s' % (
                        channel,
                        ord(addr[0]),
                        ord(addr[1]),
                        ord(addr[2]),
                        ord(addr[3]),
                        ord(addr[4]),
                        data.encode('hex')
                    )
                else:
                    channel = ord(pkt[0])
                    print '\033[92m%03d\033[0m \033[95m%02x%02x%02x%02x%02x >\033[0m\033[0m %s' % (
                        channel,
                        ord(sniffer.addr[0]),
                        ord(sniffer.addr[1]),
                        ord(sniffer.addr[2]),
                        ord(sniffer.addr[3]),
                        ord(sniffer.addr[4]),
                        pkt[1:].encode('hex')
                    )
    except ChannelError as error:
        print('\033[91mWrong channel: %d\033[0m' % args.channel)
    except TargetError as error:
        print('\033[91mWrong target: %s\033[0m' % args.target)
    except KeyboardInterrupt as error:
        print('\033[1mTerminating sniffing ...\033[0m')
        sniffer.close()
    except serial.serialutil.SerialException as error:
        print('\033[91mDevice not found (%s)\033[0m' % args.device)
    except Exception, error:
        print error
