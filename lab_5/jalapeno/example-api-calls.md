## Example API Calls

Basic shortest path calculation:
```
curl "http://198.18.128.101:30800/api/v1/graphs/ipv6_graph/shortest_path?source=hosts/xrd02&destination=hosts/xrd07" | jq .
```

Shortest path calculation - lowest latency:
```
curl "http://198.18.128.101:30800/api/v1/graphs/ipv6_graph/shortest_path/latency?source=hosts/xrd02&destination=hosts/xrd07" | jq .
```

Shortest path calculation - lowest utilization:
```
curl "http://198.18.128.101:30800/api/v1/graphs/ipv6_graph/shortest_path/utilization?source=hosts/xrd02&destination=hosts/xrd07" | jq .
```

Shortest path calculation - lowest load:
```
curl "http://198.18.128.101:30800/api/v1/graphs/ipv6_graph/shortest_path/load?source=hosts/xrd02&destination=hosts/xrd07" | jq .
```

Shortest path calculation - next best path:
```
curl "http://198.18.128.101:30800/api/v1/graphs/ipv6_graph/shortest_path/next-best-path?source=hosts/xrd02&destination=hosts/xrd07&direction=outbound" | jq .
```

### Fabric Graph
curl "http://198.18.128.101:30800/api/v1/graphs/fabric_graph/shortest_path/load?source=hosts/srv6-pytorch-0&destination=hosts/srv6-pytorch-1" | jq .