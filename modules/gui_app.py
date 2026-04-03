"""
Homelab Scanner — PyQt6 GUI (Windows / Pi desktop)
"""
import os
import sys
import json
import copy
import base64
import logging
import platform
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSplitter, QListWidget, QListWidgetItem,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QPushButton, QDockWidget, QPlainTextEdit, QDialog,
    QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QDialogButtonBox,
    QAbstractItemView, QCheckBox, QSpinBox, QGroupBox, QComboBox,
    QSizePolicy, QMessageBox, QFileDialog, QStatusBar, QToolBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QByteArray, QObject
from PyQt6.QtGui import QFont, QAction, QColor

logger = logging.getLogger(__name__)


# ── Numeric sort item ─────────────────────────────────────────────────────────

class _NumericItem(QTableWidgetItem):
    _MULT = {"K": 1e3, "M": 1e6, "G": 1e9, "T": 1e12, "P": 1e15}

    def __lt__(self, other):
        return self._val() < other._val()

    def _val(self) -> float:
        s = self.text().strip().rstrip("%")
        if not s or s in ("?", "N/A", "-"):
            return -1.0
        try:
            if s[-1].upper() in self._MULT:
                return float(s[:-1]) * self._MULT[s[-1].upper()]
            return float(s)
        except ValueError:
            return -1.0


# ── State persistence ─────────────────────────────────────────────────────────

def _state_path(cfg_path: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(cfg_path)), "gui_state.json")


def _load_state(cfg_path: str) -> dict:
    path = _state_path(cfg_path)
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_state(cfg_path: str, state: dict) -> None:
    path = _state_path(cfg_path)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not save GUI state: {e}")


def _tbl_save(table: QTableWidget) -> str:
    return base64.b64encode(bytes(table.horizontalHeader().saveState())).decode()


def _tbl_restore(table: QTableWidget, state_str: str) -> None:
    if not state_str:
        return
    try:
        table.horizontalHeader().restoreState(QByteArray(base64.b64decode(state_str)))
    except Exception:
        pass


# ── Table factory ─────────────────────────────────────────────────────────────

def _make_table(headers: list) -> QTableWidget:
    t = QTableWidget()
    t.setColumnCount(len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setAlternatingRowColors(True)
    t.verticalHeader().setVisible(False)
    header = t.horizontalHeader()
    for i in range(len(headers)):
        header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
    header.setSectionsMovable(True)
    return t


# ── Scan worker ───────────────────────────────────────────────────────────────

class ScanWorker(QThread):
    host_done = pyqtSignal(dict)
    all_done = pyqtSignal(list)
    log_msg = pyqtSignal(str)

    def __init__(self, cfg: dict):
        super().__init__()
        self._cfg = cfg
        self._running = True

    def run(self):
        from modules.collectors import HostCollector
        collector = HostCollector(self._cfg)
        hosts = [h for h in self._cfg["hosts"] if h.get("enabled", True)]
        results = []

        def collect_one(host):
            if not self._running:
                return None
            self.log_msg.emit(f"[INFO] Scanning {host['name']}...")
            try:
                data = collector.collect(host)
                self.log_msg.emit(f"[INFO] Done: {host['name']}")
                return data
            except Exception as e:
                self.log_msg.emit(f"[ERROR] Failed {host['name']}: {e}")
                return {"name": host["name"], "error": str(e)}

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(collect_one, h): h for h in hosts}
            for future in as_completed(futures):
                if not self._running:
                    break
                result = future.result()
                if result is not None:
                    results.append(result)
                    self.host_done.emit(result)

        order = {h["name"]: i for i, h in enumerate(self._cfg["hosts"])}
        results.sort(key=lambda r: order.get(r.get("name", ""), 999))
        self.all_done.emit(results)

    def stop(self):
        self._running = False


# ── Logging bridge ────────────────────────────────────────────────────────────

class _LogSignal(QObject):
    message = pyqtSignal(str)


class _QtLogHandler(logging.Handler):
    def __init__(self, signal_obj: _LogSignal):
        super().__init__()
        self._sig = signal_obj

    def emit(self, record):
        try:
            self._sig.message.emit(self.format(record))
        except Exception:
            pass


# ── Host config dialog ────────────────────────────────────────────────────────

class HostConfigDialog(QDialog):
    def __init__(self, host: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Configure Host — {host.get('name', 'New')}")
        self.resize(440, 400)
        self._host = copy.deepcopy(host)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._name = QLineEdit(self._host.get("name", ""))
        self._hostname = QLineEdit(self._host.get("hostname", ""))
        self._user = QLineEdit(self._host.get("user", ""))
        self._type = QComboBox()
        self._type.addItems(["linux", "windows", "qnap", "local"])
        idx = self._type.findText(self._host.get("type", "linux"))
        self._type.setCurrentIndex(max(0, idx))
        self._password = QLineEdit(self._host.get("password") or "")
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._enabled = QCheckBox("Enabled")
        self._enabled.setChecked(self._host.get("enabled", True))

        form.addRow("Name:", self._name)
        form.addRow("Hostname:", self._hostname)
        form.addRow("User:", self._user)
        form.addRow("Type:", self._type)
        form.addRow("Password:", self._password)
        form.addRow("", self._enabled)
        layout.addLayout(form)

        collect_group = QGroupBox("Collect")
        cg = QHBoxLayout(collect_group)
        collect = set(self._host.get("collect", ["disk", "docker", "ips", "services"]))
        self._chk = {}
        for item in ["disk", "docker", "ips", "services"]:
            cb = QCheckBox(item.capitalize())
            cb.setChecked(item in collect)
            self._chk[item] = cb
            cg.addWidget(cb)
        layout.addWidget(collect_group)

        svc_group = QGroupBox("Services to check (comma-separated)")
        sg = QVBoxLayout(svc_group)
        self._services = QLineEdit(", ".join(self._host.get("services_check", [])))
        sg.addWidget(self._services)
        layout.addWidget(svc_group)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_host(self) -> dict:
        collect = [k for k, cb in self._chk.items() if cb.isChecked()]
        services = [s.strip() for s in self._services.text().split(",") if s.strip()]
        h = {
            "name": self._name.text().strip(),
            "hostname": self._hostname.text().strip(),
            "user": self._user.text().strip(),
            "type": self._type.currentText(),
            "enabled": self._enabled.isChecked(),
            "collect": collect,
            "services_check": services,
        }
        pw = self._password.text()
        if pw:
            h["password"] = pw
        # preserve platform override if it existed
        if "windows" in self._host:
            h["windows"] = self._host["windows"]
        return h


# ── Settings dialog ───────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    def __init__(self, raw_cfg: dict, cfg_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(760, 520)
        self._cfg = copy.deepcopy(raw_cfg)
        self._cfg_path = cfg_path
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._ssh_tab(), "SSH")
        tabs.addTab(self._output_tab(), "Output")
        tabs.addTab(self._hosts_tab(), "Hosts")
        layout.addWidget(tabs)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _ssh_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        ssh = self._cfg.get("ssh", {})
        self._ssh_key = QLineEdit(ssh.get("key_path", ""))
        self._ssh_connect = QSpinBox()
        self._ssh_connect.setRange(1, 120)
        self._ssh_connect.setValue(ssh.get("connect_timeout", 10))
        self._ssh_cmd = QSpinBox()
        self._ssh_cmd.setRange(1, 300)
        self._ssh_cmd.setValue(ssh.get("command_timeout", 30))
        form.addRow("Key path:", self._ssh_key)
        form.addRow("Connect timeout (s):", self._ssh_connect)
        form.addRow("Command timeout (s):", self._ssh_cmd)
        return w

    def _output_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        platforms = self._cfg.get("platforms", {})
        self._platform_fields = {}

        for plat_key, plat_label in [("pi", "Pi / Linux"), ("windows", "Windows")]:
            grp = QGroupBox(plat_label)
            form = QFormLayout(grp)
            pdata = platforms.get(plat_key, {})
            fields = {}
            for field in ["data_file", "context_file", "log_file"]:
                le = QLineEdit(pdata.get(field, ""))
                fields[field] = le
                row_w = QWidget()
                row_h = QHBoxLayout(row_w)
                row_h.setContentsMargins(0, 0, 0, 0)
                row_h.addWidget(le)
                btn = QPushButton("Browse")
                btn.clicked.connect(lambda _, f=le: self._browse(f))
                row_h.addWidget(btn)
                form.addRow(field.replace("_", " ").title() + ":", row_w)
            self._platform_fields[plat_key] = fields
            layout.addWidget(grp)
        return w

    def _browse(self, line_edit: QLineEdit):
        path, _ = QFileDialog.getSaveFileName(self, "Select file")
        if path:
            line_edit.setText(path)

    def _hosts_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        self._hosts_tbl = _make_table(["Name", "Hostname", "User", "Type", "Enabled"])
        self._hosts_tbl.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._hosts_tbl.doubleClicked.connect(self._edit_host)
        self._refresh_hosts_tbl()
        layout.addWidget(self._hosts_tbl)

        btn_row = QHBoxLayout()
        for label, slot in [("Add Host", self._add_host), ("Edit Host", self._edit_host), ("Remove Host", self._remove_host)]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            btn_row.addWidget(btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        return w

    def _refresh_hosts_tbl(self):
        t = self._hosts_tbl
        t.setSortingEnabled(False)
        t.setRowCount(0)
        for host in self._cfg.get("hosts", []):
            row = t.rowCount()
            t.insertRow(row)
            t.setItem(row, 0, QTableWidgetItem(host.get("name", "")))
            t.setItem(row, 1, QTableWidgetItem(host.get("hostname", "")))
            t.setItem(row, 2, QTableWidgetItem(host.get("user", "")))
            t.setItem(row, 3, QTableWidgetItem(host.get("type", "")))
            t.setItem(row, 4, QTableWidgetItem("Yes" if host.get("enabled", True) else "No"))
        t.setSortingEnabled(True)

    def _selected_host_name(self) -> str | None:
        row = self._hosts_tbl.currentRow()
        if row < 0:
            return None
        item = self._hosts_tbl.item(row, 0)
        return item.text() if item else None

    def _edit_host(self):
        name = self._selected_host_name()
        if not name:
            return
        host = next((h for h in self._cfg["hosts"] if h["name"] == name), None)
        if not host:
            return
        dlg = HostConfigDialog(host, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            idx = next(i for i, h in enumerate(self._cfg["hosts"]) if h["name"] == name)
            self._cfg["hosts"][idx] = dlg.get_host()
            self._refresh_hosts_tbl()

    def _add_host(self):
        new = {
            "name": "NewHost", "hostname": "192.168.0.x", "user": "pi",
            "type": "linux", "enabled": True,
            "collect": ["disk", "docker", "ips", "services"], "services_check": []
        }
        dlg = HostConfigDialog(new, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._cfg["hosts"].append(dlg.get_host())
            self._refresh_hosts_tbl()

    def _remove_host(self):
        name = self._selected_host_name()
        if not name:
            return
        self._cfg["hosts"] = [h for h in self._cfg["hosts"] if h["name"] != name]
        self._refresh_hosts_tbl()

    def _on_accept(self):
        self._cfg["ssh"] = {
            "key_path": self._ssh_key.text(),
            "connect_timeout": self._ssh_connect.value(),
            "command_timeout": self._ssh_cmd.value(),
        }
        self._cfg["platforms"] = {}
        for plat_key, fields in self._platform_fields.items():
            self._cfg["platforms"][plat_key] = {k: f.text() for k, f in fields.items()}
        try:
            with open(self._cfg_path, "w", encoding="utf-8") as f:
                json.dump(self._cfg, f, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save config:\n{e}")
            return
        self.accept()

    def get_raw_cfg(self) -> dict:
        return self._cfg


# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self, raw_cfg: dict, cfg: dict, cfg_path: str):
        super().__init__()
        self._raw_cfg = raw_cfg
        self._cfg = cfg
        self._cfg_path = cfg_path
        self._results: dict[str, dict] = {}
        self._worker: ScanWorker | None = None
        self._state = _load_state(cfg_path)
        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._do_save_state)
        self._auto_timer = QTimer()
        self._auto_timer.timeout.connect(self._scan_all)

        self.setWindowTitle("Homelab Scanner")
        self._build_ui()
        self._setup_logging()
        self._restore_state()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        tb = QToolBar()
        tb.setMovable(False)
        self.addToolBar(tb)

        self._act_scan = QAction("Scan All", self)
        self._act_scan.triggered.connect(self._scan_all)
        tb.addAction(self._act_scan)

        self._act_stop = QAction("Stop", self)
        self._act_stop.triggered.connect(self._stop_scan)
        self._act_stop.setEnabled(False)
        tb.addAction(self._act_stop)

        tb.addSeparator()

        self._act_settings = QAction("Settings", self)
        self._act_settings.triggered.connect(self._open_settings)
        tb.addAction(self._act_settings)

        tb.addSeparator()

        self._chk_auto = QCheckBox("Auto-refresh every")
        self._chk_auto.toggled.connect(self._toggle_auto)
        tb.addWidget(self._chk_auto)

        self._spin_interval = QSpinBox()
        self._spin_interval.setRange(1, 60)
        self._spin_interval.setValue(self._state.get("refresh_interval", 5))
        self._spin_interval.setSuffix(" min")
        self._spin_interval.valueChanged.connect(self._schedule_save)
        tb.addWidget(self._spin_interval)

        tb.addSeparator()
        self._lbl_status = QLabel("  Not scanned")
        tb.addWidget(self._lbl_status)

        # Central splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(splitter)
        self._splitter = splitter

        # Left — host list
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(4, 4, 4, 4)
        lbl = QLabel("Hosts")
        lbl.setFont(QFont("", -1, QFont.Weight.Bold))
        ll.addWidget(lbl)
        self._host_list = QListWidget()
        self._host_list.currentItemChanged.connect(self._on_host_selected)
        ll.addWidget(self._host_list)
        left.setMinimumWidth(180)
        left.setMaximumWidth(300)
        splitter.addWidget(left)

        # Right — detail panel
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(6, 6, 6, 6)
        self._host_title = QLabel("Select a host")
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        self._host_title.setFont(font)
        self._host_title.setWordWrap(True)
        rl.addWidget(self._host_title)

        self._tabs = QTabWidget()
        self._tbl_disk = _make_table(["Mount", "Source", "Size", "Used", "Avail", "Use%"])
        self._tbl_docker = _make_table(["Name", "Image", "Status"])
        self._tbl_services = _make_table(["Service", "Status"])
        self._tabs.addTab(self._tbl_disk, "Disk")
        self._tabs.addTab(self._tbl_docker, "Docker")
        self._tabs.addTab(self._tbl_services, "Services")
        rl.addWidget(self._tabs)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)

        # Log dock
        dock = QDockWidget("Log", self)
        dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(1000)
        self._log.setFont(QFont("Courier New", 9))
        dock.setWidget(self._log)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)

        self.setStatusBar(QStatusBar())

        # Connect table header signals for state persistence
        for key, tbl in [("disk_table", self._tbl_disk),
                          ("docker_table", self._tbl_docker),
                          ("services_table", self._tbl_services)]:
            h = tbl.horizontalHeader()
            h.sectionResized.connect(self._schedule_save)
            h.sectionMoved.connect(self._schedule_save)
            h.sortIndicatorChanged.connect(self._schedule_save)

        self._refresh_host_list()

    def _setup_logging(self):
        sig = _LogSignal(self)
        sig.message.connect(self._log.appendPlainText)
        handler = _QtLogHandler(sig)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)

        # Also set up file logging
        try:
            log_file = self._cfg["output"]["log_file"]
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(self._cfg_path)))
            if not os.path.isabs(log_file):
                log_file = os.path.join(base_dir, log_file)
            log_file = os.path.expandvars(os.path.expanduser(log_file))
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
            logging.getLogger().addHandler(fh)
        except Exception as e:
            logger.warning(f"Could not set up file logging: {e}")

    # ── Host list ─────────────────────────────────────────────────────────────

    def _refresh_host_list(self):
        current_name = None
        cur = self._host_list.currentItem()
        if cur:
            current_name = cur.data(Qt.ItemDataRole.UserRole)

        self._host_list.clear()
        for host in self._cfg.get("hosts", []):
            name = host["name"]
            result = self._results.get(name)

            if not host.get("enabled", True):
                text = f"{name}  (disabled)"
                color = QColor(120, 120, 120)
            elif result is None:
                text = f"{name}  —  not scanned"
                color = QColor(160, 160, 160)
            elif "error" in result:
                text = f"{name}  —  ERROR"
                color = QColor(220, 80, 80)
            else:
                text = f"{name}  —  OK"
                color = QColor(70, 180, 70)

            item = QListWidgetItem(text)
            item.setForeground(color)
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._host_list.addItem(item)
            if name == current_name:
                self._host_list.setCurrentItem(item)

    def _on_host_selected(self, current, _prev):
        if not current:
            return
        name = current.data(Qt.ItemDataRole.UserRole)
        self._show_host(name)
        self._state["selected_host"] = name
        self._schedule_save()

    # ── Detail panel ──────────────────────────────────────────────────────────

    def _show_host(self, name: str):
        result = self._results.get(name)
        cfg_host = next((h for h in self._cfg["hosts"] if h["name"] == name), {})
        hostname = cfg_host.get("hostname", "")

        if result is None:
            self._host_title.setText(f"{name} ({hostname}) — not yet scanned")
            self._clear_tables()
            return

        if "error" in result:
            self._host_title.setText(f"{name} ({hostname}) — ERROR: {result['error']}")
            self._clear_tables()
            return

        ips = ", ".join(result.get("ips", []))
        self._host_title.setText(f"{name} ({hostname}) — {ips}")
        self._fill_disk(result.get("disk", []))
        self._fill_docker(result.get("docker", []))
        self._fill_services(result.get("services", {}))

    def _clear_tables(self):
        for t in [self._tbl_disk, self._tbl_docker, self._tbl_services]:
            t.setRowCount(0)

    def _fill_disk(self, disk: list):
        t = self._tbl_disk
        t.setSortingEnabled(False)
        t.setRowCount(0)
        for d in disk:
            r = t.rowCount()
            t.insertRow(r)
            t.setItem(r, 0, QTableWidgetItem(d.get("mount", "")))
            t.setItem(r, 1, QTableWidgetItem(d.get("source", "")))
            t.setItem(r, 2, _NumericItem(d.get("size", "")))
            t.setItem(r, 3, _NumericItem(d.get("used", "")))
            t.setItem(r, 4, _NumericItem(d.get("avail", "")))
            t.setItem(r, 5, _NumericItem(d.get("use_pct", "")))
        t.setSortingEnabled(True)
        _tbl_restore(t, self._state.get("disk_table"))

    def _fill_docker(self, containers: list):
        t = self._tbl_docker
        t.setSortingEnabled(False)
        t.setRowCount(0)
        for c in containers:
            r = t.rowCount()
            t.insertRow(r)
            t.setItem(r, 0, QTableWidgetItem(c.get("name", "")))
            t.setItem(r, 1, QTableWidgetItem(c.get("image", "")))
            t.setItem(r, 2, QTableWidgetItem(c.get("status", "")))
        t.setSortingEnabled(True)
        _tbl_restore(t, self._state.get("docker_table"))

    def _fill_services(self, services: dict):
        t = self._tbl_services
        t.setSortingEnabled(False)
        t.setRowCount(0)
        for svc, status in services.items():
            r = t.rowCount()
            t.insertRow(r)
            t.setItem(r, 0, QTableWidgetItem(svc))
            t.setItem(r, 1, QTableWidgetItem(status))
        t.setSortingEnabled(True)
        _tbl_restore(t, self._state.get("services_table"))

    # ── Scan control ──────────────────────────────────────────────────────────

    def _scan_all(self):
        if self._worker and self._worker.isRunning():
            return
        self._act_scan.setEnabled(False)
        self._act_stop.setEnabled(True)
        self._lbl_status.setText("  Scanning...")
        self._worker = ScanWorker(self._cfg)
        self._worker.host_done.connect(self._on_host_done)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.log_msg.connect(self._log.appendPlainText)
        self._worker.start()

    def _stop_scan(self):
        if self._worker:
            self._worker.stop()
        self._act_stop.setEnabled(False)

    def _on_host_done(self, result: dict):
        name = result.get("name", "")
        self._results[name] = result
        self._refresh_host_list()
        cur = self._host_list.currentItem()
        if cur and cur.data(Qt.ItemDataRole.UserRole) == name:
            self._show_host(name)

    def _on_all_done(self, results: list):
        self._act_scan.setEnabled(True)
        self._act_stop.setEnabled(False)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._lbl_status.setText(f"  Last scan: {now}")
        self.statusBar().showMessage(f"Scan complete — {len(results)} hosts", 5000)
        self._save_yaml(results)

    def _save_yaml(self, results: list):
        try:
            from modules.data_store import save_data, load_data
            from modules.context_builder import build_context
            data_path = os.path.expandvars(os.path.expanduser(self._cfg["output"]["data_file"]))
            ctx_path = os.path.expandvars(os.path.expanduser(self._cfg["output"]["context_file"]))
            save_data(results, data_path)
            data = load_data(data_path)
            build_context(data, self._cfg.get("context", {}), ctx_path)
            logger.info("Data saved and context rebuilt")
        except Exception as e:
            logger.error(f"Post-scan save failed: {e}")

    # ── Auto-refresh ──────────────────────────────────────────────────────────

    def _toggle_auto(self, enabled: bool):
        self._state["auto_refresh"] = enabled
        self._schedule_save()
        if enabled:
            self._auto_timer.start(self._spin_interval.value() * 60 * 1000)
        else:
            self._auto_timer.stop()

    # ── Settings ──────────────────────────────────────────────────────────────

    def _open_settings(self):
        from main import resolve_config
        dlg = SettingsDialog(self._raw_cfg, self._cfg_path, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._raw_cfg = dlg.get_raw_cfg()
            self._cfg = resolve_config(self._raw_cfg)
            self._refresh_host_list()
            logger.info("Settings saved")

    # ── State persistence ─────────────────────────────────────────────────────

    def _schedule_save(self):
        self._save_timer.start(500)

    def _do_save_state(self):
        self._state["disk_table"] = _tbl_save(self._tbl_disk)
        self._state["docker_table"] = _tbl_save(self._tbl_docker)
        self._state["services_table"] = _tbl_save(self._tbl_services)
        self._state["refresh_interval"] = self._spin_interval.value()
        self._state["splitter"] = self._splitter.sizes()
        _save_state(self._cfg_path, self._state)

    def _restore_state(self):
        geom = self._state.get("geometry")
        if geom:
            try:
                self.restoreGeometry(QByteArray(base64.b64decode(geom)))
            except Exception:
                self.resize(1200, 700)
        else:
            self.resize(1200, 700)

        sizes = self._state.get("splitter")
        if sizes:
            self._splitter.setSizes(sizes)

        if self._state.get("auto_refresh"):
            self._chk_auto.setChecked(True)

        sel = self._state.get("selected_host")
        if sel:
            for i in range(self._host_list.count()):
                item = self._host_list.item(i)
                if item and item.data(Qt.ItemDataRole.UserRole) == sel:
                    self._host_list.setCurrentItem(item)
                    break

    def hideEvent(self, event):
        self._do_save_state()
        super().hideEvent(event)

    def closeEvent(self, event):
        self._do_save_state()
        self._state["geometry"] = base64.b64encode(bytes(self.saveGeometry())).decode()
        _save_state(self._cfg_path, self._state)
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)
        super().closeEvent(event)


# ── Entry point ───────────────────────────────────────────────────────────────

def run_gui(raw_cfg: dict, cfg: dict, cfg_path: str):
    app = QApplication(sys.argv)
    app.setApplicationName("Homelab Scanner")
    window = MainWindow(raw_cfg, cfg, cfg_path)
    window.show()
    sys.exit(app.exec())
