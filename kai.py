#!/usr/bin/env python3

import sys
import os
import re
import stat
import shutil
import tarfile
import hashlib
import tempfile
import subprocess
import urllib.request
from pathlib import Path


# -------------------------------------------------
# PATHS
# -------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
HOME_DIR = Path.home()

CONFIG_DIR = (
    Path(
        os.environ.get(
            "XDG_CONFIG_HOME",
            HOME_DIR / ".config",
        )
    )
    / "kai"
)

DATA_DIR = (
    Path(
        os.environ.get(
            "XDG_DATA_HOME",
            HOME_DIR / ".local/share",
        )
    )
    / "kai"
)

STATE_DIR = (
    Path(
        os.environ.get(
            "XDG_STATE_HOME",
            HOME_DIR / ".local/state",
        )
    )
    / "kai"
)

CACHE_DIR = (
    Path(
        os.environ.get(
            "XDG_CACHE_HOME",
            HOME_DIR / ".cache",
        )
    )
    / "kai"
)

LOCAL_RECIPES_DIR = BASE_DIR / "recipes"

REMOTE_REPO_DIR = DATA_DIR / "repo"
REMOTE_RECIPES_DIR = REMOTE_REPO_DIR / "recipes"

BUILD_DIR = CACHE_DIR / "build"
DATABASE_DIR = STATE_DIR / "database"
CONFIG_FILE = CONFIG_DIR / "kai.conf"

DEFAULT_REPO_URL = (
    "https://github.com/"
    "KairoPackage/kairo-repo.git"
)

SELF_UPDATE_URL = (
    "https://raw.githubusercontent.com/"
    "KairoPackage/kairo-repo/main/kai.py"
)


# -------------------------------------------------
# HELP
# -------------------------------------------------

def show_help():
    print("Kairo Package Manager")
    print()
    print("Usage:")
    print("  kai search <package>")
    print("  kai available")
    print("  kai info <package>")
    print("  kai install <package>")
    print("  kai update [package]")
    print("  kai checkupdates")
    print("  kai remove <package>")
    print("  kai list")
    print("  kai sync [repo-url]")
    print("  kai self-update")


# -------------------------------------------------
# CONFIG
# -------------------------------------------------

def read_config():
    config = {}

    if not CONFIG_FILE.exists():
        return config

    with open(CONFIG_FILE, "r") as file:
        for line in file:
            line = line.strip()

            if not line:
                continue

            if line.startswith("#"):
                continue

            if "=" not in line:
                continue

            key, value = line.split("=", 1)

            config[key.strip()] = value.strip()

    return config


def write_repo_url(url):
    CONFIG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    config = read_config()
    config["repo"] = url

    with open(CONFIG_FILE, "w") as file:
        for key, value in config.items():
            file.write(
                f"{key}={value}\n"
            )


# -------------------------------------------------
# REPOSITORY
# -------------------------------------------------

def sync_repository(url=None):
    if url:
        write_repo_url(url)

    config = read_config()

    repo_url = config.get(
        "repo",
        DEFAULT_REPO_URL,
    )

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        f"Repository: {repo_url}"
    )
    print()

    if (
        REMOTE_REPO_DIR / ".git"
    ).exists():

        print(
            "Updating Kai repository..."
        )

        try:
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(REMOTE_REPO_DIR),
                    "pull",
                    "--ff-only",
                ],
                check=True,
            )

        except subprocess.CalledProcessError:
            print(
                "Repository update failed."
            )
            return False

    else:
        if REMOTE_REPO_DIR.exists():
            shutil.rmtree(
                REMOTE_REPO_DIR
            )

        print(
            "Downloading Kai repository..."
        )

        try:
            subprocess.run(
                [
                    "git",
                    "clone",
                    repo_url,
                    str(REMOTE_REPO_DIR),
                ],
                check=True,
            )

        except subprocess.CalledProcessError:
            print(
                "Repository clone failed."
            )
            return False

    if not REMOTE_RECIPES_DIR.exists():
        print()
        print(
            "Repository synced, but it "
            "has no recipes/ directory."
        )
        return False

    count = len(
        list(
            REMOTE_RECIPES_DIR.glob(
                "*.kai"
            )
        )
    )

    print()
    print(
        f"Sync complete. "
        f"{count} recipes available."
    )

    return True


# -------------------------------------------------
# SELF UPDATE
# -------------------------------------------------

def self_update():
    current_file = Path(
        __file__
    ).resolve()

    print(
        "Checking for Kai update..."
    )

    print(
        f"Current file: {current_file}"
    )

    print()

    temp_dir = Path(
        tempfile.mkdtemp(
            prefix="kai-update-"
        )
    )

    new_file = (
        temp_dir / "kai.py"
    )

    backup_file = (
        temp_dir / "kai.py.backup"
    )

    try:
        print(
            "Downloading latest Kai..."
        )

        urllib.request.urlretrieve(
            SELF_UPDATE_URL,
            new_file,
        )

        if not new_file.exists():
            print(
                "Update failed: "
                "downloaded file is missing."
            )
            return False

        if new_file.stat().st_size == 0:
            print(
                "Update failed: "
                "downloaded file is empty."
            )
            return False

        with open(
            new_file,
            "r",
            encoding="utf-8",
        ) as file:

            first_line = (
                file.readline().strip()
            )

        if not first_line.startswith("#!"):
            print(
                "Update failed: downloaded "
                "file does not look like Kai."
            )
            return False

        shutil.copy2(
            current_file,
            backup_file,
        )

        try:
            subprocess.run(
                [
                    "sudo",
                    "install",
                    "-m",
                    "755",
                    str(new_file),
                    str(current_file),
                ],
                check=True,
            )

        except subprocess.CalledProcessError:
            print(
                "Update replacement failed."
            )

            try:
                subprocess.run(
                    [
                        "sudo",
                        "install",
                        "-m",
                        "755",
                        str(backup_file),
                        str(current_file),
                    ],
                    check=True,
                )

            except subprocess.CalledProcessError:
                print(
                    "Warning: restore failed."
                )

            return False

        print()
        print(
            "Kai updated successfully."
        )

        return True

    except Exception as error:
        print(
            f"Self-update failed: {error}"
        )

        return False

    finally:
        shutil.rmtree(
            temp_dir,
            ignore_errors=True,
        )


# -------------------------------------------------
# RECIPES
# -------------------------------------------------

def recipe_paths():
    paths = []

    if LOCAL_RECIPES_DIR.exists():
        paths.append(
            LOCAL_RECIPES_DIR
        )

    if REMOTE_RECIPES_DIR.exists():
        paths.append(
            REMOTE_RECIPES_DIR
        )

    return paths


def find_recipe(name):
    local = (
        LOCAL_RECIPES_DIR
        / f"{name}.kai"
    )

    if local.exists():
        return local

    remote = (
        REMOTE_RECIPES_DIR
        / f"{name}.kai"
    )

    if remote.exists():
        return remote

    return None


def read_recipe(name):
    recipe_path = find_recipe(
        name
    )

    if recipe_path is None:
        print(
            f"Package not found: {name}"
        )
        return None

    package = {}

    with open(
        recipe_path,
        "r",
    ) as file:

        for line in file:
            line = line.strip()

            if not line:
                continue

            if line.startswith("#"):
                continue

            if "=" not in line:
                continue

            key, value = line.split(
                "=",
                1,
            )

            package[
                key.strip()
            ] = value.strip()

    package[
        "_recipe_path"
    ] = str(recipe_path)

    return package


def all_recipe_names():
    names = set()

    for directory in recipe_paths():
        for recipe in directory.glob(
            "*.kai"
        ):
            names.add(
                recipe.stem
            )

    return sorted(names)


def parse_list(value):
    if not value:
        return []

    items = []

    for item in value.split(","):
        item = item.strip()

        if item:
            items.append(
                item
            )

    return items


def parse_dependencies(package):
    return parse_list(
        package.get(
            "depends",
            "",
        )
    )


def parse_system_dependencies(package):
    return parse_list(
        package.get(
            "system_depends",
            "",
        )
    )


def is_binary_package(package):
    value = package.get(
        "binary",
        "",
    ).strip().lower()

    return value in (
        "true",
        "yes",
        "1",
    )


# -------------------------------------------------
# SEARCH / AVAILABLE
# -------------------------------------------------

def search_package(name):
    matches = [
        package
        for package
        in all_recipe_names()
        if name.lower()
        in package.lower()
    ]

    if not matches:
        print(
            f"No package found matching: "
            f"{name}"
        )
        return

    for package in matches:
        recipe = read_recipe(
            package
        )

        if not recipe:
            continue

        version = recipe.get(
            "version",
            "unknown",
        )

        print(
            f"{package} {version}"
        )


def available_packages():
    packages = all_recipe_names()

    if not packages:
        print(
            "No packages available."
        )
        return

    print(
        f"Available packages "
        f"({len(packages)}):"
    )
    print()

    for name in packages:
        recipe = read_recipe(
            name
        )

        if not recipe:
            continue

        version = recipe.get(
            "version",
            "unknown",
        )

        installed = read_database(
            name
        )

        binary_text = ""

        if is_binary_package(
            recipe
        ):
            binary_text = " [binary]"

        if installed:
            print(
                f"{name} "
                f"{version}"
                f"{binary_text} "
                f"[installed]"
            )

        else:
            print(
                f"{name} "
                f"{version}"
                f"{binary_text}"
            )


# -------------------------------------------------
# VERSION
# -------------------------------------------------

def version_key(version):
    version = version.strip()

    if version.startswith("v"):
        version = version[1:]

    parts = re.findall(
        r"\d+|[A-Za-z]+",
        version,
    )

    result = []

    for part in parts:
        if part.isdigit():
            result.append(
                (
                    1,
                    int(part),
                )
            )
        else:
            result.append(
                (
                    0,
                    part.lower(),
                )
            )

    return tuple(result)


def compare_versions(
    version_a,
    version_b,
):
    a = version_key(
        version_a
    )

    b = version_key(
        version_b
    )

    if a < b:
        return -1

    if a > b:
        return 1

    return 0


# -------------------------------------------------
# DATABASE
# -------------------------------------------------

def read_database(name):
    database_file = (
        DATABASE_DIR / name
    )

    if not database_file.exists():
        return None

    package = {
        "files": []
    }

    with open(
        database_file,
        "r",
    ) as file:

        for line in file:
            line = line.strip()

            if not line:
                continue

            if "=" not in line:
                continue

            key, value = line.split(
                "=",
                1,
            )

            if key == "file":
                package[
                    "files"
                ].append(
                    value
                )

            else:
                package[
                    key
                ] = value

    return package


def write_database(
    package,
    files,
):
    DATABASE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    name = package.get(
        "name"
    )

    version = package.get(
        "version"
    )

    database_file = (
        DATABASE_DIR / name
    )

    with open(
        database_file,
        "w",
    ) as file:

        file.write(
            f"name={name}\n"
        )

        file.write(
            f"version={version}\n"
        )

        file.write("\n")

        for filename in files:
            file.write(
                f"file={filename}\n"
            )


# -------------------------------------------------
# INFO
# -------------------------------------------------

def info_package(name):
    recipe = read_recipe(
        name
    )

    if recipe is None:
        return

    installed = read_database(
        name
    )

    dependencies = (
        parse_dependencies(
            recipe
        )
    )

    system_dependencies = (
        parse_system_dependencies(
            recipe
        )
    )

    package_type = (
        "binary"
        if is_binary_package(recipe)
        else "source"
    )

    print(
        f"Package:   "
        f"{recipe.get('name', name)}"
    )

    print(
        f"Version:   "
        f"{recipe.get('version', 'unknown')}"
    )

    print(
        f"Type:      "
        f"{package_type}"
    )

    print(
        f"Source:    "
        f"{recipe.get('source', 'none')}"
    )

    print(
        f"SHA256:    "
        f"{recipe.get('sha256', 'none')}"
    )

    print(
        f"Build:     "
        f"{recipe.get('build', 'none')}"
    )

    print(
        f"Install:   "
        f"{recipe.get('install', 'none')}"
    )

    if dependencies:
        print(
            f"Depends:   "
            f"{', '.join(dependencies)}"
        )

    else:
        print(
            "Depends:   none"
        )

    if system_dependencies:
        print(
            f"System:    "
            f"{', '.join(system_dependencies)}"
        )

    else:
        print(
            "System:    none"
        )

    print(
        f"Recipe:    "
        f"{recipe.get('_recipe_path')}"
    )

    if installed:
        print(
            "Installed: yes"
        )

        print(
            f"Installed version: "
            f"{installed.get('version', 'unknown')}"
        )

        print(
            f"Tracked files: "
            f"{len(installed.get('files', []))}"
        )

    else:
        print(
            "Installed: no"
        )


# -------------------------------------------------
# SYSTEM DEPENDENCIES
# -------------------------------------------------

def check_system_dependencies(
    package,
):
    dependencies = (
        parse_system_dependencies(
            package
        )
    )

    if not dependencies:
        return True

    print()
    print(
        "Checking system dependencies..."
    )

    missing = []

    for dependency in dependencies:
        location = shutil.which(
            dependency
        )

        if location:
            print(
                f"  {dependency}: "
                f"found ({location})"
            )

        else:
            print(
                f"  {dependency}: missing"
            )

            missing.append(
                dependency
            )

    if missing:
        print()
        print(
            "Missing system dependencies:"
        )

        for dependency in missing:
            print(
                f"  {dependency}"
            )

        print()

        print(
            "Install them with your "
            "system package manager first."
        )

        return False

    return True


# -------------------------------------------------
# DOWNLOAD / VERIFY
# -------------------------------------------------

def download_source(package):
    name = package.get(
        "name"
    )

    version = package.get(
        "version"
    )

    source = package.get(
        "source"
    )

    if not source:
        print(
            "Recipe has no source URL."
        )
        return None

    BUILD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    package_dir = (
        BUILD_DIR
        / f"{name}-{version}"
    )

    package_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    filename = source.split(
        "/"
    )[-1]

    if not filename:
        filename = (
            f"{name}.tar.gz"
        )

    destination = (
        package_dir
        / filename
    )

    print()
    print(
        f"Downloading "
        f"{name} {version}..."
    )

    print(
        f"Source: {source}"
    )

    try:
        urllib.request.urlretrieve(
            source,
            destination,
        )

    except Exception as error:
        print(
            f"Download failed: "
            f"{error}"
        )

        return None

    print(
        "Download complete."
    )

    return destination


def calculate_sha256(
    file_path,
):
    sha256 = hashlib.sha256()

    with open(
        file_path,
        "rb",
    ) as file:

        while True:
            chunk = file.read(
                1024 * 1024
            )

            if not chunk:
                break

            sha256.update(
                chunk
            )

    return sha256.hexdigest()


def verify_source(
    package,
    archive,
):
    expected = package.get(
        "sha256"
    )

    if not expected:
        print()
        print(
            "Warning: recipe has no "
            "SHA256 checksum."
        )
        print(
            "Skipping source verification."
        )
        return True

    print()
    print(
        "Verifying SHA256..."
    )

    try:
        actual = calculate_sha256(
            archive
        )

    except OSError as error:
        print(
            f"Could not read downloaded "
            f"file: {error}"
        )
        return False

    if (
        actual.lower()
        != expected.lower()
    ):
        print()
        print(
            "SHA256 verification FAILED."
        )
        print(
            f"Expected: {expected}"
        )
        print(
            f"Actual:   {actual}"
        )
        print()
        print(
            "Kai will not build "
            "this package."
        )
        return False

    print(
        "SHA256 verified."
    )

    return True


# -------------------------------------------------
# EXTRACTION
# -------------------------------------------------

def extract_source(
    archive,
    package,
):
    name = package.get(
        "name"
    )

    version = package.get(
        "version"
    )

    extract_dir = (
        BUILD_DIR
        / f"{name}-{version}"
        / "source"
    )

    if extract_dir.exists():
        shutil.rmtree(
            extract_dir
        )

    extract_dir.mkdir(
        parents=True
    )

    print()
    print(
        f"Extracting "
        f"{archive.name}..."
    )

    try:
        with tarfile.open(
            archive,
            "r:*",
        ) as tar:

            tar.extractall(
                extract_dir,
                filter="data",
            )

    except (
        tarfile.TarError,
        OSError,
    ) as error:

        print(
            f"Extraction failed: "
            f"{error}"
        )

        return None

    print(
        "Extraction complete."
    )

    return extract_dir


def find_source_dir(
    extract_dir,
):
    directories = [
        path
        for path
        in extract_dir.iterdir()
        if path.is_dir()
    ]

    files = [
        path
        for path
        in extract_dir.iterdir()
        if path.is_file()
    ]

    if (
        len(directories) == 1
        and not files
    ):
        return directories[0]

    return extract_dir


def select_package_root(
    package,
    extract_dir,
):
    if is_binary_package(
        package
    ):
        return extract_dir

    return find_source_dir(
        extract_dir
    )


# -------------------------------------------------
# BUILD
# -------------------------------------------------

def build_package(
    package,
    source_dir,
):
    if is_binary_package(
        package
    ):
        print()
        print(
            "Binary package: "
            "skipping build."
        )

        return True

    build_command = package.get(
        "build"
    )

    if not build_command:
        print(
            "No build command in recipe."
        )

        return False

    print()
    print(
        f"Building "
        f"{package.get('name')}..."
    )

    print(
        f"Command: "
        f"{build_command}"
    )

    print()

    try:
        subprocess.run(
            build_command,
            shell=True,
            cwd=source_dir,
            check=True,
        )

    except subprocess.CalledProcessError as error:
        print()
        print(
            f"Build failed with exit code "
            f"{error.returncode}"
        )
        return False

    print()
    print(
        "Build complete."
    )

    return True


# -------------------------------------------------
# STAGING
# -------------------------------------------------

def stage_package(
    package,
    source_dir,
):
    name = package.get(
        "name"
    )

    version = package.get(
        "version"
    )

    install_command = package.get(
        "install"
    )

    if not install_command:
        print(
            "Recipe has no install command."
        )
        return None

    stage_dir = (
        BUILD_DIR
        / f"{name}-{version}"
        / "pkg"
    )

    if stage_dir.exists():
        shutil.rmtree(
            stage_dir
        )

    stage_dir.mkdir(
        parents=True
    )

    env = os.environ.copy()

    env["DESTDIR"] = str(
        stage_dir
    )

    print()
    print(
        f"Staging {name}..."
    )

    print(
        f"Command: "
        f"{install_command}"
    )

    print(
        f"DESTDIR: "
        f"{stage_dir}"
    )

    print()

    try:
        subprocess.run(
            install_command,
            shell=True,
            cwd=source_dir,
            env=env,
            check=True,
        )

    except subprocess.CalledProcessError as error:
        print()
        print(
            f"Staging failed with "
            f"exit code "
            f"{error.returncode}"
        )
        return None

    print()
    print(
        "Staging complete."
    )

    return stage_dir


def get_staged_files(
    stage_dir,
):
    files = []

    for path in stage_dir.rglob(
        "*"
    ):

        if (
            path.is_file()
            or path.is_symlink()
        ):
            relative = (
                path.relative_to(
                    stage_dir
                )
            )

            files.append(
                "/" + str(relative)
            )

    return sorted(files)


# -------------------------------------------------
# CONFLICTS
# -------------------------------------------------

def check_install_conflicts(
    files,
):
    conflicts = []

    for filename in files:
        path = Path(
            filename
        )

        if (
            path.exists()
            or path.is_symlink()
        ):
            conflicts.append(
                filename
            )

    return conflicts


def check_update_conflicts(
    new_files,
    old_files,
):
    conflicts = []

    owned = set(
        old_files
    )

    for filename in new_files:
        path = Path(
            filename
        )

        exists = (
            path.exists()
            or path.is_symlink()
        )

        if (
            exists
            and filename not in owned
        ):
            conflicts.append(
                filename
            )

    return conflicts


# -------------------------------------------------
# SAFE INSTALL
# -------------------------------------------------

def mode_string(path):
    return format(
        stat.S_IMODE(
            path.lstat().st_mode
        ),
        "o",
    )


def safely_create_directory(
    source,
    destination,
):
    if destination.exists():
        return

    mode = mode_string(
        source
    )

    subprocess.run(
        [
            "sudo",
            "install",
            "-d",
            "-m",
            mode,
            str(destination),
        ],
        check=True,
    )


def safely_install_file(
    source,
    destination,
):
    if not destination.parent.exists():
        subprocess.run(
            [
                "sudo",
                "install",
                "-d",
                str(
                    destination.parent
                ),
            ],
            check=True,
        )

    mode = mode_string(
        source
    )

    subprocess.run(
        [
            "sudo",
            "install",
            "-m",
            mode,
            str(source),
            str(destination),
        ],
        check=True,
    )


def safely_install_symlink(
    source,
    destination,
):
    target = os.readlink(
        source
    )

    if not destination.parent.exists():
        subprocess.run(
            [
                "sudo",
                "install",
                "-d",
                str(
                    destination.parent
                ),
            ],
            check=True,
        )

    subprocess.run(
        [
            "sudo",
            "ln",
            "-sfn",
            target,
            str(destination),
        ],
        check=True,
    )


def copy_stage_to_system(
    stage_dir,
):
    print()
    print(
        "Installing staged files safely..."
    )

    paths = sorted(
        stage_dir.rglob(
            "*"
        ),
        key=lambda path: (
            len(path.parts),
            str(path),
        ),
    )

    try:
        for source in paths:
            relative = (
                source.relative_to(
                    stage_dir
                )
            )

            destination = (
                Path("/")
                / relative
            )

            if source.is_symlink():
                print(
                    f"  link "
                    f"{destination}"
                )

                safely_install_symlink(
                    source,
                    destination,
                )

            elif source.is_dir():
                safely_create_directory(
                    source,
                    destination,
                )

            elif source.is_file():
                print(
                    f"  file "
                    f"{destination}"
                )

                safely_install_file(
                    source,
                    destination,
                )

    except subprocess.CalledProcessError:
        print()
        print(
            "System install failed."
        )
        return False

    return True


# -------------------------------------------------
# LDCONFIG
# -------------------------------------------------

def refresh_linker_cache():
    print()
    print(
        "Refreshing linker cache..."
    )

    try:
        subprocess.run(
            [
                "sudo",
                "ldconfig",
            ],
            check=True,
        )

    except subprocess.CalledProcessError:
        print(
            "Warning: ldconfig failed."
        )
        return False

    print(
        "Linker cache refreshed."
    )

    return True


# -------------------------------------------------
# PACKAGE PREPARATION
# -------------------------------------------------

def prepare_package(package):
    if not check_system_dependencies(
        package
    ):
        return None

    downloaded = download_source(
        package
    )

    if downloaded is None:
        return None

    if not verify_source(
        package,
        downloaded,
    ):
        return None

    extracted = extract_source(
        downloaded,
        package,
    )

    if extracted is None:
        return None

    source_dir = select_package_root(
        package,
        extracted,
    )

    if not build_package(
        package,
        source_dir,
    ):
        return None

    return stage_package(
        package,
        source_dir,
    )


# -------------------------------------------------
# DEPENDENCIES
# -------------------------------------------------

def install_dependencies(
    package,
    dependency_stack,
):
    dependencies = (
        parse_dependencies(
            package
        )
    )

    if not dependencies:
        return True

    print()
    print(
        "Checking Kai dependencies..."
    )

    for dependency in dependencies:

        if dependency in dependency_stack:
            print()
            print(
                "Dependency cycle detected:"
            )

            chain = (
                dependency_stack
                + [dependency]
            )

            print(
                " -> ".join(
                    chain
                )
            )

            return False

        installed = read_database(
            dependency
        )

        if installed:
            print(
                f"  {dependency}: "
                f"installed"
            )

            continue

        dependency_recipe = (
            read_recipe(
                dependency
            )
        )

        if dependency_recipe is None:
            print()
            print(
                f"Missing dependency recipe: "
                f"{dependency}"
            )
            return False

        print(
            f"  {dependency}: "
            f"installing"
        )

        if not install_package(
            dependency,
            dependency_stack,
        ):
            return False

    return True


# -------------------------------------------------
# INSTALL
# -------------------------------------------------

def install_to_system(
    package,
    stage_dir,
):
    files = get_staged_files(
        stage_dir
    )

    if not files:
        print(
            "No files were staged."
        )
        return False

    print()
    print(
        "Files to install:"
    )

    for filename in files:
        print(
            f"  {filename}"
        )

    conflicts = (
        check_install_conflicts(
            files
        )
    )

    if conflicts:
        print()
        print(
            "Install stopped."
        )
        print(
            "These files already exist:"
        )

        for filename in conflicts:
            print(
                f"  {filename}"
            )

        print()
        print(
            "Kai will not overwrite them."
        )

        return False

    if not copy_stage_to_system(
        stage_dir
    ):
        return False

    write_database(
        package,
        files,
    )

    refresh_linker_cache()

    print()
    print(
        f"Installed "
        f"{package.get('name')} "
        f"{package.get('version')} "
        f"successfully."
    )

    return True


def install_package(
    name,
    dependency_stack=None,
):
    if dependency_stack is None:
        dependency_stack = []

    package = read_recipe(
        name
    )

    if package is None:
        return False

    package_name = package.get(
        "name",
        name,
    )

    version = package.get(
        "version",
        "unknown",
    )

    package_type = (
        "binary"
        if is_binary_package(package)
        else "source"
    )

    print()
    print(
        f"Package: "
        f"{package_name}"
    )

    print(
        f"Version: "
        f"{version}"
    )

    print(
        f"Type: "
        f"{package_type}"
    )

    if read_database(
        package_name
    ):
        print()
        print(
            f"{package_name} is already "
            f"installed by Kai."
        )
        return True

    current_stack = (
        dependency_stack
        + [package_name]
    )

    if not install_dependencies(
        package,
        current_stack,
    ):
        return False

    stage_dir = prepare_package(
        package
    )

    if stage_dir is None:
        return False

    return install_to_system(
        package,
        stage_dir,
    )


# -------------------------------------------------
# UPDATE
# -------------------------------------------------

def remove_old_update_files(
    old_files,
    new_files,
):
    new_set = set(
        new_files
    )

    obsolete = [
        filename
        for filename
        in old_files
        if filename not in new_set
    ]

    for filename in reversed(
        obsolete
    ):
        path = Path(
            filename
        )

        if (
            not path.exists()
            and not path.is_symlink()
        ):
            continue

        print(
            f"  removing obsolete "
            f"{filename}"
        )

        try:
            subprocess.run(
                [
                    "sudo",
                    "rm",
                    "-f",
                    filename,
                ],
                check=True,
            )

        except subprocess.CalledProcessError:
            print(
                f"Failed to remove: "
                f"{filename}"
            )
            return False

    return True


def update_package(name):
    installed = read_database(
        name
    )

    if installed is None:
        print(
            f"{name} is not "
            f"installed by Kai."
        )
        return False

    recipe = read_recipe(
        name
    )

    if recipe is None:
        return False

    old_version = installed.get(
        "version",
        "unknown",
    )

    new_version = recipe.get(
        "version",
        "unknown",
    )

    print(
        f"Package:   {name}"
    )

    print(
        f"Installed: {old_version}"
    )

    print(
        f"Recipe:    {new_version}"
    )

    comparison = compare_versions(
        old_version,
        new_version,
    )

    if comparison == 0:
        print()
        print(
            f"{name} is already "
            f"up to date."
        )
        return True

    if comparison > 0:
        print()
        print(
            "Installed version is newer "
            "than the recipe."
        )
        print(
            "Kai will not downgrade it."
        )
        return False

    print()
    print(
        f"Updating {name}: "
        f"{old_version} -> "
        f"{new_version}"
    )

    if not install_dependencies(
        recipe,
        [name],
    ):
        return False

    stage_dir = prepare_package(
        recipe
    )

    if stage_dir is None:
        return False

    new_files = get_staged_files(
        stage_dir
    )

    old_files = installed.get(
        "files",
        [],
    )

    conflicts = (
        check_update_conflicts(
            new_files,
            old_files,
        )
    )

    if conflicts:
        print()
        print(
            "Update stopped."
        )
        print(
            "Conflicting files:"
        )

        for filename in conflicts:
            print(
                f"  {filename}"
            )

        return False

    if not copy_stage_to_system(
        stage_dir
    ):
        return False

    if not remove_old_update_files(
        old_files,
        new_files,
    ):
        return False

    write_database(
        recipe,
        new_files,
    )

    refresh_linker_cache()

    print()
    print(
        f"Updated {name} "
        f"{old_version} -> "
        f"{new_version}."
    )

    return True


def update_all_packages():
    if not DATABASE_DIR.exists():
        print(
            "No packages installed by Kai."
        )
        return

    packages = sorted(
        path.name
        for path
        in DATABASE_DIR.iterdir()
        if path.is_file()
    )

    updated = 0

    for name in packages:
        installed = read_database(
            name
        )

        recipe = read_recipe(
            name
        )

        if (
            not installed
            or not recipe
        ):
            continue

        old_version = installed.get(
            "version",
            "unknown",
        )

        new_version = recipe.get(
            "version",
            "unknown",
        )

        if compare_versions(
            old_version,
            new_version,
        ) < 0:

            if update_package(
                name
            ):
                updated += 1

    if updated == 0:
        print(
            "All Kai packages "
            "are up to date."
        )


# -------------------------------------------------
# CHECK UPDATES
# -------------------------------------------------

def check_updates():
    if not DATABASE_DIR.exists():
        print(
            "No packages installed by Kai."
        )
        return

    packages = sorted(
        path.name
        for path
        in DATABASE_DIR.iterdir()
        if path.is_file()
    )

    updates = []

    for name in packages:
        installed = read_database(
            name
        )

        recipe = read_recipe(
            name
        )

        if (
            not installed
            or not recipe
        ):
            continue

        old_version = installed.get(
            "version",
            "unknown",
        )

        new_version = recipe.get(
            "version",
            "unknown",
        )

        if compare_versions(
            old_version,
            new_version,
        ) < 0:

            updates.append(
                (
                    name,
                    old_version,
                    new_version,
                )
            )

    if not updates:
        print(
            "All Kai packages "
            "are up to date."
        )
        return

    print(
        "Available updates:"
    )
    print()

    for (
        name,
        old,
        new,
    ) in updates:

        print(
            f"{name}  "
            f"{old} -> {new}"
        )


# -------------------------------------------------
# LIST
# -------------------------------------------------

def list_packages():
    if not DATABASE_DIR.exists():
        print(
            "No packages installed by Kai."
        )
        return

    packages = sorted(
        path.name
        for path
        in DATABASE_DIR.iterdir()
        if path.is_file()
    )

    if not packages:
        print(
            "No packages installed by Kai."
        )
        return

    print(
        f"Installed packages "
        f"({len(packages)}):"
    )
    print()

    for name in packages:
        package = read_database(
            name
        )

        print(
            f"{package.get('name')} "
            f"{package.get('version')}"
        )


# -------------------------------------------------
# REMOVE
# -------------------------------------------------

def remove_package(name):
    package = read_database(
        name
    )

    if package is None:
        print(
            f"{name} is not "
            f"installed by Kai."
        )
        return

    print(
        f"Removing "
        f"{package.get('name')} "
        f"{package.get('version')}..."
    )

    for filename in reversed(
        package.get(
            "files",
            [],
        )
    ):

        path = Path(
            filename
        )

        if (
            not path.exists()
            and not path.is_symlink()
        ):
            continue

        print(
            f"  removing "
            f"{filename}"
        )

        try:
            subprocess.run(
                [
                    "sudo",
                    "rm",
                    "-f",
                    filename,
                ],
                check=True,
            )

        except subprocess.CalledProcessError:
            print(
                f"Failed to remove "
                f"{filename}"
            )
            return

    (
        DATABASE_DIR
        / name
    ).unlink()

    refresh_linker_cache()

    print()
    print(
        f"Removed {name} "
        f"successfully."
    )


# -------------------------------------------------
# MAIN
# -------------------------------------------------

def main():
    if len(sys.argv) < 2:
        show_help()
        return

    command = sys.argv[1]

    if command in (
        "--help",
        "-h",
        "help",
    ):
        show_help()

    elif command == "search":
        if len(sys.argv) < 3:
            print(
                "Usage: "
                "kai search <package>"
            )
            return

        search_package(
            sys.argv[2]
        )

    elif command == "available":
        available_packages()

    elif command == "info":
        if len(sys.argv) < 3:
            print(
                "Usage: "
                "kai info <package>"
            )
            return

        info_package(
            sys.argv[2]
        )

    elif command == "install":
        if len(sys.argv) < 3:
            print(
                "Usage: "
                "kai install <package>"
            )
            return

        install_package(
            sys.argv[2]
        )

    elif command == "update":
        if len(sys.argv) >= 3:
            update_package(
                sys.argv[2]
            )
        else:
            update_all_packages()

    elif command == "checkupdates":
        check_updates()

    elif command == "remove":
        if len(sys.argv) < 3:
            print(
                "Usage: "
                "kai remove <package>"
            )
            return

        remove_package(
            sys.argv[2]
        )

    elif command == "list":
        list_packages()

    elif command == "sync":
        if len(sys.argv) >= 3:
            sync_repository(
                sys.argv[2]
            )
        else:
            sync_repository()

    elif command == "self-update":
        self_update()

    else:
        print(
            f"Unknown command: "
            f"{command}"
        )

        print()
        show_help()


if __name__ == "__main__":
    main()
