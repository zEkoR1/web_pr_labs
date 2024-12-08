from RaftNode import RaftNode
import time

def main():
    num_nodes = 5
    nodes = []
    peers = list(range(num_nodes))

    for i in range(num_nodes):
        node_peers = [p for p in peers if p != i]
        node = RaftNode(i, node_peers, base_port=5000)
        node.start()
        nodes.append(node)


    time.sleep(10)

    for node in nodes:
        node.stop()
        node.join()

if __name__ == "__main__":
    main()
