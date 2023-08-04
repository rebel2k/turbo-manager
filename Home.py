import os
from functions import authenticate_user, get_request, get_instance_from_config, delete_instance_from_config
import streamlit as st

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

st.write("# Welcome to Turbonomic Topology Tool! 👋")

st.markdown(
    """
    Turbonomic Topology Tool is a custom tool created to help you manage your Turbonomic environments in PoVs.
    """
)

def set_connection_info(instance, turboserver, username, password):
    st.session_state.instancename = instance
    st.session_state.turboserver = turboserver
    st.session_state.username = username
    st.session_state.password = password

def reset_connection_info():
    st.session_state.instancename = "n/a"
    st.session_state.turboserver = "n/a"
    st.session_state.username = "n/a"
    st.session_state.password = "n/a"

def set_authtoken(username, password, turboserver):
    authstatus, authtoken = authenticate_user(username, password, turboserver)
    if authstatus == 0:
        st.session_state.authtoken = authtoken
    else:
        st.session_state.authtoken = "n/a"

def reset_authtoken():
    st.session_state.authtoken = "n/a"

def set_turboversion(version):
    st.session_state.turboversion = version

def reset_turboversion():
    st.session_state.turboversion = "n/a"

def reset_session():
    reset_connection_info()
    reset_authtoken()
    reset_turboversion()
    
with st.container():
    instance_list = get_instance_from_config()
    with st.container():
        st.title("Existing instances")
        col_left, col_right = st.columns(2)
        instance = col_left.selectbox("Chose an instance", instance_list.keys(), disabled=True if st.session_state.authtoken != "n/a" else False)
        turboserver = instance_list[instance]["address"]
        username = instance_list[instance]["username"]
        password = instance_list[instance]["password"]
        col_right.info("Address: "+turboserver+"  \n"+"Username: "+username)
        login_button = st.button("Login", disabled=True if st.session_state.authtoken != "n/a" else False, on_click=set_authtoken, args=(username, password, turboserver))
    if login_button:
        authstatus, authtoken = authenticate_user(username, password, turboserver)
        if (authstatus == 0):
            with st.container():
                #st.title("Results")
                st.success("Logged in")
                set_connection_info(instance, turboserver, username, password)
                set_authtoken(username, password, turboserver)
                response = get_request(turboserver, authtoken, "admin/versions")
                if (response):
                    st.success("Communication/REST API calls successful.")
                    set_turboversion(response["versionInfo"].split('\n')[0])
                else:
                    st.error("Communication/REST API calls successful failed!")
                    set_turboversion("n/a")
        else:
            with st.container():
                #st.title("Results")
                st.error("Login failed on instance "+instance)
                reset_authtoken()

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

st.sidebar.title("Connected Server Info")
st.sidebar.write()
st.sidebar.write("Instance Name: " + st.session_state['instancename'])
st.sidebar.write("URL: " + st.session_state['turboserver'])
st.sidebar.write("Username: " + st.session_state['username'])
st.sidebar.write("API Token: " + st.session_state['authtoken'])
st.sidebar.write("Version: " + st.session_state['turboversion'])
logout_button = st.sidebar.button("Logout", disabled=False if st.session_state.authtoken != "n/a" else True, on_click=reset_session)

if logout_button:
    reset_session()
    