#!/usr/bin/env python3
import argparse
import json
import os
from html import escape
from pathlib import Path


def template_files(project_name, title, api_base):
    safe_title = escape(title)
    js_project_name = json.dumps(project_name, ensure_ascii=False)
    js_title = json.dumps(title, ensure_ascii=False)
    return {
        "index.html": f'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_title}</title>
  <link rel="stylesheet" href="./vendor/quasar-umd.css">
  <link rel="stylesheet" href="./app.css">
</head>
<body>
  <div id="q-app">
    <q-layout view="hHh lpR fFf">
      <q-header elevated>
        <q-toolbar>
          <q-toolbar-title>{{{{ i18n.title }}}}</q-toolbar-title>
          <q-btn flat dense no-caps icon="mdi-translate" :label="i18n.language" @click="toggleLocale"></q-btn>
        </q-toolbar>
      </q-header>
      <q-page-container>
        <q-page class="q-pa-md">
          <q-card flat bordered>
            <q-card-section>
              <div class="text-h6">{{{{ i18n.projectName }}}}</div>
              <div class="text-body2 text-grey-7">{{{{ i18n.subtitle }}}}</div>
            </q-card-section>
          </q-card>
        </q-page>
      </q-page-container>
    </q-layout>
  </div>
  <script src="./vendor/quasar-umd.js"></script>
  <script src="./i18n.js"></script>
  <script src="./api.js"></script>
  <script src="./app.js"></script>
</body>
</html>
''',
        "app.js": '''const { computed, createApp, onBeforeUnmount, onMounted, ref } = Vue

const locale = ref(window.appI18n.getLocale())
const i18n = computed(() => window.appI18n.messages[locale.value].app)

function applyLocale (nextLocale) {
  locale.value = nextLocale
  document.documentElement.lang = nextLocale
  document.title = i18n.value.title

  if (Quasar.Lang) {
    const language = nextLocale === 'en-US' ? Quasar.Lang.enUS : Quasar.Lang.zhCN
    if (language) Quasar.Lang.set(language)
  }
}

const app = createApp({
  setup () {
    const loading = ref(false)
    let unsubscribeLocale = () => {}

    function toggleLocale () {
      const nextLocale = locale.value === 'zh-CN' ? 'en-US' : 'zh-CN'
      applyLocale(window.appI18n.setLocale(nextLocale))
    }

    onMounted(() => {
      unsubscribeLocale = window.appI18n.subscribe(applyLocale)
    })

    onBeforeUnmount(() => unsubscribeLocale())

    return {
      i18n,
      loading,
      toggleLocale
    }
  }
})

app.use(Quasar)
applyLocale(locale.value)

if (Quasar.IconSet && Quasar.IconSet.mdiV7) {
  Quasar.IconSet.set(Quasar.IconSet.mdiV7)
}

app.mount('#q-app')
''',
        "i18n.js": f'''(function () {{
  const messages = {{
    'zh-CN': {{
      app: {{
        title: {js_title},
        projectName: {js_project_name},
        subtitle: 'Vue 3 + Quasar UMD',
        language: 'English'
      }}
    }},
    'en-US': {{
      app: {{
        title: {js_title},
        projectName: {js_project_name},
        subtitle: 'Vue 3 + Quasar UMD',
        language: '中文'
      }}
    }}
  }}

  function normalize (locale) {{
    return locale === 'en-US' ? 'en-US' : 'zh-CN'
  }}

  function getLocale () {{
    return normalize(window.localStorage.getItem('app_locale'))
  }}

  function setLocale (locale) {{
    const nextLocale = normalize(locale)
    window.localStorage.setItem('app_locale', nextLocale)
    window.top.postMessage({{ type: 'app-locale-change', locale: nextLocale }}, window.location.origin)
    return nextLocale
  }}

  function subscribe (callback) {{
    const handleStorage = event => {{
      if (event.key === 'app_locale') callback(normalize(event.newValue))
    }}
    const handleMessage = event => {{
      if (event.origin === window.location.origin && event.data?.type === 'app-locale-change') {{
        callback(normalize(event.data.locale))
      }}
    }}
    window.addEventListener('storage', handleStorage)
    window.addEventListener('message', handleMessage)
    return () => {{
      window.removeEventListener('storage', handleStorage)
      window.removeEventListener('message', handleMessage)
    }}
  }}

  window.appI18n = {{ getLocale, messages, setLocale, subscribe }}
}})()
''',
        "api.js": f'''const API_BASE = {api_base!r}

async function request (path, options = {{}}) {{
  const response = await fetch(`${{API_BASE}}${{path}}`, {{
    headers: {{
      'Content-Type': 'application/json',
      ...(options.headers || {{}})
    }},
    ...options
  }})

  if (!response.ok) {{
    let message = `HTTP ${{response.status}}`
    try {{
      const data = await response.json()
      message = data.message || message
    }} catch (error) {{
      void error
    }}
    throw new Error(message)
  }}

  return response.status === 204 ? null : response.json()
}}

window.api = {{
  request
}}
''',
        "app.css": '''html,
body,
#q-app {
  min-height: 100%;
}

body {
  margin: 0;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
'''
    }


def main():
    parser = argparse.ArgumentParser(description="Create a Vue 3 + Quasar UMD project skeleton")
    parser.add_argument("project_dir", nargs="?", default=".")
    parser.add_argument("--title", default=None)
    parser.add_argument("--api-base", default="/api")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).expanduser().resolve()
    project_dir.mkdir(parents=True, exist_ok=True)
    project_name = project_dir.name or "quasar-umd-app"
    title = args.title or project_name
    files = template_files(project_name, title, args.api_base)
    created = []
    skipped = []

    (project_dir / "vendor").mkdir(exist_ok=True)
    for relative_path, content in files.items():
        target = project_dir / relative_path
        if target.exists() and not args.overwrite:
            skipped.append(relative_path)
            continue
        target.write_text(content, encoding="utf-8")
        created.append(relative_path)

    print(f"Project: {project_dir}")
    print("Created: " + (", ".join(created) if created else "none"))
    print("Skipped: " + (", ".join(skipped) if skipped else "none"))
    update_script = Path(__file__).with_name("update_vendor.py").resolve()
    print("Next: python3 " + os.fspath(update_script) + " " + os.fspath(project_dir))


if __name__ == "__main__":
    main()
