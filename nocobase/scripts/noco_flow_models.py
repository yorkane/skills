#!/usr/bin/env python3
import sys
import json
import os
import urllib.parse
sys.path.insert(0, os.path.dirname(__file__))
from noco_api import api, init_api, output, read_args, run_main

def do_create(args):
    model_uid = args.get("uid")
    use = args.get("use")
    props = args.get("props")
    parent_id = args.get("parentId")
    sub_key = args.get("subKey")
    sub_type = args.get("subType")
    sort_index = args.get("sortIndex")
    body = {"use": use}
    if model_uid:
        body["uid"] = model_uid
    if props:
        body["props"] = props
    if parent_id:
        body["parentId"] = parent_id
    if sub_key:
        body["subKey"] = sub_key
    if sub_type:
        body["subType"] = sub_type
    if sort_index is not None:
        body["sortIndex"] = sort_index
    res = api("/flowModels:create", method="POST", body=body)
    if res.get("error"):
        output(res)
        return
    print(json.dumps(res.get("data"), ensure_ascii=False, indent=2))

def do_attach(args):
    model_uid = args["uid"]
    parent_id = args["parentId"]
    sub_key = args["subKey"]
    sub_type = args.get("subType")
    qp = urllib.parse.urlencode({"uid": model_uid, "parentId": parent_id, "subKey": sub_key})
    if sub_type:
        qp += f"&subType={sub_type}"
    res = api("/flowModels:attach", method="POST", query=qp)
    if res.get("error"):
        output(res)
        return
    print(f"Model {model_uid} attached to {parent_id} under {sub_key}.")

def do_find(args):
    params = urllib.parse.urlencode({k: v for k, v in [("uid", args.get("uid")), ("parentId", args.get("parentId")), ("subKey", args.get("subKey"))] if v})
    res = api("/flowModels:findOne", query=params)
    if res.get("error"):
        output(res)
        return
    print(json.dumps(res.get("data"), ensure_ascii=False, indent=2))

def do_list(args):
    params = urllib.parse.urlencode({"parentId": args["parentId"], "subKey": args["subKey"]})
    res = api("/flowModels:list", query=params)
    if res.get("error"):
        output(res)
        return
    print(json.dumps(res.get("data"), ensure_ascii=False, indent=2))

def do_save(args):
    model_uid = args["uid"]
    props = args.get("props")
    res = api("/flowModels:save", method="POST", body={"uid": model_uid, "props": props})
    if res.get("error"):
        output(res)
        return
    print(f"Model {model_uid} saved.")

def do_destroy(args):
    model_uid = args["uid"]
    res = api("/flowModels:destroy", method="POST", query=f"filterByTk={model_uid}")
    if res.get("error"):
        output(res)
        return
    print(f"Model {model_uid} destroyed.")

def dispatch(args):
    action = args.get("action", "")
    if action == "create":
        do_create(args)
    elif action == "attach":
        do_attach(args)
    elif action == "find":
        do_find(args)
    elif action == "list":
        do_list(args)
    elif action == "save":
        do_save(args)
    elif action == "destroy":
        do_destroy(args)
    else:
        print(json.dumps({"error": True, "message": f"Unknown action: {action}"}))
        sys.exit(1)

if __name__ == "__main__":
    run_main(dispatch)
