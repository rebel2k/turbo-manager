import os
from functions import get_request, post_request, get_instance_data
from backend_functions import * 
import streamlit as st

st.set_page_config(
    page_title="Reporting",
    page_icon="📊",
)

# Check if connected to a server
if ('instancename' not in st.session_state or 'turboserver' not in st.session_state or 'username' not in st.session_state or 'password' not in st.session_state or 'authtoken' not in st.session_state or 'turboversion' not in st.session_state or st.session_state['instancename'] == 'n/a' or st.session_state['turboserver'] == 'n/a' or st.session_state['username'] == 'n/a' or st.session_state['password'] == 'n/a' or st.session_state['authtoken'] == 'n/a' or st.session_state['turboversion'] == 'n/a'):
    st.error("Please, connect to a server from Homepage first!")
else:
    # Retrieve session variables (for ease of use)
    instance = st.session_state.instancename
    turboserver = st.session_state.turboserver
    username = st.session_state.username
    password = st.session_state.password
    authtoken = st.session_state.authtoken
    turboversion = st.session_state.turboversion

# Get Global Topology Stats
global_stats, status, message = get_request(turboserver, authtoken, "supplychains?disable_hateoas=true&environment_type=HYBRID&health=true&uuids=Market")
if (status == 0):
    st.success("Global Topology Data retrieval successful.")
    #st.write(global_stats["seMap"])
    # Create 6 columns to display metrics
    cols = st.columns(4)
    i = 0
    for entity_type, value in global_stats["seMap"].items():
        cols[i].metric(str(entity_type), str(value["entitiesCount"]))
        if i<3:
            i+=1
        else:
            i=0
else:
    st.error("Global Topology Data retrieval failed!")

# Get On-Prem Resize Actions impact for Virtual Machines  
payload = '{"environmentType":"ONPREM","targetEntityTypes":["VirtualMachine"],"relatedEntityTypes":["VirtualMachine"],"actionTypeList":["RESIZE"]}'
response, status, message = post_request(turboserver, authtoken, "markets/Market/actions", payload)
if (status == 0):
    st.success("On-Prem Resize Data retrieval successful.")
    vcpu_diff = 0
    vmem_diff = 0
    #st.write(response)
    for action in response:
        if action["risk"]["reasonCommodities"] == ['VMem']:
            vmem_diff += float(action["currentValue"]) - float(action["newValue"])
        elif action["risk"]["reasonCommodities"] == ['VCPU']:
            vcpu_diff += float(action["currentValue"]) - float(action["newValue"])
    vm_stats_container = st.container()
    vm_stats_cols = vm_stats_container.columns(3)
    vm_stats_cols[0].write("Virtual Machine Stats")
    vm_stats_cols[1].metric("VCPU Reclamation (# VCPU)", vcpu_diff)
    vm_stats_cols[2].metric("VMem Reclamation (KB of VMem)", vmem_diff)
else:
    st.error("On-Prem Resize Data retrieval failed!")
case_data = get_instance_data()
answer, _ = handle_request("GET", case_data["url"]+"api/v3/targets", cookie=case_data["cookie"])
targets = { "Hypervisor": { }, "Cloud": {"AWS": {"Count": 0, "Billing": 0},"Azure": {"Count": 0, "Billing": 0}, "GCP": {"Count": 0, "Billing": 0}}, "APM": {}, "Cloud Native": {}}
# TODO: validate the logic for this mapping of accounts and Billing
for entry in answer:
    if entry["category"] == "Hypervisor":
         if targets["Hypervisor"].get(entry["type"], "") == "":
            targets["Hypervisor"][entry["type"]] = {"Count": 1 }
         else:
            targets["Hypervisor"][entry["type"]]["Count"] += 1
    elif entry["category"] == "Public Cloud":
        if any(substring in entry["type"] for substring in ["GCP", "AWS", "Azure"]):
            cloud_provider = entry["type"].split(" ")[0]
            if any(substring in entry["type"].lower() for substring in ["billing", "pricing" ]):
                targets["Cloud"][cloud_provider]["Billing"] += 1
            else:
                targets["Cloud"][cloud_provider]["Count"] += 1
    elif entry["category"] == "Applications and Databases":
        if targets["APM"].get(entry["type"], "") == "":
            targets["APM"][entry["type"]] = {"Count": 0 }
        else:
            targets["APM"][entry["type"]]["Count"] += 1
    elif entry["category"] == "Cloud Native":
        if targets["Cloud Native"].get(entry["type"], "") == "":
            targets["Cloud Native"][entry["type"]] = {"Count": 1 }
        else:
            targets["Cloud Native"][entry["type"]]["Count"] += 1
st.success("Target Data retrieval successful.")
print(str(targets))
target_stats = st.container()
target_category_count = len(targets.keys())
target_cols = target_stats.columns(2)
count = 0
line_count = 0
col_counter = 0

for key in targets.keys():
    if col_counter == 2:
        col_counter = 0
        line_count += 1
    target_cols[col_counter].subheader( key ) # Hypervisor, Cloud, APM
    subtarget_cols = target_cols[col_counter].columns(len(targets[key].keys())) # One column per Target Type
    subcategory_count = 0
    for entry in targets[key]: # Type of Cloud, HV, APM
        subtarget_cols[subcategory_count].text(entry,  help= entry)
        for value in targets[key][entry].keys():
            subtarget_cols[subcategory_count].metric(value, targets[key][entry][value])
        subcategory_count += 1
    count += 1
    col_counter += 1


