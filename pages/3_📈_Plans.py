import streamlit as st
from backend_functions import *
from functions import *
import math
from time import time 
def get_timestamp(offset_hours):
    timestamp = int(time())
    timestamp -= offset_hours*(60*60)
    return timestamp
def handle_container_actions(uuid):
     data = {"statistics":[{"name": "VCPU"}, {"name": "VCPURequest",},{"name": "VMem"}, {"name": "VMemRequest"}]}
     answer, _ = handle_request("POST", case_data["url"]+"api/v3/stats/"+uuid, data=json.dumps(data), cookie=case_data["cookie"])
     res = {}
     for entry in answer[0]["statistics"]:
        value = entry["values"]["avg"]
        if "Mem" in entry["name"]:
            value = value / 1024
        name = entry["name"]
        if name.find("Request") == -1:
            name += "Limit"
        res[name] = value
        action_list = get_generic_list(case_data, "api/v3/entities/"+uuid+"/actions", get_list_fragment_for_actions, {"Uuid": uuid})
        action_count = 0
        for entry in action_list:
            if entry["actionType"] == "RESIZE":
                if entry.get("compoundActions", "") == "":
                    continue
                for action in entry["compoundActions"]:
                    action_count += 1
                    value = float(action["newValue"]) - float(action["currentValue"]) 
                    action_type = ""
                    if "VMem" in action["details"]:
                        action_type = "VMem"
                        value = value / 1024
                    else:
                        action_type = "VCPU"
                    if "Request" in action["details"]:
                        action_type += "Request"
                    else:
                        action_type += "Limit"
                    if res.get("Action_"+action_type, "") == "":
                        res["Action_"+action_type] = value
                    else:
                        res["Action_"+action_type] += value
        res["ActionCount"] = action_count
     return res
def get_data(case_data, entity_type,uuid):
    start_time = get_timestamp(24)
    # This function should handle the entity_type specific stuff like which parameters to gather etc. 
    if entity_type in ["Namespace", "ContainerPlatformCluster"]:
        #Statistic VCPURequest, VMemRequest, VMem, VCPU
        res =  handle_container_actions(uuid)
        return res
    if entity_type in ["Cluster"]:
        print("Started Cluster aggregation")
        data = {"statistics":[{"name": "Mem"},  {"name": "numHosts"},{"name": "numCPUs"}],"startDate": str(start_time)}
        answer, _ = handle_request("POST", case_data["url"]+"api/v3/stats/"+uuid, data=json.dumps(data), cookie=case_data["cookie"])
        res = {}
        for stat in answer:
            for entry in stat["statistics"]:
                value = entry["values"]["avg"]
                if "Mem" in entry["name"]:
                    value = value / (1024*1024)
                res[entry["name"]] = value
        # Have to get actions on a VM Level, so first get all VMs in the Cluster... 
        entity_list = get_generic_list(case_data, "api/v3/search?types=VirtualMachine&scopes="+uuid+"&order_by=NAME&ascending=true", get_list_fragment_vms_for_hosts, {"Uuid":uuid}) 
        print("Received entity List, handling actions")
        res_list = threadify_list(entity_list, handle_action_vm_thread_ready )
        res = {}
        for entry in res_list:
            # Handle this list via threads to speed up..
            for key in entry:
                if res.get(key, "") == "":
                    res[key] = entry[key]
                else: 
                    res[key] += entry[key]
        return res
    if entity_type in ["BusinessApplication"]:
        # First get BA name
        answer, header = handle_request("GET", case_data["url"]+"api/v3/entities/"+uuid,cookie=case_data["cookie"])
        business_app_name = answer["displayName"]
        entity_list = get_generic_list(case_data, "api/v3/search?types=VirtualMachine&scopes="+uuid+"&order_by=NAME&ascending=true", get_list_fragment_search, {"Name": business_app_name, "className": "VirtualMachine", "filterType": "vmsByBusinessApplication"})
        # now get stats for all vms.. 
        res = {}
        res["VM count"] = len(entity_list)
        for entry in entity_list: 
            data = {"statistics":[{"name": "numVCPUs"},  {"name": "VMem"}],"startDate": str(start_time)}
            entry_uuid = entry["Uuid"]
            stats, _ = handle_request("POST", case_data["url"]+"api/v3/stats/"+entry_uuid, data=json.dumps(data), cookie=case_data["cookie"])
            for stat_entry in stats:
                for stat in stat_entry["statistics"]:
                    value = 0 
                    if stat.get("capacity", "") != "":
                        value = stat["capacity"]["avg"]
                    else:
                        value = stat["values"]["avg"]
                    if "Mem" in stat["name"]:
                        value = value / (1024*1024)
                    name = stat["name"]
                    if res.get(name, "") != "":
                        res[stat["name"]] += value
                    else:
                        res[name] = value
            res_list = threadify_list(entity_list, handle_action_vm_thread_ready )
            for entry in res_list:
                # Handle this list via threads to speed up..
                for key in entry:
                    if res.get(key, "") == "":
                        res[key] = entry[key]
                    else: 
                        res[key] += entry[key]
            print(str(res))
            entity_list = get_generic_list(case_data, "api/v3/search?types=ContainerPod&order_by=NAME&ascending=true", get_list_fragment_search, {"Name": business_app_name, "className": "Container", "filterType": "containersByBusinessApplication"})
            res_list = threadify_list(entity_list, get_wl_controller_thread_ready)
            
            wl_list = []
            for entry in res_list: 
                for key in entry.keys():
                    wl_list.append(entry[key])
            res_list = threadify_list(wl_list, get_wl_controller_actions_thread_ready)
            print(str(res_list))
            for entry in res_list:
                # Handle this list via threads to speed up..
                for key in entry:
                    if res.get(key, "") == "":
                        res[key] = entry[key]
                    else: 
                        res[key] += entry[key]
            
            return res
            # Todo : handle containers.. 
            # Could do a search of COntainers per Business app.. from there need to figure out the involved Workload Controllers to generate savings ? 
            # Collect unique WL controllers per identified COntainer.. 
            # Do a scrape of the Entity, then look into the providers, gather all unique UUIDs. 
            # Then get actions on those WL Controllers
def get_wl_controller_actions_thread_ready(list, q):
    res = {}
    action_count = 0
    for entity in list: 
        print(str(entity))
        
        action_list = get_generic_list(case_data, "api/v3/entities/"+entity+"/actions", get_list_fragment_for_actions, {"Uuid": entity})
        for entry in action_list:
                if entry["actionType"] == "RESIZE":
                    if entry.get("compoundActions", "") == "":
                        continue
                    for action in entry["compoundActions"]:
                        action_count += 1
                        value = float(action["newValue"]) - float(action["currentValue"]) 
                        action_type = ""
                        if "VMem" in action["details"]:
                            action_type = "VMem"
                            value = value / 1024
                        else:
                            action_type = "VCPU"
                        if "Request" in action["details"]:
                            action_type += "Request"
                        else:
                            action_type += "Limit"
                        if res.get("Action_"+action_type, "") == "":
                            res["Action_"+action_type] = value
                        else:
                            res["Action_"+action_type] += value
    res["Container ActionCount"] = action_count
    q.put(res)
def get_wl_controller_thread_ready(list, q):
    res = {}
    for entry in list:
        answer, _ = handle_request("GET", case_data["url"]+"api/v3/entities/"+entry["Uuid"]+"?include_aspects=true", cookie=case_data["cookie"])
        if answer["aspects"].get("containerPlatformContextAspect", "") != "":
                if answer["aspects"]["containerPlatformContextAspect"].get("workloadControllerEntity", "") != "":
                    res[entry["Uuid"]] = answer["aspects"]["containerPlatformContextAspect"]["workloadControllerEntity"]["uuid"]
                   
    q.put(res)
    
def handle_action_vm_thread_ready(list,q):
    res = {}
    for entry in list:
        answer, _ = handle_request("GET", case_data["url"]+"api/v3/entities/"+entry["Uuid"]+"/actions", cookie=case_data["cookie"])
        print("Length for this VM: "+str(len(answer)))
        local_action_count = 0 
        for entry in answer:
            if entry["actionType"] == "RESIZE":
                local_action_count += 1
                value = float(entry["newValue"]) - float(entry["currentValue"])
                action_type = ""
                if "VCPU" in entry["details"]:
                    action_type = "VCPU"
                else: 
                    action_type ="VMem"
                    value = value / (1024*1024)
                if res.get("Action_"+action_type, "") == "":
                    res["Action_"+action_type] = value
                else:
                    res["Action_"+action_type] += value
        if res.get("VM ActionCount","") == "":
            res["VM ActionCount"] =  local_action_count
        else: 
            res["VM ActionCount"] += local_action_count
    q.put(res)
def get_list_fragment_vms_for_hosts(case_data, cursor, limit, q, query):
    res = []
    count = 0
    entries = []
    answer, headers = handle_request("GET",case_data["url"]+"api/v3/search?types=VirtualMachine&scopes="+query["Uuid"]+"&cursor="+str(cursor)+"&limit="+str(limit)+"&order_by=NAME&ascending=true",case_data["cookie"])

    for entry in answer:
        res.append({"Name": entry["displayName"], "Uuid": entry["uuid"]})
    q.put(res)

def get_list_fragment_for_actions(case_data, cursor, limit, q, query):
    answer, headers = handle_request("GET",case_data["url"]+"api/v3/entities/"+query["Uuid"]+"/actions?cursor="+str(cursor)+"&limit="+str(limit)+"&order_by=NAME&ascending=true",case_data["cookie"])
    res = []
    for entry in answer:
        res.append(entry)
    q.put(res)
def get_list_fragment_search(case_data, cursor, limit, q, query):
    searchName = query["Name"].replace("(",".*").replace(")", ".*").replace("[",".*").replace("]",".*")
    data = {"criteriaList": [{"expVal": searchName, "expType": "RXEQ", "filterType": query["filterType"], "caseSensitive": "false"}], "className":query["className"],"logicalOperator": "AND"} 
    res = []
    count = 0
    entries = []
    answer, headers = handle_request("POST",case_data["url"]+"api/v3/search?cursor="+str(cursor)+"&limit="+str(limit)+"&order_by=NAME&ascending=true",case_data["cookie"], data=json.dumps(data))
    for entry in answer:
        res.append({"Name": entry["displayName"], "Uuid": entry["uuid"]})
    q.put(res)
def get_list_fragment_entity(case_data, cursor, limit, q, query):
    res = []
    count = 0
    entries = []
    answer, headers = handle_request("GET",case_data["url"]+"api/v3/search?types="+query["Type"]+"&cursor="+str(cursor)+"&limit="+str(limit)+"&order_by=NAME&ascending=true",case_data["cookie"])

    for entry in answer:
        parent = ""
        if len(entry.get("providers", [])) > 0:
            parent = entry["providers"][0]["displayName"]+" / "
        res.append({"Name": parent+entry["displayName"], "Uuid": entry["uuid"]})
    q.put(res)

def cache_reset():
    st.cache_resource.clear()

@st.cache_resource
def get_entities(entity_type):
    entity_list = get_generic_list(case_data, "api/v3/search?types="+entity_type, get_list_fragment_entity, {"Type": entity_type})
    return entity_list


check_instance_state()
populate_sidebar()
case_data = get_instance_data()
st.write("Create reports for different Entities:")
entities = {"ContainerClusters": "ContainerPlatformCluster", "Namespaces": "Namespace", "OnPremise Cluster":"Cluster", "Applications": "BusinessApplication"}
# For Applications: We take the underlying VMs (? does this make sense) as a baseline for provisioned ressources
entity_select = st.selectbox("Entity Type", entities.keys(), on_change=cache_reset)
# Selectbox to select entity Type
func_data = {"Type": entities[entity_select]}
entity_list = get_entities(entities[entity_select])

# Get list of entities and present as Checkbox list to deselect
# Generate Reports on click
# Offer PDF Download ? 
results = []
if len(entity_list) > 0:
    
    totals = {"Name": "Total"}
    boxes = []
    value = True
    if len(entity_list)> 20:
        value = False
    col_count = math.ceil(len(entity_list) / 30)
    if col_count > 3: 
        col_count = 3
    cols = st.columns(col_count)
    count = 0
    for entry in entity_list:
        count += 1
        if count > col_count - 1: 
            count = 0
        current_col = cols[count]
        # Todo: Add unique Key (especially for Namespaces if multiple K8s Clusters are there... maybe add the Cluster name ? )
        with current_col:
            boxes.append({"Value": st.checkbox(entry["Name"], value=value ), "Name": entry["Name"], "Uuid": entry["Uuid"]})
    bt = st.button("Gather current Data")
    if bt:
        with st.spinner():
            for box in boxes:
                if box["Value"] == True:
                    entry = {"Name": box["Name"]}
                    entry.update(get_data(case_data, entities[entity_select], box["Uuid"]))
                    results.append(entry)
            for entry in results: 
                for key in entry.keys(): 
                    if key != "Name":
                        if key not in totals.keys():
                            totals[key] = entry[key]
                        else:
                            totals[key] += entry[key]
            results.append(totals)
        st.dataframe(results)
# target: A table with : Namespaces, then Total as lines. Columns should be the values
else:
    st.write("No Entities of the given Type found")
