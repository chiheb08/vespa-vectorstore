import os
import textwrap

import requests
import streamlit as st


VESPA_URL = os.getenv("VESPA_URL", "http://localhost:8080").rstrip("/")
NAMESPACE = "demo"
DOCTYPE = "item"


def vespa_doc_url(docid: str) -> str:
    return f"{VESPA_URL}/document/v1/{NAMESPACE}/{DOCTYPE}/docid/{docid}"


def vespa_search_url() -> str:
    return f"{VESPA_URL}/search/"


st.set_page_config(page_title="Beginner Vespa CRUD UI", layout="centered")

st.title("Beginner Vespa CRUD UI")
st.caption(f"Talking to Vespa at: `{VESPA_URL}`")

st.divider()

st.subheader("1) Add / Update an item")
with st.form("put_form"):
    docid = st.text_input("Document id", value="1")
    title = st.text_input("Title", value="Hello Vespa")
    body = st.text_area(
        "Body",
        value="This is a beginner CRUD example stored in Vespa.",
        height=120,
    )
    tags_str = st.text_input("Tags (comma-separated)", value="tutorial, beginner")
    submitted = st.form_submit_button("Save (PUT)")

if submitted:
    tags = [t.strip() for t in tags_str.split(",") if t.strip()]
    payload = {"fields": {"title": title, "body": body, "tags": tags}}
    # Use POST for create/upsert. Some Vespa versions treat PUT as "field update" requiring {assign: ...}.
    r = requests.post(vespa_doc_url(docid), json=payload, timeout=10)
    st.code(r.text)
    st.success(f"Saved docid={docid}")

st.divider()

st.subheader("2) Search")
q = st.text_input("Search query", value="vespa")
hits = st.slider("Hits", min_value=1, max_value=20, value=5)

if st.button("Search"):
    params = {
        "yql": "select * from sources item where userInput(@q);",
        "q": q,
        "hits": hits,
    }
    r = requests.get(vespa_search_url(), params=params, timeout=10)
    data = r.json()
    children = data.get("root", {}).get("children", []) or []

    st.write(f"Results: {len(children)}")
    for hit in children:
        fields = hit.get("fields", {})
        st.markdown(f"**id**: `{hit.get('id','')}`")
        st.write(f"**title**: {fields.get('title','')}")
        st.write(textwrap.shorten(fields.get("body", ""), width=240, placeholder="..."))
        st.write(f"**tags**: {fields.get('tags', [])}")
        st.caption(f"relevance: {hit.get('relevance')}")
        st.divider()

st.divider()

st.subheader("3) List all items (simple)")
if st.button("List"):
    params = {
        "yql": "select * from sources item where true;",
        "hits": 20,
    }
    r = requests.get(vespa_search_url(), params=params, timeout=10)
    st.json(r.json())

st.divider()

st.subheader("4) Delete by id")
del_id = st.text_input("Document id to delete", value="1", key="del_id")
if st.button("Delete (DELETE)"):
    r = requests.delete(vespa_doc_url(del_id), timeout=10)
    st.code(r.text)
    st.success(f"Deleted docid={del_id} (if it existed)")

st.caption(
    "Tip: if this UI shows errors, check `docker logs beginner_vespa` and `docker logs beginner_vespa_deployer`."
)


