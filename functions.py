import requests
import urllib3
import json
import configparser
import os
import re

urllib3.disable_warnings()

# Global configuration
api_path = "/api/v3/"
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
        instances[instance] = {"username": config[instance]['username'], "password": config[instance]['password'], "address": config[instance]['address']}
    return instances

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
def add_instance_in_config(name, username, password, address):
    error_status = 0
    error_message = "OK"
    config = configparser.ConfigParser()
    config.read(config_file)
    pattern_address = re.compile("^https\:\/\/([a-zA-Z0-9\.]+|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})$")
    if pattern_address.match(address):
        try:
            bool_section_added = config.add_section(name)
            bool_username_added = config.set(name, 'username', username)
            bool_password_added = config.set(name, 'password', password)
            bool_address_added = config.set(name, 'address', address)
        except configparser.DuplicateSectionError as eduplicate:
            error_status = 1
            error_message = "Name already exists!"
        with open(config_file, 'w+') as config_to_update:
            config.write(config_to_update)
    else:
        error_status = 2
        error_message = "Invalid Turbonomic server address. It should follow the format: \"https://<server_name>\" or \"https://<ip_address>\""
    return error_status, error_message

# Update a section given in argument with the given values (Turbonomic Instance)
def update_instance_in_config(name, username, password, address):
    error_status = 0
    error_message = "OK"
    config = configparser.ConfigParser()
    config.read(config_file)
    pattern_address = re.compile("^https\:\/\/([a-zA-Z0-9\.]+|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})$")
    if pattern_address.match(address):
        try:
            bool_username_updated = config.set(name, 'username', username)
            bool_password_updated = config.set(name, 'password', password)
            bool_address_updated = config.set(name, 'address', address)
        except configparser.NoSectionError as eduplicate:
            error_status = 1
            error_message = "Section doesn't exist!"
        with open(config_file, 'w+') as config_to_update:
            config.write(config_to_update)
    else:
        error_status = 2
        error_message = "Invalid Turbonomic server address. It should follow the format: \"https://<server_name>\" or \"https://<ip_address>\""
    return error_status, error_message

# Authenticate a user with username and password credentials on the turboserver server
# Returns the status code and the authentication token if successful
def authenticate_user(username, password, turboserver):
    error_status = 0
    error_message = "OK"
    # Authentication of the user
    authentication_payload = {'username': username, 'password': password}
    #print(authentication_payload)
    try:
        r = requests.post(turboserver+api_path+'login', data = authentication_payload, verify=False)
        if (r.status_code == 200):
            r.encoding = 'JSON'
            error_message = r.headers['Set-Cookie'].split(';')[0]
            error_status = 0
    except requests.exceptions.RequestException as e:
        error_status = 1
        error_message = "Authentication failed!"
    return error_status, error_message

# Run a GET Rest command and returns the resulting payload in json format
def get_request(turboserver, authtoken, endpoint):
    # Get VCPU stats of the selected VM and store them
    stats_list = []
    headers = {'accept': 'application/json', 'Content-Type': 'application/json', 'cookie': authtoken}
    url = turboserver+api_path+endpoint
    r = requests.get(url, headers = headers, verify=False)
    # print("Payload: "+str(payload))
    # print("Status code: "+str(r.status_code))
    # print("Content: "+r.text)
    json_stats = r.json()
    #print(stats_list)
    return json_stats