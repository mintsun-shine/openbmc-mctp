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
