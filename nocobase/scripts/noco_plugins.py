#!/usr/bin/env python3
import sys
import json
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from noco_api import init_api, api, output, run_main

DEFAULT_PLUGINS = [
    "api-keys",
]

PLUGIN_META = {
    "api-keys":            {"name": "api-keys", "title": "API 密钥"},
    "idp-oauth":           {"name": "idp-oauth", "title": "OAuth 身份提供者"},
    "workflow-notification": {"name": "workflow-notification", "title": "工作流通知"},
    "comments":            {"name": "comments", "title": "评论"},
    "map":                 {"name": "map", "title": "地图"},
    "field-code":          {"name": "field-code", "title": "代码字段"},
    "field-m2m-array":     {"name": "field-m2m-array", "title": "M2M 数组字段"},
    "embed":               {"name": "embed", "title": "嵌入"},
    "block-tree":          {"name": "block-tree", "title": "树形区块"},
    "multi-keyword-filter": {"name": "multi-keyword-filter", "title": "多关键词筛选"},
}

def dispatch(args):
    action = args.get("action", "list")

    if action == "list":
        do_list(args)
    elif action == "enable":
        do_enable(args)
    elif action == "disable":
        do_disable(args)
    elif action == "init":
        do_init(args)
    else:
        output({"error": True, "message": f"Unknown action: {action}"})

def _list_plugins(pageSize=200):
    res = api(f"/pm:list")
    if res.get("error"):
        return res
    data = res.get("data", [])
    if isinstance(data, list):
        return data
    return data if data else []

def do_list(args):
    plugins = _list_plugins(args.get("pageSize", 200))
    if isinstance(plugins, dict) and plugins.get("error"):
        output(plugins)
        return

    status = args.get("status")
    built_in = args.get("built_in")

    result = []
    for p in plugins:
        if status == "enabled" and not p.get("enabled"):
            continue
        if status == "disabled" and p.get("enabled"):
            continue
        if built_in is True and not p.get("builtIn"):
            continue
        if built_in is False and p.get("builtIn"):
            continue
        result.append({
            "name": p["name"],
            "packageName": p.get("packageName", ""),
            "version": p.get("version", ""),
            "enabled": p["enabled"],
            "installed": p["installed"],
            "builtIn": p["builtIn"],
        })

    output({"count": len(result), "plugins": result})

def do_enable(args):
    names = args.get("names", [])
    if not names:
        output({"error": True, "message": "names parameter required"})
        return

    results = []
    for name in names:
        res = api(f"/pm:enable?filterByTk={name}", method="POST")
        results.append({
            "plugin": name,
            "success": not res.get("error"),
            "response": res
        })

    success = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    output({
        "action": "enable",
        "success_count": len(success),
        "failed_count": len(failed),
        "details": results
    })

def do_disable(args):
    names = args.get("names", [])
    if not names:
        output({"error": True, "message": "names parameter required"})
        return

    results = []
    for name in names:
        res = api(f"/pm:disable?filterByTk={name}", method="POST")
        results.append({
            "plugin": name,
            "success": not res.get("error"),
            "response": res
        })

    output({
        "action": "disable",
        "results": results
    })

def do_init(args):
    names = args.get("names", DEFAULT_PLUGINS)

    plugins = _list_plugins()
    if isinstance(plugins, dict) and plugins.get("error"):
        output(plugins)
        return

    plugin_map = {p["name"]: p for p in plugins}

    to_enable = []
    already_enabled = []
    not_installed = []

    for name in names:
        p = plugin_map.get(name)
        if p is None:
            not_installed.append(name)
        elif p["enabled"]:
            already_enabled.append(name)
        else:
            to_enable.append(name)

    results = []
    for name in to_enable:
        res = api(f"/pm:enable?filterByTk={name}", method="POST")
        results.append({
            "plugin": name,
            "success": not res.get("error"),
            "response": res
        })

    success = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    output({
        "action": "init",
        "enabled_count": len(success),
        "failed_count": len(failed),
        "already_enabled": already_enabled,
        "not_installed": not_installed if not_installed else None,
        "details": results if results else None
    })

if __name__ == "__main__":
    run_main(dispatch)
