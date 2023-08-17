#! /bin/bash
topology_ip=$(kubectl get svc -n turbonomic| grep "topology" | awk  '{print $3}')
group_ip=$(kubectl get svc -n turbonomic| grep "group" | awk  '{print $3}')
cost_ip=$(kubectl get svc -n turbonomic| grep "cost" | awk  '{print $3}')
curl http://${topology_ip}:8080/internal-state > topology.zip
curl http://${group_ip}:8080/internal-state > group.zip
curl http://${topology_ip}:8080/internal-state > cost.zip