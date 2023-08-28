import requests
import json
import os
import math
import subprocess
import csv
import yaml
import threading, queue
import urllib3
import scp 
import sys
from os import walk
import re
import time
import kubernetes
from kubernetes import client, config
import zipfile
import glob
    

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
DEFAULT_USER = "administrator"
DEFAULT_PW = "n/a"
DEFAULT_URL = "n/a"
DEFAULT_GROUP = "n/a"
def handle_request(type, url, cookie, data=None):
    session = requests.Session()
    retry = Retry(connect=3, backoff_factor=0.5)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    response = None
    if type == "GET":
        response = session.get(url, headers= {'Content-type': 'application/json', 'cookie': cookie}, verify=False)
    elif type == "POST":
        response = session.post(url,  verify=False, headers= {'Content-type': 'application/json', 'cookie': cookie}, data=data)
    elif type == "PUT":
        response = session.put(url,verify=False, headers= {'Content-type': 'application/json', 'cookie': cookie}, data=data)
    elif type == "DELETE":
        response = session.delete(url, headers= {'Content-type': 'application/json', 'cookie': cookie}, verify=False)
    if response.status_code != 200:#
        print("Issue with request to "+url+ "Status Code: "+str(response.status_code))
    try:
        answer = None
        if len(response.text) > 0:
            answer = response.json()
            #print(str(answer))
        return answer, response.headers
    except Exception:
        print("could not extract JSON... text: "+response.text)
    
def watch_deployment(client, deployment, namespace="turbo"):
    w = kubernetes.watch.Watch()
    api_client = kubernetes.client.AppsV1Api()
    count = 0
    while True:
        resp = api_client.read_namespaced_deployment(name=deployment, namespace=namespace)
        if resp.status.replicas == resp.status.ready_replicas:
            print("Done Waiting")
            return
        time.sleep(1) 
        count += 1
        if count > 200:
            print("timeout")
            return
def copy_file_to_pod(source_file, destination_file, pod_name, namespace="turbo"):
    # create an instance of the API class
    '''api_instance = kubernetes.client.CoreV1Api()
    api_instance.api_client.configuration.verify_ssl = False 
    exec_command = ['tar', 'xvf', '-', '-C', '/']
    resp = kubernetes.stream.stream(api_instance.connect_get_namespaced_pod_exec, pod_name, namespace,
                    command=exec_command,
                    stderr=True, stdin=True,
                    stdout=True, tty=False,
                    _preload_content=False)

    # Encode file

    with TemporaryFile() as tar_buffer:
        with tarfile.open(fileobj=tar_buffer, mode='w') as tar:
            tar.add(source_file)

        tar_buffer.seek(0)
        commands = []
        commands.append(tar_buffer.read())
        print("Trying to print "+str(len(commands))+" Entries")
        try:
            while resp.is_open():
                resp.update(timeout=1)
                if resp.peek_stdout():
                    print("STDOUT: %s" % resp.read_stdout())
                if resp.peek_stderr():
                    print("STDERR: %s" % resp.read_stderr())
                if commands:
                    c = commands.pop(0)
                 #   print(str(c))

                    resp.write_stdin(c)
                else:
                    break
        except Exception:
            print("Exception with : "+str(len(commands))+" Entries left in Queue")
        finally:
             resp.close()'''
    #Have to hack it this way for now..
    
    cmd = ["kubectl","-n",namespace, "cp", source_file, pod_name+":/"+destination_file]
    p = subprocess.run(cmd)
def scale_replicas( v1Client, deployment, count, namespace="turbo"):
    api_client = kubernetes.client.AppsV1Api()
    api_response = api_client.patch_namespaced_deployment_scale( deployment, namespace, {'spec': {'replicas': int(count)}})
    watch_deployment(v1Client, deployment)

def make_k8s_client(kubeconfig: dict) -> kubernetes.client.CoreV1Api:
    api_client = kubernetes.config.new_client_from_config_dict(kubeconfig)
    return kubernetes.client.CoreV1Api(api_client)

def exec_in_pod(client, podname, cmd, namespace="turbo"):
    print("Trying to run in pod: "+podname+": "+str(cmd))
    resp = kubernetes.stream.stream(client.connect_get_namespaced_pod_exec,
                  podname,
                  namespace,
                  command=cmd,
                  stderr=True, stdin=False,
                  stdout=True, tty=False)
    print("Response: " + resp)

import os
def get_biggest(input):
    file_list = glob.glob(input)
    winner = ""
    previous = 0
    for entry in file_list:
        stats = os.stat(entry)
        if stats.st_size > previous:
            winner = entry
            previous = stats.st_size
    return winner
def get_names(folder):
    ret = {"topologyfile": get_biggest(folder+"/topology*"),
           "groupfile": get_biggest(folder+"/group*"),
            "rsyslog": get_biggest(folder+'/rsyslog*.zip') }
    return ret
def purge_topology_cluster(api_client, namespace="turbo"):
    ret = api_client.list_namespaced_pod(namespace)
    to_purge = ["topology-processor", "group", "cost", "market"]
    consul_name = ""
    mysql_name = ""
    for i in ret.items:
        if "consul" in i.metadata.name:
            consul_name = i.metadata.name
        if "db-" in i.metadata.name:
            mysql_name = i.metadata.name
    scale_replicas(api_client, "t8c-operator", 0, namespace)
    for entry in to_purge:
        scale_replicas(api_client, entry, 0, namespace)
        # then get the name of the db (which is the same as the pod but - => _). Drop that.
        cmd = ["mysql", "-S","/var/run/mysqld/mysqld.sock", "-u","root" ,"--password=vmturbo", '-e', 'drop database '+entry.replace("-","_")+';']
        exec_in_pod(api_client, mysql_name, cmd, namespace)
        # Then clear in Consul:
        exec_in_pod(api_client, consul_name, ["/bin/consul","kv", "delete", "--recurse",entry], namespace)
        scale_replicas(api_client, entry, 1, namespace)

    scale_replicas(api_client, "t8c-operator", 1, namespace)
def prepare_helper_pod(api_client, filenames, namespace="turbo"):  
    open_pod(api_client,pod_name="helper", namespace=namespace)  
    exec_in_pod(api_client, "helper", ["apk", "add", "tar"], namespace)
    print(str(filenames))
    copy_file_to_pod(filenames["groupfile"],"group.zip", "helper", namespace)
    print("Copied groups")
    time.sleep(5)
    copy_file_to_pod(filenames["topologyfile"], "topology.zip","helper", namespace)
    print("Copied topology")

    exec_in_pod(api_client, "helper", ["apk", "add", "curl"], namespace)
    # Now execute those curl statements:
def open_pod(      api_client, pod_name: str, 
                   cmd: list=["sleep","60m"],
                   namespace: str='turbo', 
                   image: str='alpine', 
                   restartPolicy: str='Never'):
    '''
    This method launches a pod in kubernetes cluster according to command
    '''
    
    api_response = None
    try:
        api_response = api_client.read_namespaced_pod(name=pod_name,
                                                        namespace=namespace)
    except kubernetes.client.rest.ApiException as e:
        if e.status != 404:
            print("Unknown error: %s" % e)
            exit(1)

    if not api_response or api_response.status.phase != 'Running':
        print(f'From {os.path.basename(__file__)}: Pod {pod_name} does not exist. Creating it...')
        # Create pod manifest
        pod_manifest = {
            'apiVersion': 'v1',
            'kind': 'Pod',
            'metadata': {
                'name': pod_name
            },
            'spec': {
                'containers': [{
                    'image': image,
                    'pod-running-timeout': '5m0s',
                    'name': f'container',
                    'args': cmd,
                }],
                # 'imagePullSecrets': client.V1LocalObjectReference(name='regcred'), # together with a service-account, allows to access private repository docker image
                'restartPolicy': restartPolicy
            }
        }
        

        api_response = api_client.create_namespaced_pod(body=pod_manifest,                                                          namespace=namespace)

        while True:
            api_response = api_client.read_namespaced_pod(name=pod_name,
                                                            namespace=namespace)
            if api_response.status.phase != 'Pending':
                break
            time.sleep(0.01)
        
        print(f'From {os.path.basename(__file__)}: Pod {pod_name} in {namespace} created.')
        return pod_name
def get_service_ip(api_client, service_name, namespace="turbo"):
    ret = api_client.list_namespaced_service(namespace)
    for entry in ret.items:
        if service_name in entry.metadata.name:
            return  entry.spec.cluster_ip
        
def prepare_upload(api_client, service_name, namespace):
    service_ip = get_service_ip(api_client, service_name, namespace)
    cmd = ["curl", "--header",'Content-Type: application/zip', "--data-binary","@/"+service_name+".zip", "http://"+service_ip+":8080/internal-state" ]
    return cmd
def load_topology_cluster(kubeconfig, topologyname, prog, namespace="turbo"):
    api_client = None
    config_dict = yaml.safe_load(kubeconfig)
    api_client = make_k8s_client(config_dict)
    prog.progress(value = 20,text ="Loaded Kubeconfig")
    # First Purge old Topology: 
    # Secondly load Group
    # Thirdly load Cost
    #purge_topology_cluster(api_client)
    prepare_helper_pod(api_client,topologyname, namespace)  
    prog.progress(value = 30,text ="Launched Helper Pod")
    group_cmd = prepare_upload(api_client, "group", namespace)
    prog.progress(value = 40,text ="Uploaded Group Data")
    topology_cmd = prepare_upload(api_client, "topology", namespace)
    prog.progress(value = 50,text ="Uploaded Topology Data")
    exec_in_pod(api_client, "helper", group_cmd, namespace) 
    prog.progress(value = 60,text ="Passed Group Data")
    exec_in_pod(api_client, "helper", topology_cmd, namespace)
    prog.progress(value = 70,text ="Passed Topology Data")
    system_ip = get_service_ip(api_client, "topology-processor", namespace)
    broadcast = ["curl" ,"-X" ,"POST" ,"--header","Content-Type: application/json","--header","Accept: application/json" ,"http://"+system_ip+":8080/topology/send"]
    exec_in_pod(api_client, "helper", broadcast, namespace)
    prog.progress(value = 90,text ="Broadcasted")
    api_response = api_client.delete_namespaced_pod("helper", namespace)
    prog.progress(value = 100,text ="All Done")
        
def load_topology(ssh):
    
    stdin,stdout, stderr = ssh.exec_command("curl --header 'Content-Type: application/zip' --data-binary @/tmp/group.zip http://$(kubectl get services -n turbonomic | grep \"^group\" | grep 8080 | awk '{print $3}'):8080/internal-state")
    
    if stdout.channel.recv_exit_status() != 0:    
        print ("Encountered Errors: "+stderr.read().decode('ascii'))
        return False 
    print(stdout.read().decode('ascii'))
    print("Done Loading Group")
    stdin,stdout, stderr = ssh.exec_command("curl --header 'Content-Type: application/zip' --data-binary @/tmp/topology.zip http://$(kubectl get services -n turbonomic | grep \"^topology-processor\" | grep 8080 | awk '{print $3}'):8080/internal-state")
    if stdout.channel.recv_exit_status() != 0:    
        print ("Encountered Errors: "+stderr.read().decode('ascii'))
        return False
    print(stdout.read().decode('ascii'))
    print("Done Loading Topology")  
    stdin,stdout, stderr = ssh.exec_command("curl -X POST --header 'Content-Type: application/json' --header 'Accept: application/json' http://$(kubectl get services -n turbonomic | egrep '^topology-processor' | grep 8080 | awk '{print $3}'):8080/topology/send")
    if stdout.channel.recv_exit_status() != 0:    
        print ("Encountered Errors: "+stderr.read().decode('ascii'))
        return False
    print(stdout.read().decode('ascii'))
    print("Done Broadcasting")
    return True
def purge_topology(ssh):
    scpClient = scp.SCPClient(ssh.get_transport(), progress=progress)
    scpClient.put("./tools/purge.sh", remote_path='/tmp/purge.sh')
    print("")
    stdin, stdout, stderr = ssh.exec_command('/tmp/purge.sh')
    if stdout.channel.recv_exit_status() != 0:
        print ("Encountered Errors: "+stderr.read().decode('ascii'))
        return False
    print (stdout.channel.recv_exit_status())
    ssh.exec_command('rm -f /tmp/purge.sh')
    if stdout.channel.recv_exit_status() != 0:
        print ("Encountered Errors: "+stderr.read().decode('ascii'))
        return False
    else: 
        return True

def progress(filename, size, sent):
    sys.stdout.write("%s's progress: %.2f%%   \r" % (filename, float(sent)/float(size)*100) )

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
THREAD_COUNT = 50
previous = int(0)
def get_folders_in_folder(path):
    res = [f.name for f in os.scandir(path) if f.is_dir()]
    return res
def delete_file_in_folder(folder, name):
    os.remove(folder+"/"+name)
def get_files_in_folder(folder):
    res = []
    filenames = next(walk(folder), (None, None, []))[2]  # [] if no file
    for entry in filenames:
        if  ".json" in entry:
            print("Appending: "+entry)
            res.append(entry.replace(".json", ""))
    return res
def write_to_json_file(filename, data):
    with open(filename+".json", "w") as f:
        data_string = str(json.dumps(data))
        data_string.replace(",", ",\n")
        data_string.replace("}", ",}\n")
        data_string.replace("{", ",{\n")
        f.write(str(data_string))
            
def write_to_file(filename, data):
    with open(filename+".txt", "w") as f:
        for entry in data:
            f.write(str(entry)+'\n')
def create_entity_group(case_data, entity, group_name):
    data = {
        "criteriaList": [], "groupType": entity["entityType"], "isStatic": False, "displayName": group_name, "logicalOperator": entity["logicalOperator"]
    }
    for entry in entity["criteriaList"]:
        data["criteriaList"].append({
            "expVal": entry["value"],
            "expType": entry["type"],
            "filterType": str(entry["criterion"]),
            "caseSensitive": False,
        })
    answer, headers = handle_request("POST",case_data["url"]+"api/v3/groups",case_data["cookie"],json.dumps(data))
    return answer["uuid"],answer["membersCount"]

def get_group_uuid(case_data, name):
    data = {
        "criteriaList": [], "className": "Group", "logicalOperator": "AND"
    }
    data["criteriaList"].append({
        "expVal": name,
        "expType": "RXEQ",
        "filterType": "groupsByName",
        "caseSensitive": False,
    })
    answer, headers = handle_request("POST",case_data["url"]+"api/v3/search", case_data["cookie"],data=json.dumps(data))
    ret = []
    if len(answer) == 1:
        return answer[0]["uuid"]
    return -1
def search_by_filter(case_data, entity):
    
    data = {
        "criteriaList": [], "className": entity["entityType"], "logicalOperator": entity["logicalOperator"]
    }
    for entry in entity["criteriaList"]:
        data["criteriaList"].append({
            "expVal": entry["value"],
            "expType": entry["type"],
            "filterType": str(entry["criterion"]),
            "caseSensitive": False,
        })
    answer, headers = handle_request("POST",case_data["url"]+"api/v3/search", case_data["cookie"],data=json.dumps(data))
    ret = []
    for entry in answer:
        ret.append({"Name": entry["displayName"], "UUID": entry["uuid"]})
    while headers.get("X-next-cursor"):
        cursor = headers["X-next-cursor"]
        answer, headers = handle_request("POST", case_data["url"]+"api/v3/search?cursor="+cursor, case_data["cookie"], data=json.dumps(data))
        for entry in answer:
            ret.append({"Name": entry["displayName"], "UUID": entry["uuid"]})

    return ret
def get_entity(cookie, url, entry):
    answer, headers= handle_request("GET",url+"api/v3/entities/"+entry,cookie)
    return answer["displayName"]  

def get_entity_list_by_type(cookie, url, scope):
    answer, headers= handle_request("GET",url+"api/v3/groups/"+str(scope), cookie)
    names = []
    for entry in answer["memberUuidList"]:
       names.append(get_entity(cookie, url, entry))
       print("Retrieved "+names[-1])
    return names

def get_policy_list(case_data):
    answer, headers = handle_request("GET",case_data["url"]+"api/v3/settingspolicies", case_data["cookie"])
    return answer

def set_policy(case_data, uuid, content):
    answer, headers = handle_request("PUT",case_data["url"]+"api/v3/settingspolicies/"+uuid, case_data["cookie"],  data=json.dumps(content))

def apply_restrictions_k8s(entity_list, exclude_scopes, case_data):

    for entry in exclude_scopes:
        # first get VMs in list: 
        global previous 
        scope_data = case_data
        scope_data["scope"] = entry["scope"]
        previous = 0
        entities = get_k8s_list(scope_data, False)
        
        entry["Count"] = len(entities)
        #print("Obtained list of "+str(len(entities))+" VMs for scope "+entry["Scope"]+" Group: "+entry["GroupName"])
        count = 0
        for entity in entities: 
            for source_entity in entity_list: 
                if source_entity["UUID"] == entity:
                    count = count + 1
                    source_entity["Application"] = entry["Application"]

                    source_entity["VMEM"]["Request"]["Target"] = entry["VMemRequest"] if entry["VMemRequest"] > 0 else source_entity["VMEM"]["Request"]["Target"]
                    source_entity["VMEM"]["Limit"]["Target"] = entry["VMemLimit"] if entry["VMemLimit"] >0 else source_entity["VMEM"]["Limi"]["Target"]
                    source_entity["VCPU"]["Request"]["Target"] = entry["VMemRequest"] if entry["VMemRequest"] >0 else source_entity["VCPU"]["Request"]["Target"]
                    source_entity["VCPU"]["Limit"]["Target"] = entry["VMemLimit"] if entry["VMemLimit"] >0 else source_entity["VCPU"]["Limit"]["Target"]
                    # Below: Case like citrix where we do not change anything
                    source_entity["VMEM"]["Request"]["Target"] = entry["VMemRequest"] if entry["VMemRequest"] != -1 else source_entity["VMEM"]["Request"]["Current"] 
                    source_entity["VMEM"]["Limit"]["Target"] = entry["VMemLimit"] if entry["VMemLimit"] != -1 else source_entity["VMEM"]["Limit"]["Current"]
                    source_entity["VCPU"]["Request"]["Target"] = entry["VMemRequest"] if entry["VMemRequest"] != -1 else source_entity["VCPU"]["Request"]["Current"] 
                    source_entity["VCPU"]["Limit"]["Target"] = entry["VMemLimit"] if entry["VMemLimit"] != -1 else source_entity["VCPU"]["Limit"]["Current"]              
                    break
        print("Of which "+str(count)+" were relevant to our Case")
        write_to_file(entry["GroupName"], entities)
        write_to_file("BaseGroup", entity_list)
    return exclude_scopes, entity_list

def get_entity_type(case_data):
    answer, headers = handle_request("GET",case_data["url"]+"api/v3/groups/"+str(case_data["scope"]), case_data["cookie"])
    case_data["entity_type"] = answer["groupType"]
    return case_data

def correlate_actions_k8s(entries, actions):
    for action in actions: 
        for entry in entries:  
            if entry["UUID"] == action["UUID"]:
                # Hit 
                if "VMEM" in action["Type"] :
                    if "LIMIT" in action["Type"]:
                        entry["VMEM"]["Limit"]["Target"] = action["To"]
                    else: 
                        
                        entry["VMEM"]["Request"]["Target"]= action["To"]
                elif "VCPU" in action["Type"] :
                    if "LIMIT" in action["Type"]:
                        entry["VCPU"]["Limit"]["Target"] = action["To"]
                    else:
                        entry["VCPU"]["Request"]["Target"] = action["To"]
                break
    return entries
def get_action_list_chunk_k8s(case_data, data, cursor,limit, q):
    answer, headers = handle_request("POST",case_data["url"]+"api/v3/groups/"+case_data["scope"]+"/actions?limit="+str(limit)+"&cursor="+str(cursor),case_data["cookie"], data=json.dumps(data))
    res = []
    count = 0
    total = 0
    for entry in answer:
        total += len( entry.get("compoundActions", []))
    if case_data["entity_type"] != "VirtualMachine":
        for action in answer:
            if  "compoundActions" not in action:
                print("No compound action, parsing: "+action["details"])
                if action["valueUnits"] == "mCores":
                    entry_type = "VCPU"
                    if "Request" in action["details"]:
                        entry_type += "_REQ"
                    else:
                        entry_type += "_LIMIT"
                    res_entry = {
                        "From": int(float(action["currentValue"])),
                        "To": int(float(action["newValue"])),
                        "Type":entry_type,
                        "UUID": action["target"]["uuid"]
                    }
                    res.append(res_entry)
                elif action["valueUnits"] == "KB":
                    entry_type = "VMEM"
                    if "Request" in action["details"]:
                        entry_type += "_REQ"
                    elif "Limit" in action["details"]:
                        entry_type += "_LIMIT"
                    res_entry = {
                        "From": float(action["currentValue"])/(1024*1024),
                        "To": float(action["newValue"])/(1024*1024),
                        "Type":entry_type,
                        "UUID": action["target"]["uuid"]
                    }
                    res.append(res_entry)
            else:
                for entry in action["compoundActions"]:
                    count = count + 1
                    if entry["valueUnits"] == "mCores":
                        entry_type = "VCPU"
                        if "Request" in entry["details"]:
                            entry_type += "_REQ"
                        else:
                            entry_type += "_LIMIT"
                        
                        res_entry = {
                            "From": int(float(entry["currentValue"])),
                            "To": int(float(entry["newValue"])),
                            "Type":entry_type,
                            "UUID": action["target"]["uuid"]
                        }
                        res.append(res_entry)
                    elif entry["valueUnits"] == "KB":
                        entry_type = "VMEM"
                        if "Request" in entry["details"]:
                            entry_type += "_REQ"
                        else:
                            entry_type += "_LIMIT"
                        res_entry = {
                            "From": float(entry["currentValue"])/(1024*1024),
                            "To": float(entry["newValue"])/(1024*1024),
                            "Type":entry_type,
                            "UUID": action["target"]["uuid"]
                        }
                        res.append(res_entry)
                    else:
                        print("Huh ? "+str(entry))
                    
            progress_bar(count, total)
    else:
        for entry in answer:
            count = count + 1
            if entry["valueUnits"] == "vCPU":
                res_entry = {
                    "From": int(float(entry["currentValue"])),
                    "To": int(float(entry["newValue"])),
                    "Type":"VCPU_REQ",
                    "UUID": entry["target"]["uuid"]
                }
                res.append(res_entry)
            elif entry["valueUnits"] == "KB" and "Mem" in entry["details"]:
                res_entry = {
                    "From": float(entry["currentValue"])/(1024*1024),
                    "To": float(entry["newValue"])/(1024*1024),
                    "Type":"VMEM_REQ",
                    "UUID": entry["target"]["uuid"]
                }
                res.append(res_entry)
            
            progress_bar(count, len(answer))
    
    q.put(res)

def get_action_list_chunk_k8s_related(case_data, list_fragment, q):
    res = []
    count = 0
    data =  {
		"actionTypeList": ["RESIZE"]
    }
    total = len(list_fragment)
    for entity in list_fragment:
        answer, headers = handle_request("POST",case_data["url"]+"api/v3/entities/"+entity["UUID"]+"/actions",case_data["cookie"], data=json.dumps(data))
        if answer == None:
            continue
        if case_data["entity_type"] != "VirtualMachine":
            for action in answer:
                if  "compoundActions" not in action:
                    print("No compound action, parsing: "+action["details"])
                    if action["valueUnits"] == "mCores":
                        entry_type = "VCPU"
                        if "Request" in action["details"]:
                            entry_type += "_REQ"
                        else:
                            entry_type += "_LIMIT"
                        res_entry = {
                            "From": int(float(action["currentValue"])),
                            "To": int(float(action["newValue"])),
                            "Type":entry_type,
                            "UUID": entity["UUID"]
                        }
                        res.append(res_entry)
                    elif action["valueUnits"] == "KB":
                        entry_type = "VMEM"
                        if "Request" in action["details"]:
                            entry_type += "_REQ"
                        elif "Limit" in action["details"]:
                            entry_type += "_LIMIT"
                        res_entry = {
                            "From": float(action["currentValue"])/(1024*1024),
                            "To": float(action["newValue"])/(1024*1024),
                            "Type":entry_type,
                            "UUID": entity["UUID"]
                        }
                        res.append(res_entry)
                else:
                    for entry in action["compoundActions"]:
                        if entry["valueUnits"] == "mCores":
                            entry_type = "VCPU"
                            if "Request" in entry["details"]:
                                entry_type += "_REQ"
                            else:
                                entry_type += "_LIMIT"
                            
                            res_entry = {
                                "From": int(float(entry["currentValue"])),
                                "To": int(float(entry["newValue"])),
                                "Type":entry_type,
                            "UUID": entity["UUID"]
                            }
                            res.append(res_entry)
                        elif entry["valueUnits"] == "KB":
                            entry_type = "VMEM"
                            if "Request" in entry["details"]:
                                entry_type += "_REQ"
                            else:
                                entry_type += "_LIMIT"
                            res_entry = {
                                "From": float(entry["currentValue"])/(1024*1024),
                                "To": float(entry["newValue"])/(1024*1024),
                                "Type":entry_type,
                                "UUID": entity["UUID"]
                            }
                            res.append(res_entry)
                        else:
                            print("Huh ? "+str(entry))
                        
        else:
            for entry in answer:
                count = count + 1
                if entry["valueUnits"] == "vCPU":
                    res_entry = {
                        "From": int(float(entry["currentValue"])),
                        "To": int(float(entry["newValue"])),
                        "Type":"VCPU_REQ",
                        "UUID": entity["UUID"]
                    }
                    res.append(res_entry)
                elif entry["valueUnits"] == "KB" and "VMem" in entry["details"]:
                    res_entry = {
                        "From": float(entry["currentValue"])/(1024*1024),
                        "To": float(entry["newValue"])/(1024*1024),
                        "Type":"VMEM_REQ",
                        "UUID": entity["UUID"]
                    }
                    res.append(res_entry)
        
        progress_bar(count, total)
        count += 1    
    q.put(res)


def get_action_list_chunk_cloud(case_data, list_fragment, q):
    res = []
    count = 0
    entries = []
    total = len(list_fragment)
    start_time = int(time.time()-3600*24*7)*1000
    end_time = int(time.time()+3600*24*7)*1000
    for entity in list_fragment:
        data =  {"statistics":[{"name":"VCPU","groupBy":["percentile"]},{"name":"VMem","groupBy":["percentile"]},{"name":"numVCPUs","groupBy":["percentile"]}],"startDate":start_time,"endDate":end_time}
        cpu_action = {}
        memory_action = {}
        answer, headers = handle_request("POST",case_data["url"]+"api/v3/stats/"+entity["UUID"]+"?disable_hateoas=true",case_data["cookie"], data=json.dumps(data))
        if answer == None:
            print("Huh?")
            continue
        mhz_per_vcpu = 0
        vcpu = 0
        mhz = 0
        mhz_to = 0
        for epoch in answer: 
            if epoch["epoch"] == "CURRENT":
                for entry in epoch["statistics"]:
                    if entry["name"] == "VCPU":
                        mhz = entry["capacity"]["total"]
                    if entry["name"] == "numVCPUs":
                        vcpu = entry["values"]["total"]
        if vcpu != 0 and mhz != 0:
            mhz_per_vcpu = float(mhz / vcpu)
        for epoch in answer:
            if epoch["epoch"] == "CURRENT":
                for entry in epoch["statistics"]: # Skip through entries, fill by value
                    if entry["name"] == "VMem":
                        current = entry["capacity"]["total"]/(1024*1024)
                        entry_type = "VMEM_REQ"
                        memory_action["From"] = int(current)
                        memory_action["Type"] = entry_type
                        memory_action["UUID"] = entity["UUID"]
                    elif entry["name"] == "numVCPUs":
                        current = entry["values"]["total"]
                        vcpu = current
                        entry_type = "VCPU_REQ"
                        cpu_action["From"] = int(current)
                        cpu_action["Type"] = entry_type
                        cpu_action["UUID"] = entity["UUID"]
            elif epoch["epoch"] == "PROJECTED":
                for entry in epoch["statistics"]: # Skip through entries, fill by value
                    if entry["name"] == "VMem":
                        current = entry["capacity"]["total"]/(1024*1024)
                        entry_type = "VMEM_REQ"
                        memory_action["To"] = int(current)
                        memory_action["Type"] = entry_type
                        memory_action["UUID"] = entity["UUID"]
                    elif entry["name"] == "VCPU":
                        current = entry["values"]["total"]
                        entry_type = "VCPU_REQ"
                        mhz_to = current
                        cpu_action["To"] = int(math.ceil(current/mhz_per_vcpu))
                        cpu_action["Type"] = entry_type
                        cpu_action["UUID"] = entity["UUID"]
                    elif entry["name"] == "numVCPUs":
                        current = entry["capacity"]["total"]
                        entry_type = "VCPU_REQ"
                        cpu_action["To"] = int(current)
                        cpu_action["Type"] = entry_type
                        cpu_action["UUID"] = entity["UUID"]
        # Now need to check for actions, otherwise we screw up our environment. 
        answer_actions, headers = handle_request("GET", case_data["url"]+"api/v3/entities/"+entity["UUID"]+"/actions",case_data["cookie"])
        for entry in answer_actions:
            if entry["risk"].get("reasonCommodities", "") != "":
                if "VCPU" in entry["risk"]["reasonCommodities"]:
                    if cpu_action.get("To","") == "":
                        cpu_action["To"] = cpu_action["From"]
                    print("Scaling : "+str(cpu_action)+" With factor: "+str(mhz_per_vcpu)+" Running at : "+str(mhz_to))
                    res.append(cpu_action)
                if "VMem" in entry["risk"]["reasonCommodities"]:
                    if memory_action.get("To","") == "":
                        memory_action["To"] = memory_action["From"] 
                    res.append(memory_action)
        progress_bar(count, total)
       # print(str(cpu_action))
        count += 1    
    q.put(res)
def get_generic_list(case_data, queue_func, entity_list=[]):
    length = 0
    if len(entity_list) == 0:
        length = int(get_list_length(case_data))
        print("Obtained length alternatively, value: "+str(length))
    else:
        length = len(entity_list)
    cursors, limit = get_cursors(length, THREAD_COUNT)
    count = 0
    # Get list of VMs in Scope:
    q = queue.Queue()
    thread_list = []
    res_list = []
    for cursor in cursors: 
        count = count + 1
        step = limit
        if len(entity_list) == 0 and length != 0:
            t = threading.Thread(target=queue_func, args=(case_data, cursor, limit, q))
        else:
            t = threading.Thread(target=queue_func, args=(case_data, entity_list[cursor:cursor+limit], q))
        t.start()
        thread_list.append(t)
        
    count = 0
    for x in thread_list:
        count = count + 1
        x.join()
    while q.qsize() > 0:
        res_list.extend(q.get())
        count = count + 1
    
    return res_list   

def get_authentication_cookie(credentials):
    login_data = {"username": credentials["user"], "password": credentials["password"]}
    r = requests.post("https://"+credentials["url"]+"/api/v3/login?hateoas=true", verify=False, data=login_data)
    return r.cookies #TODO: Maybe also use the handle_requests function? this is easier since it is a singular occurence per session and we never else need the cookie..

def get_list_length(case_data):
    answer, headers = handle_request("GET",case_data["url"]+"api/v3/groups/"+case_data["scope"], case_data["cookie"])
    return str(answer["membersCount"])
def get_detail_k8s(case_data, uuid):
    data = {}
    if case_data["entity_type"] == "WorkloadController":
        data = {
            "statistics":[{ 
                "name": "VMemRequestQuota"
            },{
            "name": "VCPURequestQuota","filters": [
					{
						"type": "relation",
						"value": "sold"
					}]},{
            "name": "VMemLimitQuota","filters": [
					{
						"type": "relation",
						"value": "sold"
					}]},{
            "name": "VCPULimitQuota","filters": [
					{
						"type": "relation",
						"value": "sold"
					}]}]
        }
    elif case_data["entity_type"] in ["Namespace", "ContainerCluster", "ContainerPod"]:
        data = {
            "statistics":[{ 
                "name": "VMemRequest"
            },{
            "name": "VCPURequest"},{
            "name": "VMemLimit"},{
            "name": "VCPULimit"}]
        }
    elif case_data["entity_type"] in ["ContainerSpec"]:
        data = {
            "statistics":[{
            "name": "VCPU"},{
            "name": "VMem"}
        ]}
    elif case_data["entity_type"] in ["VirtualMachine"]:
        data = {
        "statistics":[{ 
            "name": "vMem"
        },{
        "name": "numVCPUs"}]
    }
    answer, headers = handle_request("POST",case_data["url"]+"api/v3/entities/"+uuid+"/stats",case_data["cookie"], json.dumps(data))
    
    if len(answer) < 1:
        print("RETURNING EMPTY: ")
        return {}
    returnVal = {
        "UUID": uuid,
        "Application": "N/A",
        "environmentType": "N/A",
        "Name": answer[0]["displayName"],
        "VCPU": {
            "Request": {
                "Current": 0,
                "Target": 0
            },
            "Limit": {
                "Current": 0,
                "Target": 0
            }
        },
        "VMEM": {
            "Request": {
                "Current": 0.0,
                "Target": 0.0
            },
            "Limit": {
                "Current": 0.0,
                "Target": 0.0
            }
        }}
    if case_data["entity_type"] not in  ["VirtualMachine", "ContainerSpec"]:
        for entry in answer[0]["statistics"]:
            current = 0
            if "VMem" in entry["name"]:
                current = entry["capacity"]["total"]
            current =entry["value"]
            if "VCPU" in entry["name"] and "Request" in entry["name"]:
                returnVal["VCPU"]["Request"]["Current"] =  current
                returnVal["VCPU"]["Request"]["Target"] = current
            if "VCPU" in entry["name"] and "Limit" in entry["name"]:
                returnVal["VCPU"]["Limit"]["Current"] =  current
                returnVal["VCPU"]["Limit"]["Target"] = current
            if "VMem" in entry["name"] and "Request" in entry["name"]:
                returnVal["VMEM"]["Request"]["Current"]= current/(1024*1024)
                returnVal["VMEM"]["Request"]["Target"]= current/(1024*1024)
            if "VMem" in entry["name"] and "Limit" in entry["name"]:
                returnVal["VMEM"]["Limit"]["Current"]= current/(1024*1024)
                returnVal["VMEM"]["Limit"]["Target"]= current/(1024*1024)
    else:
        for entry in answer[0]["statistics"]:
            current = 0
            if "VMem" in entry["name"]:
                current = entry["capacity"]["total"]
            else:
                current =entry["value"]
            if "VCPU" in entry["name"]:
                returnVal["VCPU"]["Request"]["Current"] =  current
                returnVal["VCPU"]["Request"]["Target"] = current
            if "VMem" in entry["name"]:
                returnVal["VMEM"]["Request"]["Current"]= current/(1024*1024)
                returnVal["VMEM"]["Request"]["Target"]= current/(1024*1024)
    return returnVal

def progress_bar(current, total, bar_length=50):
    global previous
    if  previous < current:
        fraction = current / total
        arrow = int(fraction * bar_length - 1) * '-' + '>'
        padding = int(bar_length - len(arrow)) * ' '
        ending = '\n' if current == total else '\r'
        if current < total: 
            sys.stdout.write("\033[K")
        print(f'Progress: [{arrow}{padding}] {int(fraction*100)}%', end=ending)
        previous = current
        
def get_list_chunk_k8s(case_data, cursor, limit, q):
    list, headers = handle_request("GET",case_data["url"]+"api/v3/groups/"+case_data["scope"]+"/entities?cursor="+str(cursor)+"&limit="+str(limit),case_data["cookie"])
    result = []
    count = 0
    total = 0
    if case_data["entity_type"] == "VirtualMachine":
        for entry in list:
            total += len(entry.get("consumers", []))
            total += len(entry.get("providers", []))
        for entry in list: 
            count = count +1
            entities = []
            consumers = entry.get("consumers", [])
            providers = entry.get("providers", [])
            entities = providers
            if len(consumers) > 0:
                entities.extend(consumers)
            if entry["className"] == case_data["entity_type"]:
                    count += 1
                    detailEntry = get_detail_k8s(case_data, entry["uuid"])
                    if len(detailEntry) > 0:
                        detailEntry["environmentType"] = entry["environmentType"]
                        result.append(detailEntry)
            for vm in entities:
                if vm["className"] == case_data["entity_type"]:
                    detailEntry = get_detail_k8s(case_data, vm["uuid"])
                    if len(detailEntry) > 0: 
                        detailEntry["environmentType"] = entry["environmentType"]
                        result.append(detailEntry)
                progress_bar(count, total)
    else:
        total = len(list)
        for entry in list: 
            count = count +1
            if entry["className"] == case_data["entity_type"]:
                    detailEntry = get_detail_k8s(case_data, entry["uuid"])
                    if len(detailEntry) > 0:
                        detailEntry["environmentType"] = entry["environmentType"]
                        result.append(detailEntry)
            progress_bar(count, total)
    q.put(result)

def get_policy_parameters(policies, managerName, entity):
    ret_val = {}
    for entry in policies: 
        if entry["entityType"] == entity and entry["default"] == True: 
            for manager in entry["settingsManagers"]:
                if manager["uuid"] ==  managerName:
                    for setting in manager["settings"]:
                            ret_val[setting["displayName"]] = setting["value"]
    return ret_val
def get_policy_parameter(policies, managerName, entity, settingName):
    for entry in policies: 
        if entry["entityType"] == entity and entry["default"] == True: 
            for manager in entry["settingsManagers"]:
                if manager["uuid"] ==  managerName:
                    for setting in manager["settings"]:
                        if setting["uuid"] == settingName:
                            return setting["value"]
    return "Not Found"
def set_policies(case_data,policies):
    count = 0
    for entry in policies:  
        if entry["readOnly"] == True:
            continue
        uuid = entry["uuid"]
        answer, headers = handle_request("PUT",case_data["url"]+"api/v3/settingspolicies/"+uuid, case_data["cookie"],  data=json.dumps(entry))
        if "Container" in entry["displayName"] :
            print(str(answer))
        count += 1
    return True
def get_market_data(case_data, uuid):
    answer, header = handle_request("GET", case_data["url"]+"api/v3/markets/"+uuid+"/stats", case_data["cookie"])
    returnVal = {"Name": answer[0]["displayName"], "Hosts":{"Current": 0, "Projected": 0}, "Mem": {"Current": 0, "Projected": 0},"CPU": {"Current": 0, "Projected": 0},"VMem": {"Current": 0, "Projected": 0}, "VCPU": {"Current": 0, "Projected": 0}, "Storages": {"Current": 0, "Projected": 0}, "Space":{"Current": 0, "Projected": 0}}
    for entry in answer[0]["statistics"]:
        if entry["name"] == "VMem" and entry["relatedEntityType"] == "VirtualMachine":
            if len(entry["filters"]) > 0:#previous
                returnVal["VMem"]["Current"] = entry["capacity"]["total"]/(1024*1024)
            else:
                returnVal["VMem"]["Projected"] = entry["capacity"]["total"]/(1024*1024)

        if entry["name"] == "VCPU" and entry["relatedEntityType"] == "VirtualMachine":
            if len(entry["filters"]) > 0:#previous
                returnVal["VCPU"]["Current"] = entry["capacity"]["total"]/1000
            else:
                returnVal["VCPU"]["Projected"] = entry["capacity"]["total"]/1000
        if entry["name"] == "Mem":
            value = float(entry["capacity"]["total"])/(1024*1024)
            if len(entry["filters"]) > 0:#previous
                returnVal["Mem"]["Current"] = value
            else:
                returnVal["Mem"]["Projected"] = value
        if entry["name"] == "numCPUs":
            value = float(entry["value"]) #GHz
            if len(entry["filters"]) > 0:#previous
                returnVal["CPU"]["Current"] = value
            else:
                returnVal["CPU"]["Projected"] = value
        if entry["name"] == "StorageAmount":
            value = entry["capacity"]["total"]/(1024*1024) #TB
            if len(entry["filters"]) > 0:#previous
                returnVal["Space"]["Current"] = value
            else:
                returnVal["Space"]["Projected"] = value
        if entry["name"] == "numHosts":
            value = entry["value"]
            if len(entry["filters"]) > 0:#previous
                returnVal["Hosts"]["Current"] = value
            else:
                returnVal["Hosts"]["Projected"] = value
        if entry["name"] == "numStorages":
            value = entry["value"]
            if len(entry["filters"]) > 0:#previous
                returnVal["Storages"]["Current"] = value
            else:
                returnVal["Storages"]["Projected"] = value
    return returnVal
    
def create_plan(case_data, plan_name, market_uuid, scenario_uuid):
    data = {"plan_market_name": plan_name}
    answer, headers = handle_request("POST", case_data["url"]+"api/v3/markets/"+market_uuid+"/scenarios/"+scenario_uuid, case_data["cookie"],data=json.dumps(data))
    return {"uuid": answer["uuid"], "Name": answer["displayName"]}
def is_market_done(case_data, uuid):
    answer, headers = handle_request("GET", case_data["url"]+"api/v3/markets/"+uuid, case_data["cookie"])
    if answer["stateProgress"] == 100:
        return True
    return False
def create_scenario(case_data, name, uuid, type):
    # first check if scope is not empty: 
    case_data["scope"] = uuid
    if int(get_list_length(case_data)) > 0:
        data = {"scope": [{"uuid":uuid}], "displayName": name, "type": type}
        answer, headers = handle_request("POST", case_data["url"]+"api/v3/scenarios", case_data["cookie"], data=json.dumps(data))
        return answer["uuid"]
    else:
        return -1
def set_policy_parameter(policies,entity,manager_name, name, value):
    managerCount = 0
    settingsCount = 0
    entityCount = 0
    print("Handling: "+str(entity)+"manager_name:"+ manager_name+" name: "+name+" Value:"+str(value))
    for entry in policies: 
        if entry["entityType"] == entity and entry["default"] == True: #VM etc. 
            for manager in entry["settingsManagers"]:
                if manager["uuid"] == manager_name:
                    for setting in manager["settings"]:
                        if setting["displayName"] == name:
                            policies[entityCount]["settingsManagers"][managerCount]["settings"][settingsCount]["value"] = value
                            print("Found: "+str(setting))
                            return True
                        settingsCount += 1
                managerCount += 1
        entityCount += 1
    return False
def get_active_policies(case_data, group_uuid, entity=False):
    answer = {}
    if entity == True:
        print("Getting policies for entity, not group")
        answer, headers = handle_request("GET", case_data["url"]+"api/v3/entities/"+group_uuid+"/settings?include_settingspolicies=true", case_data["cookie"])
    else:
        answer, headers = handle_request("GET", case_data["url"]+"api/v3/groups/"+group_uuid+"/settings?include_settingspolicies=true", case_data["cookie"])
    active_policies = []
    for entry in answer:
        for setting in entry["settings"]:
            if setting.get("activeSettingsPolicies", "") != "":
                for policy in setting["activeSettingsPolicies"]:
                    active_policies.append({"PolicyName": policy["settingsPolicy"]["displayName"], "Value": policy["value"], "Setting": setting["displayName"]})
    return active_policies
def create_policy(case_data,uuid, policy_name, entityType, managerCategory, settingsUuid, value):
    data = {
        "displayName": policy_name,
        "scopes" : [{"uuid": uuid}],
        "entityType": entityType,
        "settingsManagers":[
            {"category": managerCategory,
             "settings":[{"uuid": settingsUuid, "value": value}]}
        ]
    }
    answer, headers = handle_request("POST", case_data["url"]+"api/v3/settingspolicies", case_data["cookie"], data=json.dumps(data))
    return answer
def get_percentage(a, b):
    if b > 0:
        return str(round(float(a/b*100),2))+"%"
    else:
        return "0.0%"
def delete_group(case_data, uuid):
    handle_request("DELETE",case_data["url"]+"api/v3/groups/"+uuid,  case_data["cookie"])
    print("Deleted group "+str(uuid))

def print_to_file_k8s(case_data,entries):
    with open("result.csv", "w") as f:
        savedMemRequest = 0
        savedMemLimit = 0
        savedCpuRequest = 0
        savedCpuLimit = 0
        investedMemRequest = 0
        investedMemLimit = 0
        investedCpuRequest = 0
        investedCpuLimit = 0
        totalMemRequest = 0
        totalMemLimit = 0
        totalCpuRequest = 0
        cpuUnit = "mCores"
        k8s_suffix = "Request"
        if case_data["entity_type"] == "VirtualMachine":
            cpuUnit = "vCPU"
            k8s_suffix = ""
        totalCpuLimit = 0
        writer = csv.writer(f, delimiter =";") 
        header = ["UUID", "Name", "Application",  "Current VCPU Limit","Current VCPU Request", "Target VCPU Limit", "Target VCPU Request", "Current VMEM Limit","Current VMEM Request", "Target VMEM Limit", "Target VMEM Request"]
        writer.writerow(header)
        for entry in entries: 
           
            line = [entry["Name"],entry["Application"],entry["VCPU"]["Limit"]["Current"],entry["VCPU"]["Request"]["Current"],entry["VCPU"]["Limit"]["Target"],entry["VCPU"]["Request"]["Target"], str(entry["VMEM"]["Limit"]["Current"]), str(entry["VMEM"]["Request"]["Current"]), str(entry["VMEM"]["Limit"]["Target"]),  str(entry["VMEM"]["Request"]["Target"])]
            writer.writerow(line)
            if entry["VMEM"]["Request"]["Target"] > entry["VMEM"]["Request"]["Current"]:
                investedMemRequest += (entry["VMEM"]["Request"]["Target"] - entry["VMEM"]["Request"]["Current"])
            else:
                savedMemRequest += (entry["VMEM"]["Request"]["Current"] - entry["VMEM"]["Request"]["Target"])
            if entry["VMEM"]["Limit"]["Target"] > entry["VMEM"]["Limit"]["Current"] :
                investedMemLimit += (entry["VMEM"]["Limit"]["Target"] - entry["VMEM"]["Limit"]["Current"])
            else:
                savedMemLimit += (entry["VMEM"]["Limit"]["Current"] - entry["VMEM"]["Limit"]["Target"])
            if entry["VCPU"]["Request"]["Target"] > entry["VCPU"]["Request"]["Current"]:
                investedCpuRequest += entry["VCPU"]["Request"]["Target"] - entry["VCPU"]["Request"]["Current"]
            else: 
                savedCpuRequest += (entry["VCPU"]["Request"]["Current"] - entry["VCPU"]["Request"]["Target"])
            if entry["VCPU"]["Limit"]["Target"] > entry["VCPU"]["Limit"]["Current"]:
                investedCpuLimit += (entry["VCPU"]["Limit"]["Target"] - entry["VCPU"]["Limit"]["Current"])
            else:
                savedCpuLimit += (entry["VCPU"]["Limit"]["Current"] - entry["VCPU"]["Limit"]["Target"])
            totalMemRequest += (entry["VMEM"]["Request"]["Current"])
            totalMemLimit += (entry["VMEM"]["Limit"]["Current"])
            totalCpuRequest += (entry["VCPU"]["Request"]["Current"])
            totalCpuLimit += (entry["VCPU"]["Limit"]["Current"])
        percentageCpuLimit = get_percentage((savedCpuLimit-investedCpuLimit), totalCpuLimit)
        percentageCpuRequest = get_percentage((savedCpuRequest-investedCpuRequest), totalCpuRequest)
        percentageMemLimit = get_percentage((savedMemLimit-investedMemLimit), totalMemLimit)
        percentageMemRequest = get_percentage((savedMemRequest-investedMemLimit), totalMemRequest)
        headers = ["Parameter", "total", "to invest", "saveable","after action", "change [%]"]
        cpuRequest = ["vCPU "+k8s_suffix, str(totalCpuRequest)+cpuUnit,str(investedCpuRequest)+cpuUnit, str(savedCpuRequest)+cpuUnit,str(totalCpuRequest-savedCpuRequest)+cpuUnit, percentageCpuRequest]
        cpuLimit = ["-","-","-","-","-","-"]
        memLimit = cpuLimit
        if case_data["entity_type"] != "VirtualMachine":
            cpuLimit = ["vCPU Limit", str(totalCpuLimit)+cpuUnit,str(investedCpuLimit)+cpuUnit,  str(savedCpuLimit)+cpuUnit,str(totalCpuLimit-savedCpuLimit)+cpuUnit, percentageCpuLimit]
        memRequest = ["vMEM "+k8s_suffix, str(totalMemRequest)+"GB",str(investedMemRequest)+"GB", str(savedMemRequest)+"GB",str(totalMemRequest-savedMemRequest)+"GB", percentageMemRequest]
        if case_data["entity_type"] != "VirtualMachine":
            memLimit = ["vMEM Limit", str(totalMemLimit)+"GB",str(investedMemLimit)+"GB", str(savedMemLimit)+"GB",str(totalMemLimit-savedMemLimit)+"GB", percentageMemLimit]
        result_values = {"CPURequest": {
        "total": totalCpuRequest, "invested": investedCpuRequest, "saved": savedCpuRequest, "change": percentageCpuRequest},
         "CPULimit":{
        "total": totalCpuLimit, "invested": investedCpuLimit, "saved": savedCpuLimit, "change": percentageCpuLimit}, 
        "MemRequest": {
        "total": totalMemRequest, "invested": investedMemRequest, "saved": savedMemRequest, "change": percentageMemRequest}, "MemLimit": {
        "total": totalMemLimit, "invested": investedMemLimit, "saved": savedMemLimit, "change": percentageMemLimit}}
        

        
    return result_values
def get_cursors(length, threads):
    cursors = []
    last = length
    step = length
    if threads > 1:
        last = length % (threads -1)
        step = int(length / (threads-1))
    if threads > length:
        threads = length
        step = 1
    count = 0
    cursors.append(0)
    while count < length:
        if count + step <= length:
            count += step 
        else:
            count += last
        cursors.append(count)
    
    return cursors, step

def get_group_name(case_data, scope):
    answer,headers = handle_request("GET",case_data["url"]+"api/v3/groups/"+scope,case_data["cookie"])
    return answer["displayName"]
def get_entity_list_chunk(case_data, list_fragment,q):
    res = []
    count = 0 
    for list_entry in list_fragment:
        cpu_req = 0
        mem_req = 0
        cpu_limit = 0
        mem_limit = 0
        answer, headers = handle_request("GET",case_data["url"]+"api/v3/entities/"+list_entry["UUID"]+"/stats", case_data["cookie"])
        
        for stat in answer[0]["statistics"]:
            if "numCPUs" in stat["name"]:
                cpu_req =  stat["values"]["total"]
            elif stat["name"] == "Mem":
                mem_req = int(stat["capacity"]["total"])/(1024*1024)
            elif stat["name"] == "MemProvisioned":
                mem_req = int(stat["values"]["total"])/(1024*1024)
            elif stat["name"] == "VMemRequestQuota":
                mem_req = int(stat["capacity"]["total"])/(1024*1024)


            elif "numVCPUs" in stat["name"]:
                cpu_req = stat["values"]["total"]
            elif stat["name"] == "VCPURequestQuota":
                cpu_req = int(stat["values"]["total"]) / 1000
            elif stat["name"] == "VCPULimitQuota":
                cpu_limit = int(stat["capacity"]["total"]) / 1000
                if cpu_limit > 1e8:
                    cpu_limit = -1
            elif stat["name"] == "VMemLimitQuota":
                mem_limit = int(stat["capacity"]["total"])/(1024*1024)
                if mem_limit > 1e8:
                    mem_limit = -1


        res.append({ "UUID" : list_entry, "Name": answer[0]["displayName"],"MemoryRequest": mem_req, "CpuRequest": cpu_req, "MemoryLimit": mem_limit, "CpuLimit": cpu_limit})
        count += 1
        progress_bar(count, len(list_fragment))
    q.put(res)


