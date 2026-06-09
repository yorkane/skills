#!/usr/bin/env python3
import sys
import json
import os
sys.path.insert(0, os.path.dirname(__file__))
from noco_api import api, init_api, output, read_args, run_main

def do_list(args):
    res = api("/desktopRoutes:listAccessible", query="tree=true")
    if res.get("error"):
        output(res)
        return
    print(json.dumps(res.get("data"), ensure_ascii=False, indent=2))

def do_create_group(args):
    title = args["title"]
    sort = args.get("sort", 100)
    res = api("/desktopRoutes:create", method="POST", body={"title": title, "type": "group", "sort": sort})
    if res.get("error"):
        output(res)
        return
    print(f'Group "{title}" created. ID: {res.get("data", {}).get("id", "N/A")}')

def do_create_page(args):
    title = args["title"]
    schema_uid = args.get("schemaUid")
    parent_id = args.get("parentId")
    sort = args.get("sort", 100)
    children = args.get("children")
    body = {"title": title, "type": "flowPage", "parentId": parent_id, "sort": sort}
    if children and len(children) > 0:
        body["children"] = children
    elif schema_uid:
        body["schemaUid"] = schema_uid
    res = api("/desktopRoutes:create", method="POST", body=body)
    if res.get("error"):
        output(res)
        return
    info = [f'Page "{title}" created. ID: {res.get("data", {}).get("id", "N/A")}']
    if children:
        info.append(f'Tabs: {", ".join(c.get("tabSchemaName", c.get("schemaUid", "")) for c in children)}')
    if schema_uid:
        info.append(f"schemaUid: {schema_uid}")
    print("\n".join(info))

def do_delete(args):
    route_id = args["id"]
    res = api("/desktopRoutes:destroy", method="POST", query=f"filterByTk={route_id}")
    if res.get("error"):
        output(res)
        return
    print(f"Route {route_id} deleted.")

def dispatch(args):
    action = args.get("action", "")
    if action == "list":
        do_list(args)
    elif action == "create_group":
        do_create_group(args)
    elif action == "create_page":
        do_create_page(args)
    elif action == "delete":
        do_delete(args)
    else:
        print(json.dumps({"error": True, "message": f"Unknown action: {action}"}))
        sys.exit(1)

if __name__ == "__main__":
    run_main(dispatch)
