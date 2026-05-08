#!/bin/bash
sudo ip netns exec xrd01 tc qdisc add dev Gi0-0-0-1 root netem delay 10000
sudo ip netns exec xrd01 tc qdisc add dev Gi0-0-0-2 root netem delay 5000
sudo ip netns exec xrd02 tc qdisc add dev Gi0-0-0-1 root netem delay 30000
sudo ip netns exec xrd02 tc qdisc add dev Gi0-0-0-2 root netem delay 20000
sudo ip netns exec xrd03 tc qdisc add dev Gi0-0-0-1 root netem delay 40000
sudo ip netns exec xrd04 tc qdisc add dev Gi0-0-0-1 root netem delay 30000
sudo ip netns exec xrd04 tc qdisc add dev Gi0-0-0-2 root netem delay 30000
sudo ip netns exec xrd05 tc qdisc add dev Gi0-0-0-2 root netem delay 5000
sudo ip netns exec xrd06 tc qdisc add dev Gi0-0-0-0 root netem delay 30000
echo "Latencies added. The following output applies in both directions, Ex: xrd01 -> xrd02 and xrd02 -> xrd01"
for n in xrd01 xrd02 xrd03 xrd04 xrd05 xrd06; do
    echo "$n link latency: "
    sudo ip netns exec $n tc qdisc list | grep delay
done

