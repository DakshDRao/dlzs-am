# Build the DLZS board-test application with the Vitis Python API (no GUI).
# Safe to re-run: an existing platform/app is reused, and the sources are
# re-copied from SRC_DIR into the app before every build.
#
#   C:\AMDDesignTools\2025.2\Vitis\bin\vitis.bat -s <path>\build_vitis.py
#
# Edit the three paths below. Use forward slashes.

import os
import shutil
import sys
import vitis

XSA = "C:/projects/major_project/vitis_wrk/dlzs_edge/dlzs_edge.xsa"
WORKSPACE = "C:/projects/major_project/vitis_wrk/dlzs_edge/ws"
SRC_DIR = "C:/projects/major_project/vitis_wrk/dlzs_edge"

PLATFORM = "edge_platform"
APP = "dlzs_test"
SOURCES = ["dlzs_board_test.c", "dlzs_vectors.h"]

for f in SOURCES:
    assert os.path.isfile(os.path.join(SRC_DIR, f)), f"missing {f} in {SRC_DIR}"
assert os.path.isfile(XSA), f"missing {XSA}"

client = vitis.create_client()
client.set_workspace(path=WORKSPACE)

xpfm = os.path.join(WORKSPACE, PLATFORM, "export", PLATFORM, PLATFORM + ".xpfm")
if os.path.isfile(xpfm):
    print("== reusing platform:", xpfm)
else:
    print("== creating platform")
    platform = client.create_platform_component(
        name=PLATFORM, hw_design=XSA, os="standalone", cpu="ps7_cortexa9_0")
    platform.build()

app_dir = os.path.join(WORKSPACE, APP)
if os.path.isdir(app_dir):
    print("== reusing application")
    app = client.get_component(name=APP)
else:
    print("== creating application")
    app = client.create_app_component(
        name=APP, platform=xpfm,
        domain="standalone_ps7_cortexa9_0", template="empty_application")

src_dst = os.path.join(app_dir, "src")
for f in SOURCES:
    shutil.copy2(os.path.join(SRC_DIR, f), os.path.join(src_dst, f))
print("== copied sources into", src_dst)

app.build()

elf = os.path.join(app_dir, "build", APP + ".elf")
vitis.dispose()
if os.path.isfile(elf):
    print("== DONE:", elf)
else:
    print("== BUILD FAILED: no", elf, "-- see the errors above")
    sys.exit(1)
