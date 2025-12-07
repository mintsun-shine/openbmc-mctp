#!/usr/bin/env python3

import sys
import socket
import struct
import array
import os
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

# Constants
AF_MCTP = 45
MCTP_NET_ANY = 0
MCTP_ADDR_ANY = 0
MCTP_TAG_OWNER = 0x08

DBUS_NAME = 'xyz.openbmc_project.Mctp.Tool'
OBJ_PATH = '/xyz/openbmc_project/mctp/tool'
IFACE_NAME = 'xyz.openbmc_project.Mctp.Tool'

class MctpTool(dbus.service.Object):
    def __init__(self, bus):
        self.bus = bus
        dbus.service.Object.__init__(self, bus, OBJ_PATH)

    @dbus.service.method(IFACE_NAME, in_signature='yynay', out_signature='')
    def Send(self, eid, msg_type, network, payload):
        """
        Send an MCTP message.
        :param eid: destination EID
        :param msg_type: MCTP message type key
        :param network: Network ID (0 for any)
        :param payload: Message payload
        """
        print(f"Send: EID={eid}, Type={msg_type}, Net={network}, Len={len(payload)}")
        try:
            s = socket.socket(AF_MCTP, socket.SOCK_DGRAM)
            # addr: (network, eid, type, tag)
            addr = (network, eid, msg_type, MCTP_TAG_OWNER)
            s.connect(addr)
            s.send(bytes(payload))
            s.close()
            print("Message sent successfully")
        except Exception as e:
            print(f"Error sending: {e}")
            raise dbus.exceptions.DBusException(f"xyz.openbmc_project.Common.Error.InternalFailure: {str(e)}")

    @dbus.service.method(IFACE_NAME, in_signature='yynayq', out_signature='ay')
    def SendRecv(self, eid, msg_type, network, payload, timeout_ms):
        """
        Send an MCTP message and wait for a response.
        :param timeout_ms: Timeout in milliseconds
        """
        print(f"SendRecv: EID={eid}, Type={msg_type}, Net={network}, Len={len(payload)}, Timeout={timeout_ms}ms")
        try:
            s = socket.socket(AF_MCTP, socket.SOCK_DGRAM)
            
            # Bind to receive response
            # we let the kernel assign a local address, but we might need to bind to specific network if needed.
            # Usually strict binding isn't required for client sockets in AF_MCTP unless we want to filter receiving.
            # But we DO need to Send with TAG_OWNER, and the response will come back with TAG_OWNER | MCTP_TAG_PREALLOC (cleared).
            # The kernel handles the tag matching if we trace correctly.
            
            # Implementation detail: Kernel MCTP socket semantics for Request/Response:
            # If we connect() with TAG_OWNER, send(), and then recv(), the kernel should give us the response.
            
            addr = (network, eid, msg_type, MCTP_TAG_OWNER)
            s.connect(addr)
            
            s.settimeout(timeout_ms / 1000.0)
            
            s.send(bytes(payload))
            
            # Receive response
            # We expect a response from the same EID/Type/Net.
            resp_data = s.recv(4096) # Max MCTP MTU is usually small (~64K max but typical < 4K)
            s.close()
            print(f"Received response: {len(resp_data)} bytes")
            return dbus.Array(resp_data, signature='y')
            
        except socket.timeout:
            print("Timeout waiting for response")
            raise dbus.exceptions.DBusException("xyz.openbmc_project.Common.Error.Timeout: Request Timed Out")
        except Exception as e:
            print(f"Error in SendRecv: {e}")
            raise dbus.exceptions.DBusException(f"xyz.openbmc_project.Common.Error.InternalFailure: {str(e)}")

    @dbus.service.method(IFACE_NAME, in_signature='say', out_signature='')
    def SendRawPacket(self, interface, payload):
        """
        Send a raw MCTP packet to a specific interface.
        :param interface: Interface name (e.g., mctpi2c15)
        :param payload: Full MCTP packet (Header + Body)
        """
        print(f"SendRawPacket: Iface={interface}, Len={len(payload)}")
        try:
            # AF_PACKET = 17
            # ETH_P_ALL = 0x0003 (htons not strictly needed if we bind) or specific MCTP EtherType if applicable.
            # MCTP over serial/binding usually sits on top of tty or i2c, but AF_PACKET allows sending to the netdev.
            # We use ETH_P_ALL to validly bind.
            ETH_P_ALL = 3
            
            s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_ALL))
            s.bind((interface, 0))
            s.send(bytes(payload))
            s.close()
            print("Raw packet sent successfully")
            
        except Exception as e:
            print(f"Error sending raw packet: {e}")
            raise dbus.exceptions.DBusException(f"xyz.openbmc_project.Common.Error.InternalFailure: {str(e)}")

    @dbus.service.method(IFACE_NAME, in_signature='sayq', out_signature='ay')
    def SendReceiveRawPacket(self, interface, payload, timeout_ms):
        """
        Send a raw MCTP packet and wait for the next incoming packet on the interface.
        :param interface: Interface name
        :param payload: Full MCTP packet
        :param timeout_ms: Timeout in milliseconds
        """
        print(f"SendReceiveRawPacket: Iface={interface}, len={len(payload)}, timeout={timeout_ms}")
        try:
            ETH_P_ALL = 3
            PACKET_OUTGOING = 4
            
            s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_ALL))
            s.bind((interface, 0))
            s.settimeout(timeout_ms / 1000.0)
            
            s.send(bytes(payload))
            
            while True:
                data, addr = s.recvfrom(4096)
                # addr tuple: (ifname, proto, pkttype, hatype, addr)
                pkttype = addr[2]
                
                # Filter out the packet we just sent (OUTGOING)
                if pkttype == PACKET_OUTGOING:
                    continue
                    
                # Return the first incoming packet
                s.close()
                print(f"Received raw packet: {len(data)} bytes")
                return dbus.Array(data, signature='y')

        except socket.timeout:
            print("Timeout waiting for raw response")
            raise dbus.exceptions.DBusException("xyz.openbmc_project.Common.Error.Timeout: Request Timed Out")
        except Exception as e:
            print(f"Error in SendReceiveRawPacket: {e}")
            raise dbus.exceptions.DBusException(f"xyz.openbmc_project.Common.Error.InternalFailure: {str(e)}")

def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    name = dbus.service.BusName(DBUS_NAME, bus)
    _ = MctpTool(bus)
    
    loop = GLib.MainLoop()
    print(f"Service {DBUS_NAME} running...")
    loop.run()

if __name__ == '__main__':
    main()
