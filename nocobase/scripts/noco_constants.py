#!/usr/bin/env python3
STANDARD_TEMPLATE_FIELDS = [
    {"name": "id", "type": "bigInt", "interface": "integer", "primaryKey": True, "autoIncrement": True, "uiSchema": {"type": "number", "x-component": "InputNumber", "x-component-props": {"stringMode": True, "step": "1"}, "x-validator": "integer", "title": "ID"}},
    {"name": "createdAt", "type": "date", "interface": "createdAt", "field": "createdAt", "uiSchema": {"type": "datetime", "title": "创建时间", "x-component": "DatePicker", "x-component-props": {}, "x-read-pretty": True}},
    {"name": "createdBy", "type": "belongsTo", "interface": "createdBy", "target": "users", "foreignKey": "createdById", "targetKey": "id", "uiSchema": {"type": "object", "title": "创建人", "x-component": "AssociationField", "x-component-props": {"fieldNames": {"value": "id", "label": "nickname"}}, "x-read-pretty": True}},
    {"name": "updatedAt", "type": "date", "interface": "updatedAt", "field": "updatedAt", "uiSchema": {"type": "datetime", "title": "更新时间", "x-component": "DatePicker", "x-component-props": {}, "x-read-pretty": True}},
    {"name": "updatedBy", "type": "belongsTo", "interface": "updatedBy", "target": "users", "foreignKey": "updatedById", "targetKey": "id", "uiSchema": {"type": "object", "title": "更新人", "x-component": "AssociationField", "x-component-props": {"fieldNames": {"value": "id", "label": "nickname"}}, "x-read-pretty": True}},
]

STANDARD_TEMPLATE_OPTIONS = {
    "template": "general", "autoGenId": False, "logging": True,
    "createdAt": True, "createdBy": True, "updatedAt": True, "updatedBy": True,
}

SYSTEM_TABLES = {"users", "roles", "collections", "fields", "migrations", "rolesCollections", "rolesUsers", "collectionsFields"}

INTERFACE_TYPE_MAP = {
    "input": "string", "textarea": "text", "email": "string", "phone": "string",
    "password": "string", "number": "float", "integer": "bigInt", "percent": "float",
    "checkbox": "boolean", "select": "string", "radioGroup": "string",
    "checkboxGroup": "json", "datePicker": "date", "timePicker": "time",
    "url": "string", "colorPicker": "string", "icon": "string",
    "richText": "text", "attachment": "belongsToMany", "json": "json", "text": "text",
    "m2o": "belongsTo", "belongsTo": "belongsTo", "o2m": "hasMany", "hasMany": "hasMany",
    "m2m": "belongsToMany", "belongsToMany": "belongsToMany",
}

FIELD_COMPONENT_MAP = {
    "input": "Input", "textarea": "Input.TextArea", "email": "Input", "phone": "Input",
    "password": "Password", "number": "InputNumber", "integer": "InputNumber",
    "percent": "Percent", "checkbox": "Checkbox", "select": "Select",
    "radioGroup": "Radio.Group", "checkboxGroup": "Checkbox.Group",
    "datePicker": "DatePicker", "timePicker": "TimePicker", "url": "Input",
    "colorPicker": "ColorPicker", "icon": "IconPicker", "richText": "RichText",
    "attachment": "Upload", "m2o": "AssociationField", "belongsTo": "AssociationField",
    "o2m": "AssociationField", "hasMany": "AssociationField",
    "m2m": "AssociationField", "belongsToMany": "AssociationField",
    "json": "Input.TextArea", "text": "Input.TextArea",
}

SORTABLE_INTERFACES = {"number", "integer", "float", "datePicker", "timePicker", "percent"}
FILTERABLE_INTERFACES = {"input", "textarea", "select", "m2o", "belongsTo"}

SYSTEM_FIELDS = {"id", "created_at", "createdAt", "updated_at", "updatedAt", "created_by_id", "createdById", "updated_by_id", "updatedById", "createdBy", "updatedBy"}

BELONGS_TO_INTERFACES = {"m2o", "belongsTo"}
HAS_MANY_INTERFACES = {"o2m", "hasMany"}
M2M_INTERFACES = {"m2m", "belongsToMany"}

FORM_SKIP_INTERFACES = {"o2m", "hasMany", "json", "attachment"}

FORM_FIELD_MODEL_MAP = {
    "input": "InputFieldModel", "textarea": "TextareaFieldModel", "email": "InputFieldModel",
    "phone": "InputFieldModel", "password": "InputFieldModel", "number": "NumberFieldModel",
    "integer": "NumberFieldModel", "percent": "NumberFieldModel", "checkbox": "CheckboxFieldModel",
    "select": "SelectFieldModel", "radioGroup": "RadioGroupFieldModel",
    "checkboxGroup": "CheckboxGroupFieldModel", "datePicker": "DatePickerFieldModel",
    "timePicker": "TimePickerFieldModel", "url": "InputFieldModel", "richText": "RichTextFieldModel",
    "m2o": "RecordSelectFieldModel", "belongsTo": "RecordSelectFieldModel",
    "m2m": "RecordSelectFieldModel", "belongsToMany": "RecordSelectFieldModel",
}

FILTER_FIELD_MODEL_MAP = {
    "input": "InputFieldModel", "textarea": "InputFieldModel", "email": "InputFieldModel",
    "phone": "InputFieldModel", "number": "NumberFieldModel", "integer": "NumberFieldModel",
    "percent": "NumberFieldModel", "select": "SelectFieldModel", "checkbox": "InputFieldModel",
    "datePicker": "InputFieldModel", "m2o": "FilterFormRecordSelectFieldModel",
    "belongsTo": "FilterFormRecordSelectFieldModel",
}

TITLE_FIELD_CANDIDATES = ["name", "title", "label", "content", "caption", "subject", "displayName", "description"]
TEXT_INTERFACES = {"input", "textarea", "email", "phone", "url", "richText", "text"}

TITLE_MAP = {
    "name": "名称", "title": "标题", "description": "描述", "status": "状态",
    "sort": "排序", "price": "价格", "quantity": "数量", "count": "数量",
    "phone": "手机号", "mobile": "手机号", "email": "邮箱", "remark": "备注",
    "note": "备注", "icon": "图标", "type": "类型", "total": "金额", "amount": "金额",
}

def is_system_table(name):
    return name.startswith('_') or name in SYSTEM_TABLES

def is_system_field(name):
    return name in SYSTEM_FIELDS or name.endswith('_id')

def is_belongs_to(field):
    return field.get("interface") in BELONGS_TO_INTERFACES

def is_has_many(field):
    return field.get("interface") in HAS_MANY_INTERFACES

def is_association_field(field):
    return field.get("interface") in (BELONGS_TO_INTERFACES | HAS_MANY_INTERFACES | M2M_INTERFACES)

def get_display_model(field):
    iface = field.get("interface", "")
    if iface in {"number", "integer", "percent", "float"}:
        return "DisplayNumberFieldModel"
    if iface in {"select", "radioGroup"}:
        return "DisplayEnumFieldModel"
    if iface in {"checkbox"}:
        return "DisplayCheckboxFieldModel"
    if iface in {"datePicker", "timePicker"}:
        return "DisplayDateFieldModel"
    return "DisplayTextFieldModel"

def get_form_field_model(field):
    return FORM_FIELD_MODEL_MAP.get(field.get("interface"), "InputFieldModel")

def get_field_title(field):
    if field.get("uiSchema", {}).get("title"):
        return field["uiSchema"]["title"]
    return TITLE_MAP.get(field.get("name"), field.get("name", ""))

def pick_title_field(custom_fields):
    for candidate in TITLE_FIELD_CANDIDATES:
        f = next((f for f in custom_fields if f["name"] == candidate and f.get("interface") in TEXT_INTERFACES), None)
        if f:
            return f["name"]
    first_text = next((f for f in custom_fields if f.get("interface") in TEXT_INTERFACES), None)
    if first_text:
        return first_text["name"]
    return None
