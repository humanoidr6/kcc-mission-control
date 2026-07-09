import eventlet
eventlet.monkey_patch()

import socket
import threading
import time
import json
from flask import Flask, render_template
from flask_socketio import SocketIO
import struct

app = Flask(__name__)
app.config['SECRET_KEY'] = 'missioncontrol'
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

UDP_IP = "127.0.0.1"
UDP_PORT = 52001

def parse_ccsds(data):
    """
    Very basic CCSDS primary header parser.
    First 6 bytes:
    - Version (3 bits), Type (1 bit), Sec. Hdr Flag (1 bit), APID (11 bits)
    - Seq Flags (2 bits), Seq Count (14 bits)
    - Packet Data Length (16 bits)
    """
    if len(data) < 6:
        return {"error": "Packet too short"}
    
    header = struct.unpack(">HHH", data[:6])
    word1, word2, length = header
    
    apid = word1 & 0x07FF
    seq_count = word2 & 0x3FFF
    
    payload = data[6:]
    # The 'payload' IS the telemetry data (27 bytes) since the 6 byte header is already stripped.
    telemetry_data = payload
    decoded_values = {}
    try:
        if len(telemetry_data) == 27:
            unpacked = struct.unpack('<ffBhhhhhhhhh', telemetry_data)
            decoded_values = {
                "temperature": round(unpacked[0], 2),
                "humidity": round(unpacked[1], 2),
                "ldr": bool(unpacked[2]),
                "accelX": unpacked[3],
                "accelY": unpacked[4],
                "accelZ": unpacked[5],
                "gyroX": unpacked[6],
                "gyroY": unpacked[7],
                "gyroZ": unpacked[8],
                "magX": unpacked[9],
                "magY": unpacked[10],
                "magZ": unpacked[11]
            }
        else:
            decoded_values = {"error": f"Invalid length {len(payload)}"}
    except Exception as e:
        decoded_values = {"error": str(e)}

    return {
        "apid": apid,
        "seq_count": seq_count,
        "length": length + 1,
        "payload_hex": payload.hex(),
        "telemetry": decoded_values,
        "timestamp": time.strftime("%H:%M:%S")
    }

def udp_listener():
    print(f"Starting UDP Listener on port {UDP_PORT}...")
    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind((UDP_IP, UDP_PORT))
            while True:
                data, addr = sock.recvfrom(4096)
                print(f"Received {len(data)} bytes")
                parsed = parse_ccsds(data)
                
                if "error" not in parsed:
                    print(parsed)
                    # Emit data to frontend
                    socketio.emit('telemetry_packet', parsed)
                else:
                    print(f"Packet error: {parsed['error']}")
        except Exception as e:
            print(f"UDP Listener Error: {e}. Restarting in 2 seconds...")
            time.sleep(2)

@app.route('/')
def index():
    return render_template('index.html')

# Simulated test route
@socketio.on('inject_test_packet')
def handle_test_packet():
    print("Injecting test packet...")
    # Dummy CCSDS packet: APID=123, Seq=45, Length=10, Payload="TESTDATA"
    # Word1: Vers=0(000), Type=0, SHdr=0, APID=123 (0x7B) -> 0x007B
    # Word2: Flags=3(11), Seq=45 (0x2D) -> 0xC02D
    # Length: 7 (means 8 bytes payload) -> 0x0007
    dummy_header = struct.pack(">HHH", 0x007B, 0xC02D, 0x0007)
    dummy_payload = b"TESTDATA"
    parsed = parse_ccsds(dummy_header + dummy_payload)
    socketio.emit('telemetry_packet', parsed)

if __name__ == '__main__':
    # Start UDP listener in background
    threading.Thread(target=udp_listener, daemon=True).start()
    print("Mission Control Dashboard running at http://127.0.0.1:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)
