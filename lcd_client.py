#!/usr/bin/env python3
"""
LCD Client - Network client for sending status to LCD server
Can be used standalone or integrated into live_webcam.py
"""

import socket
import json
import time
import threading
from queue import Queue, Empty


class LCDClient:
    def __init__(self, server_ip, server_port=5555, reconnect=True):
        """
        Initialize LCD network client
        
        Args:
            server_ip: IP address of Raspberry Pi running lcd_server.py
            server_port: Port number (default: 5555)
            reconnect: Auto-reconnect on connection loss
        """
        self.server_ip = server_ip
        self.server_port = server_port
        self.reconnect = reconnect
        self.connected = False
        self.running = False
        self.socket = None
        
        # Message queue for async sending
        self.message_queue = Queue()
        self.send_thread = None
    
    def connect(self):
        """Connect to LCD server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)
            self.socket.connect((self.server_ip, self.server_port))
            self.connected = True
            print(f"✅ Connected to LCD server at {self.server_ip}:{self.server_port}")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to LCD server: {e}")
            self.connected = False
            return False
    
    def start(self):
        """Start the client (async mode)"""
        if not self.connect():
            if not self.reconnect:
                return False
        
        self.running = True
        
        # Start background thread for sending messages
        self.send_thread = threading.Thread(target=self._send_loop)
        self.send_thread.daemon = True
        self.send_thread.start()
        
        return True
    
    def _send_loop(self):
        """Background thread for sending messages"""
        while self.running:
            try:
                # Get message from queue (with timeout)
                try:
                    message = self.message_queue.get(timeout=1.0)
                except Empty:
                    # Send periodic ping to keep connection alive
                    if self.connected:
                        self._send_message({'type': 'ping'})
                    continue
                
                # Send the message
                if not self.connected and self.reconnect:
                    self.connect()
                
                if self.connected:
                    success = self._send_message(message)
                    if not success and self.reconnect:
                        print("⚠️ Connection lost, attempting to reconnect...")
                        self.connected = False
                        time.sleep(1)
                        self.connect()
                        
            except Exception as e:
                print(f"❌ Send loop error: {e}")
                time.sleep(1)
    
    def _send_message(self, message):
        """Send a single message (internal use)"""
        if not self.socket:
            return False
        
        try:
            json_str = json.dumps(message) + '\n'
            self.socket.sendall(json_str.encode('utf-8'))
            return True
        except Exception as e:
            print(f"❌ Send error: {e}")
            self.connected = False
            return False
    
    def update_display(self, status, object_count=0, fps=0.0):
        """
        Update LCD display with status
        
        Args:
            status: 'SAFE' or 'STOP'
            object_count: Number of detected objects
            fps: Frames per second
        """
        message = {
            'type': 'status',
            'status': status,
            'object_count': object_count,
            'fps': fps
        }
        
        if self.running:
            self.message_queue.put(message)
        else:
            # Synchronous mode
            if not self.connected:
                self.connect()
            if self.connected:
                self._send_message(message)
    
    def display_message(self, line1, line2=''):
        """
        Display custom message on LCD
        
        Args:
            line1: First line of text
            line2: Second line of text
        """
        message = {
            'type': 'message',
            'line1': line1,
            'line2': line2
        }
        
        if self.running:
            self.message_queue.put(message)
        else:
            if not self.connected:
                self.connect()
            if self.connected:
                self._send_message(message)
    
    def close(self):
        """Close connection"""
        self.running = False
        
        if self.send_thread:
            self.send_thread.join(timeout=2.0)
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        
        self.connected = False
        print("✅ LCD client disconnected")


def main():
    """Test the LCD client"""
    import argparse
    
    parser = argparse.ArgumentParser(description='LCD Client Test (Laptop)')
    parser.add_argument('server_ip', help='IP address of Raspberry Pi running lcd_server.py')
    parser.add_argument('--port', type=int, default=5555, help='Server port (default: 5555)')
    
    args = parser.parse_args()
    
    # Create client
    client = LCDClient(args.server_ip, args.port)
    
    # Test connection
    if not client.connect():
        print("❌ Could not connect to server")
        return
    
    try:
        print("✅ Testing LCD display...")
        
        # Test 1: Display message
        print("📝 Displaying welcome message...")
        client.display_message("Pathguard", "Network test")
        time.sleep(2)
        
        # Test 2: SAFE status
        print("✅ Testing SAFE status...")
        client.update_display('SAFE', object_count=0, fps=30.5)
        time.sleep(3)
        
        # Test 3: STOP status
        print("⚠️ Testing STOP status...")
        client.update_display('STOP', object_count=3, fps=28.2)
        time.sleep(3)
        
        # Test 4: Alternating status
        print("🔄 Alternating SAFE/STOP...")
        for i in range(5):
            status = 'SAFE' if i % 2 == 0 else 'STOP'
            client.update_display(status, object_count=i, fps=30.0)
            time.sleep(1)
        
        # Final message
        client.display_message("Test complete", "Success!")
        time.sleep(2)
        
        print("✅ Test complete!")
        
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted")
    finally:
        client.close()


if __name__ == '__main__':
    main()
