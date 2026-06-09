#!/usr/bin/env python3
import sys
import json
import os
sys.path.insert(0, os.path.dirname(__file__))
from noco_api import api, init_api, output, read_args, run_main

def do_create(args):
    schema = args["schema"]
    position = args.get("position", "beforeEnd")
    parent_uid = args.get("uid")
    if parent_uid:
        res = api("/uiSchemas:insertAdjacent", method="POST", body={"schema": schema, "position": position, "uid": parent_uid})
    else:
        res = api("/uiSchemas:create", method="POST", body=schema)
    if res.get("error"):
        output(res)
        return
    print(f'Schema created. UID: {schema.get("x-uid")}')

def do_get(args):
    schema_uid = args["uid"]
    res = api(f"/uiSchemas:getJsonSchema/{schema_uid}")
    if res.get("error"):
        output(res)
        return
    print(json.dumps(res.get("data"), ensure_ascii=False, indent=2))

def do_update(args):
    schema_uid = args["uid"]
    patch = args.get("patch", {})
    body = {"x-uid": schema_uid, **patch}
    res = api("/uiSchemas:patch", method="POST", body=body)
    if res.get("error"):
        output(res)
        return
    print(f'Schema node "{schema_uid}" updated.')

def do_delete(args):
    schema_uid = args["uid"]
    res = api("/uiSchemas:destroy", method="POST", query=f"filterByTk={schema_uid}")
    if res.get("error"):
        output(res)
        return
    print(f'Schema node "{schema_uid}" destroyed.')

def dispatch(args):
    action = args.get("action", "")
    if action == "create":
        do_create(args)
    elif action == "get":
        do_get(args)
    elif action == "update":
        do_update(args)
    elif action == "delete":
        do_delete(args)
    else:
        print(json.dumps({"error": True, "message": f"Unknown action: {action}"}))
        sys.exit(1)

if __name__ == "__main__":
    run_main(dispatch)
