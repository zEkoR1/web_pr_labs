import socket
import threading
import time
import random
import json

# Possible states of a node
FOLLOWER = "FOLLOWER"
CANDIDATE = "CANDIDATE"
LEADER = "LEADER"

# Message types
REQUEST_VOTE = "REQUEST_VOTE"
VOTE_RESPONSE = "VOTE_RESPONSE"
HEARTBEAT = "HEARTBEAT"


class RaftNode(threading.Thread):
    def __init__(self, node_id, peers, base_port=5000):
        super(RaftNode, self).__init__()
        self.node_id = node_id
        self.peers = peers  # list of node_ids representing other nodes
        self.base_port = base_port

        # Raft persistent and volatile state (simplified)
        self.current_term = 0
        self.voted_for = None
        self.state = FOLLOWER

        # For leader election timing
        self.election_timeout = self.reset_election_timeout()
        self.last_heartbeat_time = time.time()

        # Networking (UDP)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("localhost", self.base_port + self.node_id))
        self.sock.setblocking(False)

        # For voting and counting majority
        self.votes_received = 0
        self.majority = (len(self.peers) + 1) // 2 + 1  # majority threshold

        self.running = True

    def reset_election_timeout(self):
        # Randomized election timeout: between 1.5 and 3 seconds
        return time.time() + random.uniform(1.5, 3.0)

    def send_message(self, target_id, message):
        addr = ("localhost", self.base_port + target_id)
        data = json.dumps(message).encode('utf-8')
        self.sock.sendto(data, addr)

    def broadcast_message(self, message):
        for p in self.peers:
            self.send_message(p, message)

    def request_votes(self):
        # Send RequestVote to all peers
        msg = {
            "type": REQUEST_VOTE,
            "term": self.current_term,
            "candidate_id": self.node_id
        }
        print(f"Node {self.node_id}: Requesting votes for term {self.current_term}")
        self.broadcast_message(msg)

    def send_heartbeat(self):
        # Leader sends heartbeat
        msg = {
            "type": HEARTBEAT,
            "term": self.current_term,
            "leader_id": self.node_id
        }
        self.broadcast_message(msg)

    def handle_request_vote(self, msg, addr):
        term = msg["term"]
        candidate_id = msg["candidate_id"]
        if term > self.current_term:
            # Higher term found; revert to follower
            self.current_term = term
            self.state = FOLLOWER
            self.voted_for = None

        vote_granted = False
        if term == self.current_term and (self.voted_for is None or self.voted_for == candidate_id):
            # Grant vote
            vote_granted = True
            self.voted_for = candidate_id
            print(f"Node {self.node_id}: Voted for Node {candidate_id} in term {term}")

        # Send vote response
        response = {
            "type": VOTE_RESPONSE,
            "term": self.current_term,
            "vote_granted": vote_granted
        }
        self.sock.sendto(json.dumps(response).encode('utf-8'), addr)

    def handle_vote_response(self, msg):
        if self.state == CANDIDATE and msg["term"] == self.current_term and msg["vote_granted"]:
            self.votes_received += 1
            print(f"Node {self.node_id}: Received vote. Total votes = {self.votes_received}")
            if self.votes_received >= self.majority:
                # Become the leader
                print(f"Node {self.node_id}: I received majority votes, becoming LEADER for term {self.current_term}")
                self.state = LEADER
                # As a leader, immediately send heartbeat to establish authority
                self.send_heartbeat()
                self.last_heartbeat_time = time.time()

    def handle_heartbeat(self, msg):
        leader_term = msg["term"]
        if leader_term > self.current_term:
            self.current_term = leader_term
            self.state = FOLLOWER
            self.voted_for = None

        if leader_term >= self.current_term:
            # Reset election timeout and acknowledge leader
            self.last_heartbeat_time = time.time()
            self.election_timeout = self.reset_election_timeout()

    def run(self):
        print(f"Node {self.node_id} started as {self.state} on port {self.base_port + self.node_id}")
        while self.running:
            # Check for messages
            self.receive_messages()

            # Leader behavior: send periodic heartbeats
            if self.state == LEADER:
                if time.time() - self.last_heartbeat_time > 0.5:
                    self.send_heartbeat()
                    self.last_heartbeat_time = time.time()

            # Follower and Candidate behavior: check election timeouts
            if self.state in [FOLLOWER, CANDIDATE]:
                if time.time() > self.election_timeout:
                    self.start_election()

            time.sleep(0.05)

    def start_election(self):
        self.state = CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id
        self.votes_received = 1  # voted for self
        print(f"Node {self.node_id}: Starting election for term {self.current_term}")
        self.request_votes()
        self.election_timeout = self.reset_election_timeout()

    def receive_messages(self):
        while True:
            try:
                data, addr = self.sock.recvfrom(4096)
            except BlockingIOError:
                break
            msg = json.loads(data.decode('utf-8'))
            msg_type = msg.get("type")

            if msg_type == REQUEST_VOTE:
                self.handle_request_vote(msg, addr)

            elif msg_type == VOTE_RESPONSE:
                self.handle_vote_response(msg)

            elif msg_type == HEARTBEAT:
                self.handle_heartbeat(msg)

    def stop(self):
        self.running = False
        self.sock.close()
