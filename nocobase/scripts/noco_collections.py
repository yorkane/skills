#!/usr/bin/env python3
import sys
import json
import copy
import os
sys.path.insert(0, os.path.dirname(__file__))
from noco_api import api, init_api, output, read_args, run_main
from noco_constants import (
    is_system_table, INTERFACE_TYPE_MAP, STANDARD_TEMPLATE_FIELDS,
    STANDARD_TEMPLATE_OPTIONS, pick_title_field, TEXT_INTERFACES
)

def do_list(args):
    filter_system = args.get("filter_system", True)
    page = args.get("page", 1)
    page_size = args.get("pageSize", 200)
    res = api("/collections:list", query=f"page={page}&pageSize={page_size}")
    if res.get("error"):
        output(res)
        return
    data = res.get("data", [])
    if filter_system:
        data = [c for c in data if not is_system_table(c["name"])]
    summary = [{"name": c["name"], "title": c.get("title", c["name"]), "fields": len(c.get("fields", []))} for c in data]
    print(json.dumps(summary, ensure_ascii=False, indent=2))

def do_get(args):
    name = args["name"]
    res = api("/collections:get", query=f"filterByTk={name}&appends=fields")
    if res.get("error"):
        output(res)
        return
    print(json.dumps(res.get("data"), ensure_ascii=False, indent=2))

def do_create(args):
    project = args.get("project")
    tab = args.get("tab")
    if not project or not tab:
        print(json.dumps({"error": True, "message": '"project" and "tab" are required for create action.'}))
        sys.exit(1)
    title = args.get("title")
    fields = args.get("fields", [])
    from datetime import datetime
    now = datetime.now()
    col_name = f"{project}_{tab}-{now.strftime('%y%m%d')}"
    col_title = title or col_name
    body = {"name": col_name, "title": col_title, **STANDARD_TEMPLATE_OPTIONS}
    standard_fields = copy.deepcopy(STANDARD_TEMPLATE_FIELDS)
    custom_fields = []
    for f in fields:
        field = {"name": f["name"], "interface": f["interface"]}
        field["type"] = f.get("type") or INTERFACE_TYPE_MAP.get(f["interface"], "string")
        if f.get("title"):
            field["uiSchema"] = {"title": f["title"]}
        if f.get("target"):
            field["target"] = f["target"]
        if f.get("foreignKey"):
            field["foreignKey"] = f["foreignKey"]
        if f.get("uiSchema"):
            field.setdefault("uiSchema", {}).update(f["uiSchema"])
        custom_fields.append(field)
    body["fields"] = standard_fields + custom_fields
    title_field = pick_title_field(custom_fields)
    if title_field:
        body["titleField"] = title_field
    res = api("/collections:create", method="POST", body=body)
    if res.get("error"):
        output(res)
        return
    title_info = f', titleField: "{title_field}"' if title_field else ""
    print(f'Collection "{col_name}" (title: "{col_title}") created successfully. {len(standard_fields)} standard + {len(custom_fields)} custom fields included{title_info}.')

def do_update(args):
    filter_by_tk = args.get("filterByTk")
    update_body = {k: v for k, v in args.items() if k not in ("action", "filterByTk")}
    res = api("/collections:update", method="POST", query=f"filterByTk={filter_by_tk}", body=update_body)
    if res.get("error"):
        output(res)
        return
    print(f'Collection "{filter_by_tk}" updated successfully.')

def do_delete(args):
    name = args.get("name")
    res = api("/collections:destroy", method="POST", query=f"filterByTk={name}")
    if res.get("error"):
        output(res)
        return
    print(f'Collection "{name}" deleted successfully.')

def dispatch(args):
    action = args.get("action", "")
    if action == "list":
        do_list(args)
    elif action == "get":
        do_get(args)
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
