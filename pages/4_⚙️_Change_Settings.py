import streamlit as st
from backend_functions import *
from functions import *

st.set_page_config(
    page_title="Change Settings",
    page_icon="⚙️",
)

@st.cache_resource
def get_policies(case_data):
    policy_list = get_policy_list(case_data)
    vm_policies = get_policy_parameters(policy_list, "marketsettingsmanager","VirtualMachine" )
    container_policies =  get_policy_parameters(policy_list, "marketsettingsmanager","ContainerSpec" )
    storage_policies =  get_policy_parameters(policy_list, "marketsettingsmanager","Storage" )
    policies = {
        "VirtualMachine" : vm_policies,
        "ContainerSpec": container_policies,
        "Storage": storage_policies
    }
    return policies
def test_func():
    if st.session_state['button_disabled']  is True:
        st.session_state['button_disabled']  = False

@st.cache_resource
def set_initial():
    print("Setting initial")
    st.session_state['button_disabled'] = True
def get_instance_data():
    turboserver = st.session_state.turboserver
    username = st.session_state.username
    password = st.session_state.password
    authtoken = st.session_state.authtoken
    turboversion = st.session_state.turboversion
    ssh_url = st.session_state.ssh_address
    if ssh_url == "":
        ssh_url = turboserver.replace("https://","").replace("/")
    ssh_password = st.session_state.ssh_password
    if ssh_password == "":
        ssh_password = st.text_input("SSH-Password", type="password")
    return {
        "cookie": authtoken,
        "url": "https://"+turboserver.replace("https://","").replace("/","")+"/",
        "scope": "n/a",
        "ssh-pw": ssh_password,
        "ssh-url": ssh_url,
        "entity_type": "n/a",
    }
check_instance_state()
populate_sidebar()
set_initial()
DEFAULT_ROR = 3
    # Get Values for Environment
case_data = get_instance_data()
policies = get_policies(case_data)
measures = {
    "Aggressiveness": [90.0, 95.0,99.0, 99.1, 99.5,99.9, 100.0 ],
    "Min Observation Period": [0.0, 1.0, 3.0, 7.0], 
    "Max Observation Period": [90.0,30.0,7.0],
   "Rate of Resize": [1.0,2.0,3.0]
}
values = {
}
objects = ["VirtualMachine", "ContainerSpec", "Storage"] # These are our Headlines, then we have a line for every entry below
boxes = []
for entry in objects:
    values[entry] = {}
policy_names = ["Rate of Resize", "Min Observation Period","Max Observation Period", "Aggressiveness"]
for single_object in objects:
    st.write("## "+single_object)
    for name in policy_names:
        if name in policies[single_object].keys():
            sb = st.selectbox(name, options=measures[name], index=measures[name].index(float(policies[single_object][name])), key=single_object.replace(" ","_")+name.replace(" ","_"),  on_change=test_func)
            values[single_object][name] = {"Value": sb, "Key": single_object.replace(" ","_")+name.replace(" ","_")}
            boxes.append({"Value": float(policies[single_object][name]), "Key": single_object.replace(" ","_")+name.replace(" ","_")})
btn = st.button("Sync Changes", type="secondary", disabled=st.session_state['button_disabled'] )
btn2 = st.button("Reset", type="primary", disabled=st.session_state["button_disabled"])
if btn: 
    print("Would sync now")
if btn2: 
    print("Resetting")
    st.cache_resource.clear()
    for entry in boxes:
        st.session_state[entry["Key"]] =  entry["Value"]
    st.experimental_rerun()

