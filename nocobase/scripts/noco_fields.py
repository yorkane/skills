#!/usr/bin/env python3
import sys
import json
import os
sys.path.insert(0, os.path.dirname(__file__))
from noco_api import api, init_api, output, read_args, run_main
from noco_constants import INTERFACE_TYPE_MAP

def do_list(args):
    collection = args["collection"]
    col_res = api("/collections:get", query=f"filterByTk={collection}&appends=fields")
    if col_res.get("error"):
        output(col_res)
        return
    fields = [{"name": f["name"], "interface": f["interface"], "type": f["type"], "title": f.get("uiSchema", {}).get("title", f["name"])} for f in (col_res.get("data", {}).get("fields", []))]
    print(json.dumps(fields, ensure_ascii=False, indent=2))

def do_create(args):
    collection = args["collection"]
    field = args["field"]
    field_body = {"name": field["name"], "interface": field["interface"]}
    field_body["type"] = field.get("type") or INTERFACE_TYPE_MAP.get(field["interface"], "string")
    if field.get("title"):
        field_body["uiSchema"] = {"title": field["title"]}
    if field.get("target"):
        field_body["target"] = field["target"]
    if field.get("foreignKey"):
        field_body["foreignKey"] = field["foreignKey"]
    if field.get("uiSchema"):
        field_body.setdefault("uiSchema", {}).update(field["uiSchema"])
    res = api(f"/collections/{collection}/fields:create", method="POST", body=field_body)
    if res.get("error"):
        output(res)
        return
    print(f'Field "{field["name"]}" created in collection "{collection}".')

def do_update(args):
    collection = args["collection"]
    filter_by_tk = args.get("filterByTk")
    field = args.get("field", {})
    res = api(f"/collections/{collection}/fields:update", method="POST", query=f"filterByTk={filter_by_tk}", body=field)
    if res.get("error"):
        output(res)
        return
    print(f'Field "{filter_by_tk}" updated in collection "{collection}".')

def do_delete(args):
    collection = args["collection"]
    filter_by_tk = args.get("filterByTk")
    res = api(f"/collections/{collection}/fields:destroy", method="POST", query=f"filterByTk={filter_by_tk}")
    if res.get("error"):
        output(res)
        return
    print(f'Field "{filter_by_tk}" deleted from collection "{collection}".')

def dispatch(args):
    action = args.get("action", "")
    if action == "list":
        do_list(args)
    elif action == "create":
        do_create(args)
    elif action == "update":
        do_update(args)
    elif action == "delete":
        do_delete(args)
    else:
        print(json.dumps({"error": True, "message": f"Unknown action: {action}"}))
        sys.exit(1)

if __name__ == "__main__":
    run_main(dispatch)
