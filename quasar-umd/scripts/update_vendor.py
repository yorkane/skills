#!/usr/bin/env python3
import argparse
import hashlib
import io
import json
import os
import re
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


DEFAULT_REGISTRY = "https://registry.npmjs.org"
DEFAULT_FONT_SOURCE = "https://fonts.googleapis.com/css?family=Roboto:100,300,400,500,700,900"
DEFAULT_MDI_RANGE = "^7.0.0"
USER_AGENT = "quasar-umd-skill/1.0"
URL_PATTERN = re.compile(r"""url\(\s*(['"]?)([^)'"]+)\1\s*\)""")


def fetch_bytes(url, user_agent=USER_AGENT):
    request = Request(url, headers={"User-Agent": user_agent})
    with urlopen(request, timeout=120) as response:
        return response.read()


def fetch_json(url):
    return json.loads(fetch_bytes(url).decode("utf-8"))


def version_tuple(version):
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def package_metadata(registry, package_name, requested_version):
    encoded_name = quote(package_name, safe="")
    base_url = f"{registry.rstrip('/')}/{encoded_name}"
    if requested_version and requested_version.startswith("^"):
        range_match = re.match(r"^\^(\d+)\.(\d+)\.(\d+)$", requested_version)
        if not range_match:
            raise RuntimeError(f"Unsupported version range: {requested_version}")
        minimum = tuple(int(part) for part in range_match.groups())
        package = fetch_json(base_url)
        candidates = []
        for version in package.get("versions", {}):
            parsed = version_tuple(version)
            if parsed and parsed[0] == minimum[0] and parsed >= minimum:
                candidates.append(parsed + (version,))
        if not candidates:
            raise RuntimeError(f"No stable version matches {package_name}@{requested_version}")
        version = max(candidates)[-1]
        return package["versions"][version]
    suffix = requested_version or "latest"
    return fetch_json(f"{base_url}/{quote(suffix, safe='')}")


def open_archive(metadata):
    data = fetch_bytes(metadata["dist"]["tarball"])
    return tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")


def member_bytes(archive, candidates):
    names = {member.name: member for member in archive.getmembers()}
    for candidate in candidates:
        member = names.get(candidate)
        if member is not None and member.isfile():
            source = archive.extractfile(member)
            if source is not None:
                return source.read(), candidate
    raise RuntimeError("Package is missing required asset: " + ", ".join(candidates))


def quasar_assets(metadata):
    with open_archive(metadata) as archive:
        requests = {
            "quasar.umd.prod.js": ["package/dist/quasar.umd.prod.js"],
            "quasar.prod.css": ["package/dist/quasar.prod.css"],
            "icon-set/mdi-v7.umd.prod.js": [
                "package/dist/icon-set/mdi-v7.umd.prod.js"
            ],
            "lang/zh-CN.umd.prod.js": ["package/dist/lang/zh-CN.umd.prod.js"],
            "lang/en-US.umd.prod.js": ["package/dist/lang/en-US.umd.prod.js"],
        }
        assets = []
        for destination, candidates in requests.items():
            data, source = member_bytes(archive, candidates)
            assets.append({"path": destination, "data": data, "source": source})
        return assets


def vue_assets(metadata):
    with open_archive(metadata) as archive:
        data, source = member_bytes(
            archive,
            ["package/dist/vue.global.prod.js"],
        )
        return [{"path": "vue.global.prod.js", "data": data, "source": source}]


def mdi_assets(metadata):
    with open_archive(metadata) as archive:
        css, css_source = member_bytes(
            archive,
            ["package/css/materialdesignicons.min.css"],
        )
        assets = [{"path": "mdi.css", "data": css, "source": css_source}]
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            if not member.isfile() or path.parts[:2] != ("package", "fonts"):
                continue
            if path.suffix.lower() not in {".eot", ".svg", ".ttf", ".woff", ".woff2"}:
                continue
            source = archive.extractfile(member)
            if source is not None:
                assets.append({
                    "path": f"fonts/mdi/{path.name}",
                    "data": source.read(),
                    "source": member.name,
                })
        if len(assets) == 1:
            raise RuntimeError("Package is missing MDI font files")
        return assets


def google_font_assets(url):
    css = fetch_bytes(url, "Mozilla/5.0")
    text = css.decode("utf-8")
    assets = []
    replacements = {}
    destinations = set()
    for match in URL_PATTERN.finditer(text):
        font_url = match.group(2)
        if not font_url.startswith("http"):
            continue
        filename = Path(urlsplit(font_url).path).name
        if not filename:
            continue
        destination = f"fonts/roboto/{filename}"
        if destination not in destinations:
            assets.append({
                "path": destination,
                "data": fetch_bytes(font_url, "Mozilla/5.0"),
                "source": font_url,
            })
            destinations.add(destination)
        replacements[font_url] = f"./{destination}"
    for original, replacement in replacements.items():
        text = text.replace(original, replacement)
    assets.insert(0, {"path": "roboto.css", "data": text.encode("utf-8"), "source": url})
    return assets


def rewrite_mdi_css(data):
    text = data.decode("utf-8")
    pattern = re.compile(r"""url\(\s*(['"]?)(?:\.\./)?fonts/([^)'"]+)\1\s*\)""")
    text = pattern.sub(
        lambda match: f"url(./fonts/mdi/{Path(match.group(2).split('?')[0]).name})",
        text,
    )
    text = re.sub(r"/\*# sourceMappingURL=.*?\*/", "", text)
    return text.encode("utf-8")


def build_bundles(vue, quasar, mdi, roboto):
    js_paths = {
        "quasar.umd.prod.js",
        "icon-set/mdi-v7.umd.prod.js",
        "lang/zh-CN.umd.prod.js",
        "lang/en-US.umd.prod.js",
    }
    js_parts = [vue[0]["data"]]
    js_parts.extend(asset["data"] for asset in quasar if asset["path"] in js_paths)
    css_parts = [roboto[0]["data"], rewrite_mdi_css(mdi[0]["data"])]
    css_parts.append(next(asset["data"] for asset in quasar if asset["path"] == "quasar.prod.css"))
    return b"\n;\n".join(js_parts), b"\n".join(css_parts)


def write_staged(staging, assets, package_name):
    records = []
    for asset in assets:
        target = staging / asset["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(asset["data"])
        records.append({
            "path": asset["path"],
            "source_path": asset["source"],
            "package": package_name,
            "sha256": hashlib.sha256(asset["data"]).hexdigest(),
            "bytes": len(asset["data"]),
        })
    return records


def commit(staging, vendor, records):
    for record in records:
        source = staging / record["path"]
        target = vendor / record["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, target)


def main():
    parser = argparse.ArgumentParser(description="Bundle Vue 3 and Quasar UMD assets into a project")
    parser.add_argument("project_dir", nargs="?", default=".")
    parser.add_argument("--source", default=DEFAULT_REGISTRY)
    parser.add_argument("--font-source", default=DEFAULT_FONT_SOURCE)
    parser.add_argument("--vue-version", default=None)
    parser.add_argument("--quasar-version", default=None)
    parser.add_argument("--mdi-version", default=DEFAULT_MDI_RANGE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).expanduser().resolve()
    vendor = project_dir / "vendor"
    vendor.mkdir(parents=True, exist_ok=True)
    specs = [
        ("vue", args.vue_version),
        ("quasar", args.quasar_version),
        ("@mdi/font", args.mdi_version),
    ]
    resolved = {}
    metadata = {}
    for package_name, requested_version in specs:
        metadata[package_name] = package_metadata(args.source, package_name, requested_version)
        resolved[package_name] = {
            "version": metadata[package_name]["version"],
            "tarball": metadata[package_name]["dist"]["tarball"],
        }
        print(f"{package_name}: {metadata[package_name]['version']}")

    if args.dry_run:
        print("Dry run: no files changed")
        return

    vue = vue_assets(metadata["vue"])
    quasar = quasar_assets(metadata["quasar"])
    mdi = mdi_assets(metadata["@mdi/font"])
    roboto = google_font_assets(args.font_source)
    js_bundle, css_bundle = build_bundles(vue, quasar, mdi, roboto)
    assets = [
        {"path": "quasar-umd.js", "data": js_bundle, "source": "Vue + Quasar + lang + mdi-v7"},
        {"path": "quasar-umd.css", "data": css_bundle, "source": "Roboto + MDI + Quasar"},
    ]
    assets.extend(mdi[1:])
    assets.extend(roboto[1:])

    with tempfile.TemporaryDirectory(prefix="quasar-umd-") as temporary:
        staging = Path(temporary)
        records = write_staged(staging, assets, "bundled")
        commit(staging, vendor, records)

    manifest = {
        "format": 3,
        "source": args.source.rstrip("/"),
        "font_source": args.font_source,
        "packages": resolved,
        "bundles": {
            "js": ["vue", "quasar", "lang/zh-CN", "lang/en-US", "mdi-v7"],
            "css": ["Roboto", "MDI", "Quasar"],
        },
        "assets": records,
    }
    manifest_path = vendor / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Updated {len(records)} assets in {vendor}")


if __name__ == "__main__":
    main()
