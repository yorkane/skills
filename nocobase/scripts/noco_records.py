#!/usr/bin/env python3
import sys
import json
import os
import urllib.parse
sys.path.insert(0, os.path.dirname(__file__))
from noco_api import api, init_api, output, read_args, run_main

def do_list(args):
    collection = args["collection"]
    page = args.get("page", 1)
    page_size = args.get("pageSize", 20)
    params = urllib.parse.urlencode({"page": page, "pageSize": page_size})
    if args.get("filter"):
        params += f"&filter={urllib.parse.quote(json.dumps(args['filter']))}"
    if args.get("sort"):
        params += f"&sort={','.join(args['sort'])}"
    if args.get("appends"):
        params += f"&appends={','.join(args['appends'])}"
    res = api(f"/{collection}:list", query=params)
    if res.get("error"):
        output(res)
        return
    print(json.dumps(res.get("data"), ensure_ascii=False, indent=2))

def do_create(args):
    collection = args["collection"]
    record = args.get("record", {})
    res = api(f"/{collection}:create", method="POST", body=record)
    if res.get("error"):
        output(res)
        return
    print(f'Record created in "{collection}". ID: {res.get("data", {}).get("id", "N/A")}')

def do_update(args):
    collection = args["collection"]
    filter_by_tk = args.get("filterByTk")
    record = args.get("record", {})
    res = api(f"/{collection}:update", method="POST", query=f"filterByTk={filter_by_tk}", body=record)
    if res.get("error"):
        output(res)
        return
    print(f'Record {filter_by_tk} updated in "{collection}".')

def do_delete(args):
    collection = args["collection"]
    filter_by_tk = args.get("filterByTk")
    res = api(f"/{collection}:destroy", method="POST", query=f"filterByTk={filter_by_tk}")
    if res.get("error"):
        output(res)
        return
    print(f'Record {filter_by_tk} deleted from "{collection}".')

def do_batch_create(args):
    collection = args["collection"]
    records = args.get("records", [])
    results = []
    for record in records:
        res = api(f"/{collection}:create", method="POST", body=record)
        if res.get("error"):
            results.append({"ok": False, "error": res.get("data")})
        else:
            results.append({"ok": True, "id": res.get("data", {}).get("id")})
    ok = sum(1 for r in results if r["ok"])
    fail = len(results) - ok
    print(f"Batch create: {ok} succeeded, {fail} failed.\n{json.dumps(results, ensure_ascii=False, indent=2)}")

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
    elif action == "batch_create":
        do_batch_create(args)
    else:
        print(json.dumps({"error": True, "message": f"Unknown action: {action}"}))
        sys.exit(1)

if __name__ == "__main__":
    run_main(dispatch)
