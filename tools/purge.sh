#!/bin/bash
consul_pod_id=$(kubectl get pods -n turbonomic| grep "consul" | awk  '{print $1}')
#kubectl scale --replicas=0 deployment t8c-operator -n turbonomic
declare -a arr=("topology-processor" "group" "cost" "market")

## now loop through the above array
for i in "${arr[@]}"
do
    kubectl scale --replicas=0 deployment $i -n turbonomic
    db_name=$(mysql -u root --password=vmturbo -e "show databases;" | grep "${i/-/_}")
    echo "$db_name"
    if [[ !$(mysql -u root --password=vmturbo -e "show databases;" | grep "$i") ]]
    then
        mysql -u root --password=vmturbo  -e "drop database ${db_name};"
    else
        tp_db=$(grep "dbSchemaName.*"$i"" /opt/turbonomic/$namespace/charts_v1alpha1_xl_cr.yaml | cut -d ':' -f2 | xargs)
        mysql -u root --password=vmturbo -e  "drop database ${tp_db};"
    fi
    kubectl exec -i -n turbonomic "$consul_pod_id" -- consul kv delete --recurse $i-
    kubectl scale --replicas=1 deployment $i -n turbonomic
    kubectl wait deployment $i --for condition=Available=True --timeout=90s
done
kubectl scale --replicas=1 deployment t8c-operator -n turbonomic
kubectl wait deployment t8c-operator --for condition=Available=True --timeout=120s -n turbonomic
kubectl wait deployment --all --for condition=Available=True --timeout=120s -n turbonomic