
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

# ==========================================================
# SDN ASSIGNMENT: ALL FOUR SCENARIOS IN ONE PYTHON FILE
# Local mock controller for demonstration in VS Code.
# ==========================================================

SWITCHES = {
    "s1": [
        {"port": 1, "tx_rate_bps": 5_000_000},
        {"port": 2, "tx_rate_bps": 15_000_000}
    ],
    "s2": [
        {"port": 1, "tx_rate_bps": 3_000_000}
    ]
}

flows = []
intents = []
mac_table = {}


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
            switch = self.path.split("/")[-1]
            self.send_json({"ports": SWITCHES.get(switch, [])})

        elif self.path == "/intents":
            self.send_json({"intents": intents})

        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")

        if self.path == "/flows":
            flows.append(payload)
            self.send_json({
                "status": "Flow submitted (simulated)",
                "flow": payload
            }, 201)

        elif self.path == "/intents":
            payload["id"] = len(intents) + 1
            payload["state"] = "INSTALLED"
            intents.append(payload)
            self.send_json(payload, 201)

        else:
            self.send_json({"error": "Not found"}, 404)

    def log_message(self, *args):
        pass


def start_controller():
    HTTPServer(("127.0.0.1", 8765), ControllerHandler).serve_forever()


threading.Thread(target=start_controller, daemon=True).start()
time.sleep(0.3)

BASE = "http://127.0.0.1:8765"


def heading(title):
    print("\n" + "=" * 65)
    print(title)
    print("=" * 65)


# ==========================================================
# SCENARIO 1: REST API, PORT STATISTICS, ICMP BLOCK
# ==========================================================

def scenario1():
    heading("SCENARIO 1: AUTOMATED NETWORK POLICY ENGINE")

    response = requests.get(BASE + "/switches", timeout=5)
    response.raise_for_status()
    switches = response.json()["switches"]

    print("Connected switches:", switches)
    threshold = 10_000_000  # 10 Mbps

    for switch in switches:
        response = requests.get(
            f"{BASE}/stats/{switch}", timeout=5
        )
        response.raise_for_status()

        for port in response.json()["ports"]:
            rate = port["tx_rate_bps"]
            print(
                f"{switch}, port {port['port']}: "
                f"{rate / 1_000_000:.1f} Mbps"
            )

            if rate > threshold:
                rule = {
                    "switch": switch,
                    "priority": 300,
                    "match": {
                        "eth_type": "IPv4",
                        "ip_protocol": 1,
                        "ipv4_src": "10.0.0.1",
                        "ipv4_dst": "10.0.0.2"
                    },
                    "action": "DROP"
                }

                result = requests.post(
                    BASE + "/flows", json=rule, timeout=5
                )
                result.raise_for_status()
                print("Threshold exceeded. ICMP drop rule submitted.")
                print("POST status:", result.status_code)


# ==========================================================
# SCENARIO 2: PACKET-IN AND MAC LEARNING
# ==========================================================

def scenario2():
    heading("SCENARIO 2: MAC LEARNING AND BROADCAST HANDLING")

    packets = [
        {"port": 1, "src": "AA:AA", "dst": "BB:BB",
         "eth_type": "IPv4"},
        {"port": 2, "src": "BB:BB", "dst": "AA:AA",
         "eth_type": "IPv4"},
        {"port": 1, "src": "CC:CC",
         "dst": "FF:FF:FF:FF:FF:FF", "eth_type": "ARP"}
    ]

    for pkt in packets:
        src, dst, port = pkt["src"], pkt["dst"], pkt["port"]

        print("\nPacketIn:", pkt)
        mac_table[src] = port
        print("Learned MAC table:", mac_table)

        if dst == "FF:FF:FF:FF:FF:FF":
            print("Broadcast packet -> FLOOD")
            print("Loop prevention must be handled separately.")
        elif dst not in mac_table:
            print("Unknown destination -> FLOOD")
        else:
            print("Known destination -> FORWARD to port", mac_table[dst])
            print("FlowMod -> install reactive forwarding rule")


# ==========================================================
# SCENARIO 3: OVS QOS, QUEUES AND TRAFFIC SLICING
# ==========================================================

def scenario3():
    heading("SCENARIO 3: NETWORK SLICING USING OVS")

    print("Slice A: Streaming | VLAN 100 | Queue 1")
    print("Minimum: 60 Mbps | Maximum: 80 Mbps")

    print("Slice B: Control   | VLAN 200 | Queue 2")
    print("Minimum: 5 Mbps  | Maximum: 20 Mbps")

    print("\n--- Run these commands in Linux with OVS installed ---")

    commands = [
        """sudo ovs-vsctl set Port s1-eth2 qos=@qos \\
-- --id=@qos create QoS type=linux-htb \\
other-config:max-rate=100000000 \\
queues:1=@stream queues:2=@control \\
-- --id=@stream create Queue \\
other-config:min-rate=60000000 \\
other-config:max-rate=80000000 \\
-- --id=@control create Queue \\
other-config:min-rate=5000000 \\
other-config:max-rate=20000000""",

        """sudo ovs-ofctl -O OpenFlow13 add-flow s1 \\
"priority=200,dl_vlan=100,actions=set_queue:1,output:2" """,

        """sudo ovs-ofctl -O OpenFlow13 add-flow s1 \\
"priority=200,dl_vlan=200,actions=set_queue:2,output:2" """
    ]

    for command in commands:
        print("\n" + command)

    print("\nQueue mapping displayed. Commands not executed.")


# ==========================================================
# SCENARIO 4: ONOS-STYLE INTENT AND FAILOVER SIMULATION
# ==========================================================

def scenario4():
    heading("SCENARIO 4: INTENT FRAMEWORK AND LINK FAILOVER")

    intent = {
        "type": "PointToPointIntent",
        "source_mac": "00:00:00:00:00:01",
        "destination_mac": "00:00:00:00:00:02",
        "bandwidth_mbps": 50,
        "path": ["s1", "s2", "s3"]
    }

    response = requests.post(
        BASE + "/intents", json=intent, timeout=5
    )
    response.raise_for_status()
    created = response.json()

    print("Created intent:")
    print(json.dumps(created, indent=2))

    response = requests.get(BASE + "/intents", timeout=5)
    response.raise_for_status()
    print("\nRetrieved intent state:", response.json()["intents"][0]["state"])

    print("\nSimulating link failure: s1-s2 DOWN")

    # Demonstrate the intended result; this does not change a real network.
    created["path"] = ["s1", "s4", "s3"]
    created["state"] = "INSTALLED"

    print("Alternative path:", " -> ".join(created["path"]))
    print("Intent state after simulated failover:", created["state"])


# ==========================================================
# MAIN
# ==========================================================

if __name__ == "__main__":
    try:
        scenario1()
        scenario2()
        scenario3()
        scenario4()

        heading("ALL FOUR SCENARIOS COMPLETED")
        print("Local demonstration finished successfully.")
        print("Scenarios 1, 2 and 4 use simulated controller behavior.")
        print("Scenario 3 displays commands for a real OVS environment.")

    except requests.RequestException as error:
        print("REST API error:", error)
