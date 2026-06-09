#!/usr/bin/env python3
import sys
import json
import os
import re
import time
import urllib.parse
sys.path.insert(0, os.path.dirname(__file__))
from noco_api import api, init_api, uid, create_and_attach, save_step_params, output, read_args, run_main
from noco_constants import (
    is_system_field, get_display_model, SORTABLE_INTERFACES, is_association_field,
    HAS_MANY_INTERFACES, BELONGS_TO_INTERFACES, M2M_INTERFACES, get_form_field_model,
    FORM_SKIP_INTERFACES
)

def create_form_structure(parent_action_uid, collection_name, fields, form_type):
    is_create = form_type == "CreateFormModel"
    child_page_uid = uid()
    create_and_attach(child_page_uid, "ChildPageModel", parent_action_uid, "page", "object", 0,
        {"pageSettings": {"general": {"displayTitle": False, "enableTabs": True}}})

    tab_uid = uid()
    tab_title = '{{t("Add new")}}' if is_create else '{{t("Edit")}}'
    create_and_attach(tab_uid, "ChildPageTabModel", child_page_uid, "tabs", "object", 0,
        {"pageTabSettings": {"tab": {"title": tab_title}}})

    block_grid_uid = uid()
    create_and_attach(block_grid_uid, "BlockGridModel", tab_uid, "grid", "object", 0)

    form_model_uid = uid()
    resource_init = {"dataSourceKey": "main", "collectionName": collection_name}
    if not is_create:
        resource_init["filterByTk"] = "{{ctx.view.inputArgs.filterByTk}}"
    create_and_attach(form_model_uid, form_type, block_grid_uid, "items", "array", 0,
        {"resourceSettings": {"init": resource_init}})

    block_row_name = uid()
    save_step_params(block_grid_uid, {
        "gridSettings": {"grid": {"rows": {block_row_name: [[form_model_uid]]}, "sizes": {block_row_name: [24]}, "rowOrder": [block_row_name]}}
    })

    create_and_attach(uid(), "FormSubmitActionModel", form_model_uid, "actions", "array", 0)

    form_grid_uid = uid()
    create_and_attach(form_grid_uid, "FormGridModel", form_model_uid, "grid", "object", 0)

    form_fields = [f for f in fields if not is_system_field(f["name"]) and f.get("interface") not in FORM_SKIP_INTERFACES and f.get("interface") not in HAS_MANY_INTERFACES]

    grid_rows = {}
    grid_sizes = {}
    grid_row_order = []
    item_idx = 0

    for f in form_fields:
        form_item_uid = uid()
        field_model_name = get_form_field_model(f)
        create_and_attach(form_item_uid, "FormItemModel", form_grid_uid, "items", "array", item_idx,
            {"fieldSettings": {"init": {"dataSourceKey": "main", "collectionName": collection_name, "fieldPath": f["name"]}}})

        field_uid = uid()
        create_and_attach(field_uid, field_model_name, form_item_uid, "field", "object", 0)

        is_assoc_select = f.get("interface") in BELONGS_TO_INTERFACES or f.get("interface") in M2M_INTERFACES
        if is_assoc_select and f.get("target"):
            display_uid = uid()
            create_and_attach(display_uid, "DisplayTextFieldModel", field_uid, "field", "object", 0, {
                "fieldSettings": {"init": {"dataSourceKey": "main", "collectionName": f["target"], "fieldPath": "name"}},
                "popupSettings": {"openView": {"collectionName": f["target"], "associationName": f"{collection_name}.{f['name']}", "dataSourceKey": "main"}},
            })

        row_name = uid()
        grid_rows[row_name] = [[form_item_uid]]
        grid_sizes[row_name] = [24]
        grid_row_order.append(row_name)
        item_idx += 1

    save_step_params(form_grid_uid, {
        "gridSettings": {"grid": {"rows": grid_rows, "sizes": grid_sizes, "rowOrder": grid_row_order}}
    })

    return form_model_uid

def strip_emoji(s):
    return re.sub(r'^[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF\ufe0f\u200d\U000E0020-\U000E007F]+\s*', '', s).strip()

def do_create(args):
    collection_name = args["collection_name"]
    group_title_raw = args.get("group_title", "数据管理")
    page_title_raw = args.get("page_title")
    icon = args.get("icon", "")
    group_icon = args.get("group_icon", "") or icon

    col_res = api("/collections:get", query=f"filterByTk={collection_name}&appends=fields")
    if col_res.get("error"):
        print(json.dumps({"error": True, "message": f'Collection "{collection_name}" not found.', "data": col_res.get("data")}))
        sys.exit(1)
    col_data = col_res.get("data", {})
    fields = col_data.get("fields", [])
    user_fields = [f for f in fields if not is_system_field(f["name"])]
    raw_title = page_title_raw or col_data.get("title", collection_name)
    page_title = f"{icon} {raw_title}" if icon else raw_title

    routes_res = api("/desktopRoutes:listAccessible", query="tree=true")
    if routes_res.get("error"):
        print(json.dumps({"error": True, "message": "Cannot list routes.", "data": routes_res.get("data")}))
        sys.exit(1)

    group_id = None
    group_title = f"{group_icon} {group_title_raw}" if group_icon else group_title_raw
    for g in (routes_res.get("data") or []):
        if g.get("type") == "group" and strip_emoji(g.get("title", "")) == group_title_raw:
            group_id = g["id"]
            break
    if not group_id:
        g_res = api("/desktopRoutes:create", method="POST", body={"title": group_title, "type": "group", "sort": 100})
        if g_res.get("error"):
            print(json.dumps({"error": True, "data": g_res.get("data")}))
            sys.exit(1)
        group_id = g_res.get("data", {}).get("id")

    tab_schema_uid = uid()
    route_res = api("/desktopRoutes:create", method="POST", body={
        "title": page_title, "type": "flowPage", "parentId": group_id, "sort": 100,
        "children": [{"type": "tabs", "schemaUid": tab_schema_uid, "tabSchemaName": page_title, "hidden": True}]
    })
    if route_res.get("error"):
        print(json.dumps({"error": True, "data": route_res.get("data")}))
        sys.exit(1)
    route_id = route_res.get("data", {}).get("id")
    log = [f"Route: ID={route_id}, tab={tab_schema_uid}"]

    route_schema_uid = uid()
    api("/uiSchemas:create", method="POST", body={"type": "void", "x-component": "FlowRoute", "name": uid(), "x-uid": route_schema_uid, "x-async": False})
    api("/desktopRoutes:update", method="POST", query=f"filterByTk={route_id}", body={"schemaUid": route_schema_uid})

    grid_model_uid = None
    for i in range(5):
        time.sleep(1)
        g = api("/flowModels:findOne", query=f"parentId={tab_schema_uid}&subKey=grid")
        if g.get("data", {}).get("uid"):
            grid_model_uid = g["data"]["uid"]
            break
    if not grid_model_uid:
        grid_model_uid = uid()
        create_and_attach(grid_model_uid, "BlockGridModel", tab_schema_uid, "grid", "object", 0, {})
        log.append("Grid created manually")

    table_model_uid = uid()
    table_step_params = {
        "resourceSettings": {"init": {"dataSourceKey": "main", "collectionName": collection_name}}
    }
    table_res = create_and_attach(table_model_uid, "TableBlockModel", grid_model_uid, "items", "array", 0, table_step_params)
    if table_res.get("error"):
        log.append(f"ERROR TableBlockModel: {json.dumps(table_res.get('data'))}")
        print("\n".join(log))
        sys.exit(1)
    log.append(f"TableBlock: {table_model_uid}")

    table_row_name = uid()
    save_step_params(grid_model_uid, {
        "gridSettings": {"grid": {"rows": {table_row_name: [[table_model_uid]]}, "sizes": {table_row_name: [24]}, "rowOrder": [table_row_name]}}
    })

    create_and_attach(uid(), "FilterActionModel", table_model_uid, "actions", "array", 0)
    add_new_uid = uid()
    create_and_attach(add_new_uid, "AddNewActionModel", table_model_uid, "actions", "array", 1,
        {"popupSettings": {"openView": {"collectionName": collection_name, "dataSourceKey": "main"}}})
    create_form_structure(add_new_uid, collection_name, user_fields, "CreateFormModel")
    create_and_attach(uid(), "RefreshActionModel", table_model_uid, "actions", "array", 2)
    create_and_attach(uid(), "BulkDeleteActionModel", table_model_uid, "actions", "array", 3)
    log.append("Actions: filter, add-new(with form), refresh, bulk-delete")

    col_idx = 0
    col_errors = []
    for f in user_fields:
        col_model_uid = uid()
        display_model = get_display_model(f)
        col_step_params = {
            "fieldSettings": {"init": {"dataSourceKey": "main", "collectionName": collection_name, "fieldPath": f["name"]}},
            "tableColumnSettings": {"model": {"use": display_model}}
        }
        if f.get("interface") in SORTABLE_INTERFACES:
            col_step_params["tableColumnSettings"]["sortable"] = True
            col_step_params["tableColumnSettings"]["sorter"] = {"sorter": True}
        col_res2 = create_and_attach(col_model_uid, "TableColumnModel", table_model_uid, "columns", "array", col_idx, col_step_params)
        if col_res2.get("error"):
            col_errors.append(f'{f["name"]}: {json.dumps(col_res2.get("data"))}')
        else:
            display_uid = uid()
            if is_association_field(f) and f.get("target"):
                display_step_params = {
                    "popupSettings": {"openView": {"collectionName": f["target"], "associationName": f"{collection_name}.{f['name']}", "dataSourceKey": "main"}}
                }
            else:
                display_step_params = {
                    "popupSettings": {"openView": {"collectionName": collection_name, "dataSourceKey": "main"}},
                    "fieldBinding": {"use": display_model},
                    "fieldSettings": {"init": {"dataSourceKey": "main", "collectionName": collection_name, "fieldPath": f["name"]}}
                }
            create_and_attach(display_uid, display_model, col_model_uid, "field", "object", 0, display_step_params)
        col_idx += 1
    log.append(f"Columns: {col_idx} created" + (f", {len(col_errors)} failed" if col_errors else ""))

    act_col_uid = uid()
    act_col_res = create_and_attach(act_col_uid, "TableActionsColumnModel", table_model_uid, "columns", "array", col_idx)
    if not act_col_res.get("error"):
        edit_action_uid = uid()
        create_and_attach(edit_action_uid, "EditActionModel", act_col_uid, "actions", "array", 0,
            {"popupSettings": {"openView": {"collectionName": collection_name, "dataSourceKey": "main"}}, "buttonSettings": {"general": {"type": "link", "icon": None}}})
        create_form_structure(edit_action_uid, collection_name, user_fields, "EditFormModel")
        log.append("Action column: edit(link) with form")

    print(f"""Table UI created (v2 flow engine)!
{chr(10).join(log)}

- Collection: {collection_name}
- Group: {group_title} (ID: {group_id})
- Page: {page_title}
- Route ID: {route_id}
- Columns: {col_idx}""" + (f", {len(col_errors)} failed" if col_errors else ""))

def do_delete(args):
    collection_name = args["collection_name"]
    routes_res = api("/desktopRoutes:listAccessible", query="tree=true")
    if routes_res.get("error"):
        print(json.dumps({"error": True, "message": "Cannot list routes.", "data": routes_res.get("data")}))
        sys.exit(1)

    target_route = None
    col_res2 = api("/collections:get", query=f"filterByTk={collection_name}")
    col_title = col_res2.get("data", {}).get("title", "") if not col_res2.get("error") else ""

    for group in (routes_res.get("data") or []):
        for child in (group.get("children") or []):
            page_title = (child.get("title") or "").lower()
            c_name = collection_name.lower()
            c_title = col_title.lower()
            if page_title and (c_name in page_title or (c_title and c_title in page_title)):
                target_route = child
                break
        if target_route:
            break

    if not target_route:
        print(json.dumps({"error": True, "message": f'No page route found matching collection "{collection_name}".'}))
        sys.exit(1)

    route_del_res = api("/desktopRoutes:destroy", method="POST", query=f"filterByTk={target_route['id']}")
    if route_del_res.get("error"):
        print(json.dumps({"error": True, "message": "Failed to delete route.", "data": route_del_res.get("data")}))
        sys.exit(1)

    if target_route.get("schemaUid"):
        api("/uiSchemas:destroy", method="POST", query=f"filterByTk={target_route['schemaUid']}")

    print(f"""Table UI deleted!
- Collection: {collection_name}
- Route ID: {target_route['id']} (deleted)""")

def dispatch(args):
    action = args.get("action", "")
    if action == "create":
        do_create(args)
    elif action == "delete":
        do_delete(args)
    else:
        print(json.dumps({"error": True, "message": f"Unknown action: {action}"}))
        sys.exit(1)

if __name__ == "__main__":
    run_main(dispatch)
