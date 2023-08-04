import os
from functions import get_request, post_request
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
