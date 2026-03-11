#!/usr/bin/env python3

import argparse
import json
import subprocess
import sys
import os
import shlex
from pathlib import Path

# Try to import PySide6 for the GUI
try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QListWidget, QListWidgetItem, QPushButton, QInputDialog, QMessageBox, QLabel,
        QFileDialog
    )
    from PySide6.QtGui import QIcon
    from PySide6.QtCore import Qt, QSize
    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False

VERBOSE = True
DEFAULT_PROFILE_DIR = Path.home() / ".local/share/kde-display-profiles"

def log(*args):
    if VERBOSE:
        print(*args)

def run_command(cmd):
    log(f"[CMD] {cmd}")
    try:
        subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        log(f"Error executing command: {e}")

def get_mode_string(output, mode_id):
    for mode in output.get('modes', []):
        if mode['id'] == mode_id:
            width = mode['size']['width']
            height = mode['size']['height']
            refresh_rate = round(mode['refreshRate'])
            return f"{width}x{height}@{refresh_rate}"
    return None

def save_profile(profile_path):
    log(f"Saving current display profile to {profile_path}...")
    try:
        with open(profile_path, 'w') as f:
            subprocess.run(['kscreen-doctor', '--json'], stdout=f, check=True)
        log("Profile saved successfully.")
    except Exception as e:
        log(f"Error saving profile: {e}")
        raise e

def apply_attribute(output_name, attribute, value, value_map=None):
    if value is None:
        log(f"Output {output_name} has no attribute {attribute}, skipping...")
        return

    # If it's a list or dict, something might be wrong or it's a complex structure we don't handle this way
    if isinstance(value, (list, dict)):
        log(f"Output {output_name} attribute {attribute} has complex value {value}, skipping...")
        return

    str_value = str(value).lower()
    if value_map:
        if str_value in value_map:
            value = value_map[str_value]
        else:
            log(f"Warning: Value {str_value} not found in map for {attribute}, using as is.")

    cmd = f"kscreen-doctor output.{output_name}.{attribute}.{value}"
    run_command(cmd)

def load_profile(profile_path):
    log(f"Loading display profile from {profile_path}...")
    if not os.path.exists(profile_path):
        raise FileNotFoundError(f"Profile file not found: {profile_path}")

    try:
        with open(profile_path, 'r') as f:
            profile = json.load(f)
    except Exception as e:
        log(f"Error reading profile JSON: {e}")
        raise e

    outputs = profile.get('outputs', [])
    commands = []

    # Maps from JSON values to kscreen-doctor options
    bool_enable_map = {"true": "enable", "false": "disable"}
    bool_allow_map = {"true": "allow", "false": "disallow"}
    rgb_range_map = {
        "0": "automatic", "1": "full", "2": "limited",
        "automatic": "automatic", "full": "full", "limited": "limited"
    }
    rotation_map = {"1": "normal", "2": "left", "4": "inverted", "8": "right"}
    vrr_policy_map = {
        "0": "never", "1": "always", "2": "automatic",
        "never": "never", "always": "always", "automatic": "automatic"
    }

    def add_attr(output_name, attribute, value, value_map=None):
        if value is None:
            return
        if isinstance(value, (list, dict)):
            return
        
        str_value = str(value).lower()
        if value_map:
            if str_value in value_map:
                value = value_map[str_value]
        
        commands.append(f"output.{output_name}.{attribute}.{value}")

    # 1. Handle Enable/Disable
    for out in outputs:
        status = "enable" if out.get('enabled') else "disable"
        commands.append(f"output.{out['name']}.{status}")

    # 2. Collect other attributes
    for out in outputs:
        name = out['name']
        
        # WCG
        add_attr(name, "wcg", out.get('wcg'), bool_enable_map)
        # SDR Brightness
        add_attr(name, "sdr-brightness", out.get('sdr-brightness'))
        # VRR Policy
        add_attr(name, "vrrpolicy", out.get('vrrPolicy'), vrr_policy_map)
        # RGB Range
        add_attr(name, "rgbrange", out.get('rgbRange'), rgb_range_map)
        # Overscan
        add_attr(name, "overscan", out.get('overscan'))
        # HDR
        add_attr(name, "hdr", out.get('hdr'), bool_enable_map)
        
        # Brightness
        brightness = out.get('brightness')
        if brightness is not None:
            add_attr(name, "brightness", int(float(brightness) * 100))
        
        # Max BPC
        max_bpc = out.get('maxBpc')
        if max_bpc == 0:
            max_bpc = "automatic"
        add_attr(name, "maxbpc", max_bpc)
        
        # DDC/CI
        add_attr(name, "ddcCi", out.get('ddcCiAllowed'), bool_allow_map)
        
        # Mirroring
        replication_source_id = out.get('replicationSource', 0)
        if replication_source_id != 0:
            source_name = "none"
            for other_out in outputs:
                if other_out.get('id') == replication_source_id:
                    source_name = other_out['name']
                    break
            add_attr(name, "mirror", source_name)
        else:
            add_attr(name, "mirror", "none")

        # ICC Profile
        icc_path = out.get('iccProfilePath')
        if icc_path:
            add_attr(name, "iccProfilePath", icc_path)

        # Mode
        mode_id = out.get('currentModeId')
        if mode_id:
            mode_str = get_mode_string(out, mode_id)
            if mode_str:
                add_attr(name, "mode", mode_str)

        # Position
        pos = out.get('pos')
        if pos:
            add_attr(name, "position", f"{pos['x']},{pos['y']}")

        # Scale
        add_attr(name, "scale", out.get('scale'))

        # Rotation
        add_attr(name, "rotation", out.get('rotation'), rotation_map)

        # Priority and Primary
        priority = out.get('priority')
        if priority is not None:
            if priority == 1:
                commands.append(f"output.{name}.primary")
            commands.append(f"output.{name}.priority.{priority}")

    if commands:
        full_cmd = ["kscreen-doctor"] + commands
        log(f"Running atomic command: {' '.join(full_cmd)}")
        try:
            subprocess.run(full_cmd, check=True)
        except subprocess.CalledProcessError as e:
            log(f"Error executing kscreen-doctor: {e}")
            raise e

    log("Display configuration restored.")

class DisplayProfileManagerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KDE Display Profile Manager")
        self.setMinimumSize(420, 300)
        
        # Ensure default directory exists
        DEFAULT_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        
        self.setup_ui()
        self.refresh_profiles()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Header layout
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Available Profiles:"))
        header_layout.addStretch()
        
        self.refresh_btn = QPushButton()
        self.refresh_btn.setIcon(QIcon.fromTheme("view-refresh"))
        self.refresh_btn.setIconSize(QSize(20, 20))
        self.refresh_btn.setToolTip("Refresh Profiles")
        self.refresh_btn.setFlat(True)
        self.refresh_btn.clicked.connect(self.refresh_profiles)
        header_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(header_layout)
        
        self.profile_list = QListWidget()
        self.profile_list.itemDoubleClicked.connect(self.on_load_clicked)
        layout.addWidget(self.profile_list)
        
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save Current")
        self.save_btn.clicked.connect(self.on_save_clicked)
        btn_layout.addWidget(self.save_btn)

        self.load_btn = QPushButton("Load Selected")
        self.load_btn.clicked.connect(self.on_load_clicked)
        btn_layout.addWidget(self.load_btn)
        

        
        layout.addLayout(btn_layout)

    def refresh_profiles(self):
        self.profile_list.clear()
        if DEFAULT_PROFILE_DIR.exists():
            profiles = sorted(DEFAULT_PROFILE_DIR.glob("*.json"))
            for profile in profiles:
                name = profile.stem
                # Create item without text to prevent double-rendering/blurriness
                item = QListWidgetItem(self.profile_list)
                item.setData(Qt.UserRole, name)
                
                # Custom widget for the row
                widget = QWidget()
                row_layout = QHBoxLayout(widget)
                row_layout.setContentsMargins(5, 2, 5, 2)
                row_layout.setSpacing(5)
                
                label = QLabel(name)
                # Ensure the label doesn't inherit transparency issues
                label.setStyleSheet("background: transparent;") 
                row_layout.addWidget(label)
                row_layout.addStretch()
                
                # Copy button
                copy_btn = QPushButton()
                copy_btn.setIcon(QIcon.fromTheme("edit-copy"))
                copy_btn.setIconSize(QSize(16, 16))
                copy_btn.setFlat(True)
                copy_btn.setToolTip("Copy Load Command")
                copy_btn.clicked.connect(lambda checked=False, n=name: self.copy_profile_cmd(n))
                row_layout.addWidget(copy_btn)
                
                # Delete button
                del_btn = QPushButton()
                del_btn.setIcon(QIcon.fromTheme("user-trash"))
                del_btn.setIconSize(QSize(16, 16))
                del_btn.setFlat(True)
                del_btn.setToolTip("Delete Profile")
                del_btn.clicked.connect(lambda checked=False, n=name: self.delete_profile(n))
                row_layout.addWidget(del_btn)
                
                item.setSizeHint(widget.sizeHint())
                self.profile_list.addItem(item)
                self.profile_list.setItemWidget(item, widget)

    def get_default_profile_name(self):
        existing_names = []
        if DEFAULT_PROFILE_DIR.exists():
            existing_names = [p.stem for p in DEFAULT_PROFILE_DIR.glob("*.json")]
        
        i = 1
        while f"Profile {i}" in existing_names:
            i += 1
        return f"Profile {i}"

    def on_save_clicked(self):
        default_name = self.get_default_profile_name()
        name, ok = QInputDialog.getText(self, "Save Profile", "Profile Name:", text=default_name)
        
        if ok and name:
            profile_path = DEFAULT_PROFILE_DIR / f"{name}.json"
            if profile_path.exists():
                reply = QMessageBox.question(self, "Overwrite?", 
                                           f"Profile '{name}' already exists. Overwrite?",
                                           QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.No:
                    return
            
            try:
                save_profile(str(profile_path))
                self.refresh_profiles()
                QMessageBox.information(self, "Success", f"Profile '{name}' saved.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save profile: {e}")

    def on_load_clicked(self, item=None):
        if not isinstance(item, QListWidgetItem):
            item = self.profile_list.currentItem()
            
        if not item:
            QMessageBox.warning(self, "No Selection", "Please select a profile to load.")
            return
        
        # Retrieve name from UserRole data instead of item.text()
        profile_name = item.data(Qt.UserRole)
        profile_path = DEFAULT_PROFILE_DIR / f"{profile_name}.json"
        
        try:
            load_profile(str(profile_path))
            QMessageBox.information(self, "Success", f"Profile '{profile_name}' loaded.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load profile: {e}")

    def copy_profile_cmd(self, profile_name):
        profile_path = DEFAULT_PROFILE_DIR / f"{profile_name}.json"
        script_path = os.path.abspath(__file__)
        cmd = f"python3 {shlex.quote(script_path)} load {shlex.quote(str(profile_path))}"
        
        clipboard = QApplication.clipboard()
        clipboard.setText(cmd)
        
        QMessageBox.information(self, "Command Copied", f"The following command has been copied to your clipboard:\n\n{cmd}")

    def delete_profile(self, profile_name):
        profile_path = DEFAULT_PROFILE_DIR / f"{profile_name}.json"
        
        reply = QMessageBox.question(self, "Confirm Delete", 
                                   f"Are you sure you want to delete profile '{profile_name}'?",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                os.remove(profile_path)
                self.refresh_profiles()
                QMessageBox.information(self, "Success", f"Profile '{profile_name}' deleted.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete profile: {e}")

def show_gui():
    if not PYSIDE_AVAILABLE:
        print("Error: PySide6 is not installed. Please install it to use the GUI.", file=sys.stderr)
        sys.exit(1)
    
    # Use 'Round' instead of 'PassThrough' as it is often more stable for font rendering
    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.Round)
        
    app = QApplication(sys.argv)
    window = DisplayProfileManagerGUI()
    window.show()
    sys.exit(app.exec())

def main():
    parser = argparse.ArgumentParser(description="KDE Display Profile Manager")
    subparsers = parser.add_subparsers(dest="command", required=False)

    # Save command
    save_parser = subparsers.add_parser("save", help="Save current display configuration to a profile")
    save_parser.add_argument("profile", help="Path to the profile file (e.g., profiles/myprofile.json)")

    # Load command
    load_parser = subparsers.add_parser("load", help="Load a display configuration from a profile")
    load_parser.add_argument("profile", help="Path to the profile file")

    # GUI command
    subparsers.add_parser("gui", help="Launch the GUI manager")

    args = parser.parse_args()

    if args.command == "save":
        save_profile(args.profile)
    elif args.command == "load":
        load_profile(args.profile)
    elif args.command == "gui" or args.command is None:
        show_gui()

if __name__ == "__main__":
    main()
