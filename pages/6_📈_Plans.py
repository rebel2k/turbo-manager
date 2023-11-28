import streamlit as st
from backend_functions import *
from functions import *
from os import listdir
from os.path import isfile, join

st.set_page_config(
    page_title="Reporting",
    page_icon="📈",
)

def get_list_fragment_for_plan_actions(case_data, cursor, limit, q, query):
    answer, headers = handle_request("GET",case_data["url"]+"api/v3/markets/"+query["Uuid"]+"/actions?cursor="+str(cursor)+"&limit="+str(limit)+"&order_by=NAME&ascending=true",case_data["cookie"])
    res = []
    for entry in answer:
        res.append(entry)
    q.put(res)
def gather_actions(case_data, uuid):
    action_list = get_generic_list(case_data, "api/v3/markets/"+uuid+"/actions", get_list_fragment_for_plan_actions, {"Uuid": uuid})
    action_count = 0
    res = {}
    for entry in action_list:
        if entry["actionType"] == "SUSPEND" and entry["target"]["className"] == "VirtualMachine":
                if res.get("Saved Clusternodes","") == "":
                    res["Saved Clusternodes"] = 1
                else:
                    res["Saved Clusternodes"] += 1
        if entry["actionType"] == "PROVISION" and entry["target"]["className"] == "VirtualMachine":
                if res.get("Saved Clusternodes","") == "":
                    res["Saved Clusternodes"] = -1
                else:
                    res["Saved Clusternodes"] -= 1
        if entry["actionType"] == "RESIZE" and  entry["target"]["className"] in ["WorkloadController", "Container", "ContainerPod"]:
            if entry.get("compoundActions", "") == "":
                action_count += 1
                value = float(entry["newValue"]) - float(entry["currentValue"]) 
                action_type = ""
                if "VMem" in entry["details"]:
                    action_type = "VMem"
                    value = value / 1024
                else:
                    action_type = "VCPU"
                if "Request" in entry["details"]:
                    action_type += "Request"
                else:
                    action_type += "Limit"
                if res.get("Action_"+action_type, "") == "":
                    res["Action_"+action_type] = value
                else:
                    res["Action_"+action_type] += value
            else:
                for action in entry["compoundActions"]:
                    action_count += 1
                    value = float(action["newValue"]) - float(action["currentValue"]) 
                    action_type = ""
                    if "VMem" in action["details"]:
                        action_type = "VMem"
                        value = value / 1024
                    else:
                        action_type = "VCPU"
                    if "Request" in action["details"]:
                        action_type += "Request"
                    else:
                        action_type += "Limit"
                    if res.get("Action_"+action_type, "") == "":
                        res["Action_"+action_type] = value
                    else:
                        res["Action_"+action_type] += value
        if entry["actionType"] == "SUSPEND" and entry["target"]["className"] == "PhysicalMachine":
                if res.get("Saved  Nodes","") == "":
                    res["Saved Nodes"] = 1
                else:
                    res["Saved Nodes"] += 1
        if entry["actionType"] == "PROVISION" and entry["target"]["className"] == "PhysicalMachine":
                if res.get("Saved Nodes","") == "":
                    res["Saved Nodes"] = -1
                else:
                    res["Saved Nodes"] -= 1
        if entry["actionType"] == "RESIZE" and entry["target"]["className"] == "VirtualMachine":
            action_count += 1
            value = float(entry["newValue"]) - float(entry["currentValue"])
            action_type = ""
            if "VCPU" in entry["details"]:
                action_type = "VCPU"
            else: 
                action_type ="VMem"
                value = value / (1024*1024)
            if res.get("Action_"+action_type, "") == "":
                res["Action_"+action_type] = value
            else:
                res["Action_"+action_type] += value
    if res.get("ActionCount","") == "":
        res["ActionCount"] =  action_count
    else: 
        res["ActionCount"] += action_count
    return res

    

def get_list_fragment_for_actions_plan(case_data, cursor, limit, q, query):
    answer, headers = handle_request("GET",case_data["url"]+"api/v3/markets/"+query["Uuid"]+"/actions?cursor="+str(cursor)+"&limit="+str(limit)+"&order_by=NAME&ascending=true",case_data["cookie"])
    res = []
    for entry in answer:
        res.append(entry)
    q.put(res)

check_instance_state()
populate_sidebar()
st.title("Clusterwise Plan Simulation")
st.text("Select Category for which to execute Optimize Plans: ")
entities = {"ContainerClusters": "ContainerPlatformCluster", "OnPremise Cluster":"Cluster"}
entity_select = st.selectbox("Entity Type", entities.keys())
st.text("Select Plan type:")
possible_plans = {}
option_list = []
plans = [f for f in listdir("known-plans") if isfile(join("known-plans/", f) )]
for plan in plans:
    f = open("known-plans/"+plan)
    data = json.load(f)
    if entity_select == "OnPremise Cluster" and data["planData"]["type"] == "OPTIMIZE_ONPREM":
        # Select those for the correct environment
        option_list.append(data["description"])
        possible_plans[data["description"]] = data["planData"]
    elif entity_select == "ContainerClusters" and data["planData"]["type"] == "OPTIMIZE_CONTAINER_CLUSTER":
        option_list.append(data["description"])
        possible_plans[data["description"]] = data["planData"]
        # Container Plans
options = st.multiselect("Select Plans to run", option_list, [])
plans_to_run = []
for option in options:
    plans_to_run.append({"Plan": possible_plans[option], "Description": option})
# Next get all entities we could feasibly run on 
case_data = get_instance_data()
entity_list = get_generic_list(case_data, "api/v3/search?types="+entities[entity_select], get_list_fragment_entity, {"Type": entities[entity_select]})
entity_names = [entity["Name"] for entity in entity_list ]
entities = st.multiselect("Select "+entity_select+" to run Plan on: ", entity_names, entity_names)
# now we need to start the plans for any entity.
# -> for each entity, prepare a request of plans_to_run with adapted scope and displayName, fire this off, capture the scenario UUID .
btn = st.button("Calculate Plans")
watch_list = []
if btn:
    results = []
    with st.spinner():
        for entity in entities:
            for plan in plans_to_run:
                entity_uuid = ""
                entity_name = ""
                for entry in entity_list:
                    if entry["Name"] == entity:
                        entity_uuid = entry["Uuid"]
                        entity_name = entry["Name"]
                plan["Plan"]["scope"][0]["uuid"] = entity_uuid
                plan["Plan"]["displayName"] = "AUTO_"+plan["Description"]+"_"+entity_name
                answer, _ =  handle_request("POST", case_data["url"]+"api/v3/scenarios", data=json.dumps(plan["Plan"]), cookie=case_data["cookie"])
                plan_data = {"Name" : answer["displayName"], "ScenarioUuid": answer["uuid"]}
                answer, _ =  handle_request("POST", case_data["url"]+"api/v3/markets/777777/scenarios/"+answer["uuid"], data="", cookie=case_data["cookie"])
                plan_data["PlanUuid"] = answer["uuid"]
                watch_list.append(plan_data)
        while True:
            if len(watch_list) == 0:
                break
            for entry in watch_list:
                answer, _ =  handle_request("GET", case_data["url"]+"api/v3/markets/"+entry["PlanUuid"], cookie=case_data["cookie"])
                if answer["state"] == "SUCCEEDED":
                    res = gather_actions(case_data, entry["PlanUuid"])
                    res["Plan Name"] = entry["Name"]
                    res["Link"] = case_data["url"]+"app/index.html#/view/main/plans/"+entry["PlanUuid"]
                    results.append(res)
                    watch_list.remove(entry)
                    
            time.sleep(0.1)            
    st.dataframe(results)