import os
from functions import *
import streamlit as st
import time
from streamlit_extras.switch_page_button import switch_page

st.set_page_config(
    page_title="Home",
    page_icon="☣️",
)

# Session initialization
if 'instancename' not in st.session_state:
    st.session_state['instancename'] = "n/a"
if 'turboserver' not in st.session_state:
    st.session_state['turboserver'] = "n/a"
if 'username' not in st.session_state:
    st.session_state['username'] = "n/a"
if 'password' not in st.session_state:
    st.session_state['password'] = "n/a"
if 'authtoken' not in st.session_state:
    st.session_state['authtoken'] = "n/a"
if 'turboversion' not in st.session_state:
    st.session_state['turboversion'] = "n/a"
if 'ssh_address' not in st.session_state:
    st.session_state['ssh_address'] = "n/a"
if 'ssh_password' not in st.session_state:
    st.session_state['ssh_password'] = "n/a"

instance_list = get_instance_from_config()
if instance_list == {}:
    st.write("Please add an Instance first, forwarding to the Instance Manager now...")
    time.sleep(2)
    switch_page("Instance Manager")
st.write("# Welcome to Turbonomic Topology Tool! 👋")

st.markdown(
    """
    Turbonomic Topology Tool is a custom tool created to help you manage your Turbonomic environments in PoVs.
    """
)

    
with st.container():
        with st.container():
            st.title("Existing instances")
            col_left, col_right = st.columns(2)
            instance = col_left.selectbox("Chose an instance", instance_list.keys(), disabled=True if st.session_state.authtoken != "n/a" else False)
            turboserver = instance_list[instance]["address"]
            username = instance_list[instance]["username"]
            password = instance_list[instance]["password"]
            ssh_password = instance_list[instance]["ssh-password"]
            ssh_address = instance_list[instance]["ssh-address"]
            col_right.info("Address: "+turboserver+"  \n"+"Username: "+username)
            login_button = st.button("Login", disabled=True if st.session_state.authtoken != "n/a" else False, on_click=set_authtoken, args=(username, password, turboserver))
        if login_button:
            authstatus, authtoken = authenticate_user(username, password, turboserver)
            if (authstatus == 0):
                with st.container():
                    #st.title("Results")
                    st.success("Logged in")
                    set_connection_info(instance, turboserver, username, password, ssh_address=ssh_address, ssh_password=ssh_password)
                    set_authtoken(username, password, turboserver)
                    response, status, message = get_request(turboserver, authtoken, "admin/versions")
                    if (status == 0):
                        st.success("Communication/REST API calls successful.")
                        set_turboversion(response["versionInfo"].split('\n')[0])
                    else:
                        st.error("Communication/REST API calls successful failed!")
                        st.error(message)
                        set_turboversion("n/a")
            else:
                with st.container():
                    #st.title("Results")
                    st.error("Login failed on instance "+instance)
                    reset_authtoken()
                    reset_turboversion()

# container1 = st.container()
# container1.title("Currently logged on")
# turboserver = st.session_state['turboserver']
# username = st.session_state['username']
# password = st.session_state['password']
# authtoken = st.session_state['authtoken']
# container1.text(turboserver)
# container1.text(username)
# container1.text(password)
# container1.text(authtoken)
populate_sidebar()