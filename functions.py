import requests
import urllib3
import json
import configparser
import os
from streamlit_extras.switch_page_button import switch_page
import re
import streamlit as st
import time
from io import StringIO
import threading
from streamlit.runtime.scriptrunner import add_script_run_ctx
urllib3.disable_warnings()

# Global configuration
api_path = "/api/v3/"
cursor_steps = 100
#pages_dir = os.path.dirname(os.path.abspath(__file__))
#config_path = os.path.join(pages_dir, os.pardir)
#config_file = os.path.join(os.path.abspath(config_path), "config", 'config.ini')
config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", 'config.ini')

# Read the config file
def get_instance_from_config():
    instances = {}
    config = configparser.ConfigParser()
    config.read(config_file)
    sections = config.sections()
    for instance in sections:
        instances[instance] = {"username": config[instance]['username'], "password": config[instance]['password'], "address": config[instance]['address'], "ssh-address": config[instance]['ssh-address'], "ssh-password":config[instance]['ssh-password']}
        if config[instance].get("kubeconfig", "") != "":
            instances[instance]["kubeconfig"] = config[instance]["kubeconfig"].replace(",","\n")
            instances[instance]["namespace"] = config[instance]["namespace"]
    return instances

def check_instance_state():
    if st.session_state.get("instancename", "n/a") == "n/a":
        st.write("# Please connect to an instance before trying to upload Topologies !")
        time.sleep(2)
        switch_page("Home")

# Reset step in session_state
def reset_step():
    if 'step' in st.session_state:
        st.session_state['step'] = "n/a"

# Remove a section given in argument (Turbonomic Instance)
def delete_instance_from_config(section):
    instances = get_instance_from_config()
    config = configparser.ConfigParser()
    config.read(config_file)
    bool_section_removed = config.remove_section(section)
    with open(config_file, 'w+') as config_to_update:
        config.write(config_to_update)
    return bool_section_removed

# Add a section given in argument with the given values (Turbonomic Instance)
# Returns the code (0 if OK) and the message of the error if any ("OK" if no error)
def add_instance_in_config(name, username, password, address, ssh_password, ssh_address, is_k8s):
    error_status = 0
    error_message = "OK"
    config = configparser.ConfigParser()
    config.read(config_file)
   # pattern_address = re.compile("^https\:\/\/([a-zA-Z0-9\.]+|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})$")
   # if pattern_address.match(address):
    try:
        bool_section_added = config.add_section(name)
        bool_username_added = config.set(name, 'username', username)
        bool_password_added = config.set(name, 'password', password)
        bool_address_added = config.set(name, 'address', address)
        bool_ssh_password_added = config.set(name, 'ssh-password', ssh_password)
        bool_ssh_address_added = config.set(name, 'ssh-address', ssh_address)
        if is_k8s:
            config.set(name, 'namespace', st.session_state.instance_manager_namespace)
            stringio = StringIO(st.session_state.instance_manager_kubeconfig.getvalue().decode("utf-8"))
            kubeconfig_string = stringio.read()
            config.set(name, 'kubeconfig', kubeconfig_string.replace("\n",","))
    except configparser.DuplicateSectionError as eduplicate:
        error_status = 1
        error_message = "Name already exists!"
    with open(config_file, 'w+') as config_to_update:
        config.write(config_to_update)
# else:
   #     error_status = 2
   #     error_message = "Invalid Turbonomic server address. It should follow the format: \"https://<server_name>\" or \"https://<ip_address>\""
    return error_status, error_message

# Update a section given in argument with the given values (Turbonomic Instance)
def update_instance_in_config(name, username, password, address, ssh_password, ssh_address, is_k8s):
    error_status = 0
    error_message = "OK"
    config = configparser.ConfigParser()
    config.read(config_file)
    #pattern_address = re.compile("^https\:\/\/([a-zA-Z0-9\.]+|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})$") # TODO: Amend this - With techzone etc we are working with subdomains...
    #if pattern_address.match(address):
    try:
        bool_username_updated = config.set(name, 'username', username)
        bool_password_updated = config.set(name, 'password', password)
        bool_address_updated = config.set(name, 'address', address)
        bool_ssh_password_updated = config.set(name, 'ssh-password', ssh_password)
        bool_ssh_address_updated = config.set(name, 'ssh-address', ssh_address)
        if is_k8s:
            config.set(name, 'namespace', st.session_state.instance_manager_namespace)
            if len(st.session_state.instance_manager_kubeconfig.getvalue()) > 0:
                stringio = StringIO(st.session_state.instance_manager_kubeconfig.getvalue().decode("utf-8"))
                kubeconfig_string = stringio.read()
                config.set(name, 'kubeconfig', kubeconfig_string.replace("\n", ","))

    except configparser.NoSectionError as eduplicate:
        error_status = 1
        error_message = "Section doesn't exist!"
    with open(config_file, 'w+') as config_to_update:
        config.write(config_to_update)
   # else:
   #     error_status = 2
   #     error_message = "Invalid Turbonomic server address. It should follow the format: \"https://<server_name>\" or \"https://<ip_address>\""
    return error_status, error_message
# Authenticate a user with username and password credentials on the turboserver server
# Returns the status code and the authentication token if successful
def monitor_backend():
    print("Now started")
    last_check = int(time.time())
    while True:
        time.sleep(5)
        if st.session_state.get("monitor_running", False) == False:
            print(str(st.session_state))
            print("No business to be running, bye")
            break
        current_time = int(time.time())
        print("Checking if we should run : "+str(current_time - last_check))
        if current_time - last_check > 5: # every 2 minutes ? 
            res, error, msg = get_request( st.session_state.turboserver,st.session_state.authtoken, "admin/versions")
            print("Checked backend Status")
            if error == 0:
                last_check = int(time.time())
                print("Backend responded OK")
            else:
                st.session_state["monitor_running"] = False
                reset_session()
                print("Exiting: "+msg)
                break

def authenticate_user(username, password, turboserver):
    error_status = 0
    error_message = "OK"
    # Authentication of the user
    authentication_payload = {'username': username, 'password': password}
    print("Attaching Context and starting")
    #print(authentication_payload)
    try:
        r = requests.post(turboserver+api_path+'login', data = authentication_payload, verify=False)
        if (r.status_code == 200):
            r.encoding = 'JSON'
            # Below: Spawn thread to monitor Backend
            if st.session_state.get("monitor_running", False) == False:
                st.session_state["monitor_running"] = True
                t = threading.Thread(target=monitor_backend, args=())
                # Below is very unstable since its internal Streamlit API, subject to change..
                print("Attaching Context and starting")
                add_script_run_ctx(t)
                t.start()
            error_message = r.headers['Set-Cookie'].split(';')[0]
            error_status = 0
    except requests.exceptions.RequestException as e:
        error_status = 1
        error_message = "Authentication failed!"
    return error_status, error_message

# Run a GET Rest command and returns the resulting payload in json format
def get_request(turboserver, authtoken, endpoint):
    json_response = "n/a"
    error_status = 0
    error_message = "OK"
    headers = {'accept': 'application/json', 'Content-Type': 'application/json', 'cookie': authtoken}
    url = turboserver+api_path+endpoint
    try:
        r = requests.get(url, headers = headers, verify=False)
        if (r.status_code == 200):
            error_status = 0
            json_response = r.json()
    except requests.exceptions.RequestException as e:
        error_status = 1
        error_message = "GET request failed!"
    return json_response, error_status, error_message

def post_request(turboserver, authtoken, endpoint, payload):
    json_response = "n/a"
    error_status = 0
    error_message = "OK"
    headers = {'accept': 'application/json', 'Content-Type': 'application/json', 'cookie': authtoken}
    url = turboserver+api_path+endpoint
    try:
        r = requests.post(url, headers = headers, data=payload, verify=False)
        if (r.status_code == 200):
            error_status = 0
            json_response = r.json()
    except requests.exceptions.RequestException as e:
        error_status = 1
        error_message = "POST request failed!"
    return json_response, error_status, error_message

def populate_sidebar():
        
        st.sidebar.title("Connected Server Info")
        st.sidebar.write()
        if st.session_state.get('instancename','') == "":
            st.sidebar.write("No Instance connected")
        else:
            st.sidebar.write("Instance Name: " + st.session_state['instancename'])
            st.sidebar.write("URL: " + st.session_state['turboserver'])
            st.sidebar.write("SSH Address: " + st.session_state['ssh_address'])
            st.sidebar.write("Username: " + st.session_state['username'])
            st.sidebar.write("API Token: " + st.session_state['authtoken'])
            st.sidebar.write("Version: " + st.session_state['turboversion'])
            logout_button = st.sidebar.button("Logout", disabled=False if st.session_state.authtoken != "n/a" else True, on_click=reset_session)

            if logout_button:
                reset_session()
    
def set_connection_info(instance, turboserver, username, password, ssh_password, ssh_address, kubeconfig, namespace):
    st.session_state.instancename = instance
    st.session_state.turboserver = turboserver
    st.session_state.username = username
    st.session_state.password = password
    st.session_state.ssh_password = ssh_password
    st.session_state.ssh_address = ssh_address
    st.session_state.kubeconfig = kubeconfig
    st.session_state.namespace = namespace

def reset_connection_info():
    st.session_state.instancename = "n/a"
    st.session_state.turboserver = "n/a"
    st.session_state.username = "n/a"
    st.session_state.password = "n/a"
    st.session_state.ssh_password = "n/a"
    st.session_state.ssh_address = "n/a"
    st.session_state.kubeconfig = "n/a"
    st.session_state.namespace = "n/a"

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