import streamlit as st
from backend_functions import *
from functions import *
import math
from time import time 
def get_timestamp(offset_hours):
    timestamp = int(time())
    timestamp -= offset_hours*(60*60)
    return timestamp
def get_data(case_data, entity_type,uuid):
    # This function should handle the entity_type specific stuff like which parameters to gather etc. 
    if entity_type in ["Namespace", "ContainerPlatformCluster"]:
        #Statistic VCPURequest, VMemRequest, VMem, VCPU
        data = {"statistics":[{"name": "VCPU"}, {"name": "VCPURequest",},{"name": "VMem"}, {"name": "VMemRequest"}]}
        answer, _ = handle_request("POST", case_data["url"]+"api/v3/stats/"+uuid, data=json.dumps(data), cookie=case_data["cookie"])
        res = {}
        for entry in answer[0]["statistics"]:
            value = entry["values"]["avg"]
            if "Mem" in entry["name"]:
                value = value / 1024
            name = entry["name"]
            if not "Request" in name:
                name += "Limit"
            res[entry["name"]] = value
        return res
    if entity_type in ["Cluster"]:
        start_time = get_timestamp(24)
        end_time = get_timestamp(12)
        data = {"statistics":[{"name": "Mem"},  {"name": "numHosts"},{"name": "numCPUs"}],"startDate": str(start_time)}
        answer, _ = handle_request("POST", case_data["url"]+"api/v3/stats/"+uuid, data=json.dumps(data), cookie=case_data["cookie"])
        res = {}
        for stat in answer:
            for entry in stat["statistics"]:
                value = entry["values"]["avg"]
                if "Mem" in entry["name"]:
                    value = value / 1024
                name = entry["name"]
                if not "Request" in name:
                    name += "Limit"
                res[entry["name"]] = value
        return res

    
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
