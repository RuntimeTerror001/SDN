
import json
import time
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

# =====================================================
# SIMULATED SDN CONTROLLER FOR A LOCAL ASSIGNMENT DEMO
# =====================================================

SWITCHES = {
    "s1": {
        "ports": [
            {"port_no": 1, "tx_rate_bps": 5000000},
            {"port_no": 2, "tx_rate_bps": 15000000}
        ]
    },
    "s2": {
        "ports": [
            {"port_no": 1, "tx_rate_bps": 2000000}
        ]
    }
}

installed_flows = []
mac_table = {}
queues = {}
intents = {}


class ControllerHandler(BaseHTTPRequestHandler):
    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/switches":
            self.send_json({"switches": list(SWITCHES.keys())})

        elif self.path.startswith("/stats/"):
            switch_id = self.path.split("/")[-1]
            if switch_id in SWITCHES:
                self.send_json(SWITCHES[switch_id])
            else:
                self.send_json({"error": "Switch not found"}, 404)

        elif self.path == "/intents":
            self.send_json({"intents": intents})

        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")

        if self.path == "/flows":
            installed_flows.append(payload)
            self.send_json({
                "result": "Flow rule installed (simulated)",
                "flow": payload
            }, 201)

        elif self.path == "/intents":
            intent_id = "intent-" + str(len(intents) + 1)
            payload["id"] = intent_id
            payload["state"] = "INSTALLED"
            intents[intent_id] = payload
            self.send_json(payload, 201)

        else:
            self.send_json({"error": "Not found"}, 404)

    def log_message(self, *args):
        pass


def start_controller():
    server = HTTPServer(("127.0.0.1", 8765), ControllerHandler)
    server.serve_forever()


# Start the local mock controller.
Thread(target=start_controller, daemon=True).start()
time.sleep(0.5)

BASE_URL = "http://127.0.0.1:8765"


def heading(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


# =====================================================
# SCENARIO 1: REST API, SWITCH STATS, ICMP BLOCK
# =====================================================

def scenario1():
    heading("SCENARIO 1: Automated Network Policy Engine")

    response = requests.get(BASE_URL + "/switches")
    response.raise_for_status()
    switches = response.json()["switches"]
    print("Connected switches:", switches)

    threshold = 10_000_000  # 10 Mbps

    for switch in switches:
        stats = requests.get(BASE_URL + "/stats/" + switch).json()
        print(f"\nStatistics for {switch}:")

        for port in stats["ports"]:
            rate = port["tx_rate_bps"]
            print(f"Port {port['port_no']}: {rate / 1_000_000:.1f} Mbps")

            if rate > threshold:
                flow = {
                    "switch": switch,
                    "priority": 300,
                    "source_ip": "10.0.0.1",
                    "destination_ip": "10.0.0.2",
                    "protocol": "ICMP",
                    "action": "DROP"
                }

                result = requests.post(
                    BASE_URL + "/flows", json=flow
                )
                print("POST response:", result.json())


# =====================================================
# SCENARIO 2: PACKET-IN AND MAC LEARNING
# =====================================================

def scenario2():
    heading("SCENARIO 2: MAC Learning and Broadcast Handling")

    packets = [
        {"in_port": 1, "src_mac": "AA:AA", "dst_mac": "BB:BB",
         "eth_type": "IPv4"},
        {"in_port": 2, "src_mac": "BB:BB", "dst_mac": "AA:AA",
         "eth_type": "IPv4"},
        {"in_port": 1, "src_mac": "AA:AA", "dst_mac": "FF:FF:FF:FF:FF:FF",
         "eth_type": "ARP"}
    ]

    for pkt in packets:
        print("\nPacketIn event:", pkt)
        src = pkt["src_mac"]
        dst = pkt["dst_mac"]

        mac_table[src] = pkt["in_port"]
        print("Learned MAC table:", mac_table)

        if dst == "FF:FF:FF:FF:FF:FF" or dst not in mac_table:
            print("Destination unknown/broadcast -> FLOOD")
        else:
            out_port = mac_table[dst]
            print(f"Destination known -> FORWARD to port {out_port}")
            print("FlowMod: install reactive forwarding rule")


# =====================================================
# SCENARIO 3: TRAFFIC SLICING AND QUEUES
# =====================================================

def scenario3():
    heading("SCENARIO 3: QoS Queues and Network Slicing")

    queues[1] = {
        "slice": "Streaming",
        "vlan": 100,
        "min_rate_mbps": 60,
        "max_rate_mbps": 80
    }

    queues[2] = {
        "slice": "Control",
        "vlan": 200,
        "min_rate_mbps": 5,
        "max_rate_mbps": 20
    }

    print("Configured queues:")
    print(json.dumps(queues, indent=2))

    test_packets = [
        {"vlan": 100, "traffic": "Video streaming"},
        {"vlan": 200, "traffic": "Control signaling"}
    ]

    for pkt in test_packets:
        queue_id = 1 if pkt["vlan"] == 100 else 2
        print(
            f"{pkt['traffic']} | VLAN {pkt['vlan']} "
            f"-> Queue {queue_id}"
        )
        print("Simulated OpenFlow action: set_queue:", queue_id)


# =====================================================
# SCENARIO 4: ONOS-STYLE INTENT AND FAILOVER
# =====================================================

def scenario4():
    heading("SCENARIO 4: Intent Framework and Link Failover")

    intent = {
        "type": "PointToPointIntent",
        "source_mac": "00:00:00:00:00:01",
        "destination_mac": "00:00:00:00:00:02",
        "bandwidth_mbps": 50,
        "path": ["s1", "s2", "s3"]
    }

    response = requests.post(BASE_URL + "/intents", json=intent)
    response.raise_for_status()
    created = response.json()

    print("Created intent:", json.dumps(created, indent=2))
    print("GET intent status:",
          requests.get(BASE_URL + "/intents").json())

    print("\nSimulating link failure: s1-s2 DOWN")
    created["path"] = ["s1", "s4", "s3"]
    created["state"] = "INSTALLED"
    created["event"] = "Alternative path selected (simulated)"

    print("Updated intent:", json.dumps(created, indent=2))
    print("Intent state: INSTALLED")


# =====================================================
# MAIN PROGRAM
# =====================================================

if __name__ == "__main__":
    try:
        scenario1()
        scenario2()
        scenario3()
        scenario4()

        heading("ASSIGNMENT DEMO COMPLETED")
        print("All four scenarios executed successfully.")
        print("Note: Controller operations were simulated locally.")

    except requests.RequestException as exc:
        print("REST API error:", exc)
