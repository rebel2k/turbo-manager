import streamlit as st
from backend_functions import *
from functions import *
import paramiko
import scp 
import shutil
st.set_page_config(
    page_title="Topology Management",
    page_icon="🌍",
)

def upload_topology(topology_file, name, instance_data, persist):
    
    # First step: Unzip the file:

    if topology_file != None:
        st.write("Extracting to: "+name)
        with zipfile.ZipFile(topology_file, 'r') as zip_ref:
            zip_ref.extractall("known-topologies/"+name)
    # Second step
    prog.value = 10
    prog.text = "Extracted file"
    if instance_data["kubeconfig"] == "":
        ssh = createSSHClient(instance_data["ssh_address"], "turbo", instance_data["ssh_pw"])
        scpClient = scp.SCPClient(ssh.get_transport(), progress=progress)

        topology_name = get_names("known-topologies/"+name)
        # and then
        print("Copying Group File: ")
        scpClient.put("./"+topology_name["groupfile"], remote_path='/tmp/group.zip')
        prog.progress(value = 20, text = "Uploaded groupfile")
        print("")
        print("Copying Topology File: ")
        scpClient.put("./"+topology_name["topologyfile"], remote_path='/tmp/topology.zip')
        prog.progress(value = 30, text = "Uploaded topologyfile")
        print("")
        res = purge_topology(ssh)
        prog.progress(text = "Purged old topology",value = 50)
        if res == False:
            print("Issues when Purging... cowardly exiting script now for you to debug")
            exit()
        print("Purged old Topology, now loading new Topology...")
        res = load_topology(ssh)
        prog.progress(text = "Topology loaded",value = 90)
        if res == False:
            print("Issues when Loading Group... cowardly exiting script now for you to debug")
            exit()
        print("Loaded Topology, now cleaning up")
        stdint, stdout, stderr = ssh.exec_command("rm -f /tmp/group.zip")
        if stdout.channel.recv_exit_status() != 0:
            print ("Encountered Errors: "+stderr.read().decode('ascii'))
            exit()
        stdint, stdout, stderr = ssh.exec_command("rm -f /tmp/topology.zip")
        if stdout.channel.recv_exit_status() != 0:
            print ("Encountered Errors: "+stderr.read().decode('ascii'))
            exit()
        prog.progress(value = 100,text ="All Done")
    else:

        topology_name = get_names("known-topologies/"+name)
        namespace = "turbo"
        if instance_data.get("namespace","") !="":
            namespace = instance_data["namespace"]
        load_topology_cluster(instance_data["kubeconfig"], topology_name, prog,namespace)
    if not persist:
        shutil.rmtree("known-topologies/"+name)

def createSSHClient(server, user, password, port=22):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(server, port, user, password)
    return client
def get_instance_data():
    turboserver = st.session_state.turboserver
    username = st.session_state.username
    password = st.session_state.password
    authtoken = st.session_state.authtoken
    turboversion = st.session_state.turboversion
    ssh_url = st.session_state.get("ssh_address")
    kubeconfig = st.session_state.get("kubeconfig")
    namespace = st.session_state.get("namespace")
    if ssh_url == "":
        ssh_url = turboserver.replace("https://","").replace("/")
    ssh_password = st.session_state.ssh_password
    if ssh_password == "":
        ssh_password = st.text_input("SSH-Password", type="password")
    return {
        "cookie": authtoken,
        "url": "https://"+turboserver.replace("https://","").replace("/","")+"/",
        "scope": "n/a",
        "ssh_pw": ssh_password,
        "ssh_address": ssh_url,
        "entity_type": "n/a",
        "kubeconfig": kubeconfig,
        "namespace": namespace
    }


check_instance_state()
st.write("# Upload Topologies to Instance")
prog = st.progress(0, text="Waiting for File")
topologies = get_folders_in_folder("known-topologies")
topologies.append("Upload new")
selectbox = ""
select = st.selectbox("Known Topologies", topologies)
disabled = True
topology_file = ""
name = ""
persist = False
st.text(select)
if select == "Upload new":
    disabled = False
else:  
    disabled = True
if disabled == False:
    topology_file = st.file_uploader("Upload your topology file", disabled=disabled)
    name = st.text_input("Topology Name",placeholder="Customer_XX")
    persist = st.checkbox("Save for further Use", value=True)
run = st.button("Lets go" )
if run:
    instance_data = get_instance_data()
    if select != "Upload new":
        name = select
        upload_topology(None, name, instance_data, persist)
    if topology_file == "":
        topology_file = select
    if name =="":
        name = select
    upload_topology(topology_file, name, instance_data, persist)
populate_sidebar()