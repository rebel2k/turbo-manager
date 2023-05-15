import streamlit as st

st.set_page_config(
    page_title="Topology Management",
    page_icon="🌍",
)

st.write("# Page for loading and managing topologies!")

topology_file = st.file_uploader("Upload your topology file")