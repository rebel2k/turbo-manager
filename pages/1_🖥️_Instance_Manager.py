
from functions import *
import streamlit as st

# Streamlit initialization
st.set_page_config(
    page_title="Instance Manager",
    page_icon="🖥️",
)

# Initialize session
if 'step' not in st.session_state:
    st.session_state.step = "n/a"

# UI
with st.container():
    instance_list = get_instance_from_config()
    with st.container():
        st.title("Registered instances")
        col_left, col_right = st.columns(2)
        if len(instance_list) != 0:
            instance = col_left.selectbox("Chose an instance", instance_list.keys(), on_change=reset_step)
            turboserver = instance_list[instance]["address"]
            username = instance_list[instance]["username"]
            password = instance_list[instance]["password"]
            ssh_password = instance_list[instance]["ssh-password"]
            ssh_address = instance_list[instance]["ssh-address"]
            col_right.info("Address: "+turboserver+"  \n"+"Username: "+username)
        else:
            st.info("There is no registered instance yet. You can add one by clicking the \"Add\" button.")
    with st.container():
        col_new, col_update, col_delete = st.columns(3)
    add_button = col_new.button("Add", use_container_width=True)
    if len(instance_list) != 0 and instance != st.session_state.instancename:
        update_button = col_update.button("Update", use_container_width=True)
        delete_button = col_delete.button("Delete", use_container_width=True)
    else:
        update_button = col_update.button("Update", use_container_width=True, disabled=True)
        delete_button = col_delete.button("Delete", use_container_width=True, disabled=True)
    if delete_button:
        if (delete_instance_from_config(instance)):
            st.success("Instance deleted")
            st.experimental_rerun()
        else:
            st.error("Instance deletion failed")
    if update_button:
        st.session_state.step = "update_clicked"
        st.experimental_rerun()
    if st.session_state.step == "update_clicked":
        update_form = st.form("update_form")
        st.session_state.instance_manager_name = update_form.text_input('Name', instance, disabled = True)
        st.session_state.instance_manager_username = update_form.text_input('Username', instance_list[instance]["username"])
        st.session_state.instance_manager_password = update_form.text_input('Password', instance_list[instance]["password"], type="password")
        st.session_state.instance_manager_ssh_password = update_form.text_input('SSH-Password', instance_list[instance]["ssh-password"], type="password")
        st.session_state.instance_manager_address = update_form.text_input('Server Address', instance_list[instance]["address"])
        st.session_state.instance_manager_ssh_address = update_form.text_input('Server SSH Address', instance_list[instance]["ssh-address"])
        st.session_state.instance_manager_is_k8s = update_form.checkbox('This is a ROKS Deployment')
        st.session_state.instance_manager_namespace = update_form.text_input('Kubernetes Namespace', instance_list[instance].get("namespace","turbo") ) #  TODO: Hide this if checkbox "This is a ROKS DEployment" is not checked
        st.session_state.instance_manager_kubeconfig = update_form.file_uploader("Upload your kubernetes Config") #  TODO: Hide this if checkbox "This is a ROKS DEployment" is not checked
        # Every form must have a submit button.
        col_left, col_right = update_form.columns(2)
        if col_left.form_submit_button("Save", use_container_width=True):
            st.session_state.step = "update_save_clicked"
        elif col_right.form_submit_button("Cancel", use_container_width=True):
            st.session_state.step = "n/a"
            st.experimental_rerun()
    if st.session_state.step == "update_save_clicked": # if we are there, we know the button "save" in the "add" form has been pressed
        st.session_state.step = "n/a"
        error_status, error_message = update_instance_in_config(st.session_state.instance_manager_name, st.session_state.instance_manager_username, st.session_state.instance_manager_password, st.session_state.instance_manager_address,st.session_state.instance_manager_ssh_password, st.session_state.instance_manager_ssh_address,  st.session_state.instance_manager_is_k8s)
        if (error_status == 0):
            st.success("Instance updated")
            st.experimental_rerun()
        else:
            st.error(error_message)
            st.session_state.step = "update_clicked" # to be able to fix the issue and retry
    if add_button:
        st.session_state.step = "add_clicked"
        st.experimental_rerun()
    if st.session_state.step == "add_clicked":
        add_form = st.form("add_form")
        st.session_state.instance_manager_name = add_form.text_input('Name')
        st.session_state.instance_manager_username = add_form.text_input('Username')
        st.session_state.instance_manager_password = add_form.text_input('Password', type="password")
        st.session_state.instance_manager_address = add_form.text_input('Server Address', "https://")
        st.session_state.instance_manager_ssh_password = add_form.text_input('SSH Password', type="password")
        st.session_state.instance_manager_ssh_address = add_form.text_input('Server SSH Address', "IP Address or hostname")
        st.session_state.instance_manager_is_k8s = add_form.checkbox('This is a ROKS Deployment')
        st.session_state.instance_manager_namespace = add_form.text_input('Kubernetes Namespace', "turbo")#  TODO: Hide this if checkbox "This is a ROKS DEployment" is not checked
        st.session_state.instance_manager_kubeconfig = add_form.file_uploader("Upload your kubernetes Config")#  TODO: Hide this if checkbox "This is a ROKS DEployment" is not checked
        # Every form must have a submit button.
        #submit_add = add_form.form_submit_button("Save", on_click=save_values_in_session_state, args=(name_new, username_new, password_new, address_new))
        col_left, col_right = add_form.columns(2)
        if col_left.form_submit_button("Save", use_container_width=True):
            st.session_state.step = "add_save_clicked"
        elif col_right.form_submit_button("Cancel", use_container_width=True):
            st.session_state.step = "n/a"
            st.experimental_rerun()
    if st.session_state.step == "add_save_clicked": # if we are there, we know the button "save" in the "add" form has been pressed
        st.session_state.step = "n/a"
        error_status, error_message = add_instance_in_config(st.session_state.instance_manager_name, st.session_state.instance_manager_username, st.session_state.instance_manager_password, st.session_state.instance_manager_address, st.session_state.instance_manager_ssh_password, st.session_state.instance_manager_ssh_address, st.session_state.instance_manager_is_k8s )
        if (error_status == 0):
            st.success("Instance added")
            st.experimental_rerun()
        else:
            st.error(error_message)
            st.session_state.step = "add_clicked" # to be able to fix the issue and retry
populate_sidebar()