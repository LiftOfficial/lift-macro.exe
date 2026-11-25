import sys, os, json, time, threading, urllib.parse
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl, Signal, QObject
from PySide6.QtGui import QAction, QPixmap, QIcon, QDesktopServices
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QStackedWidget, QTreeWidget, QTreeWidgetItem,
    QFileDialog, QMessageBox, QLineEdit, QDoubleSpinBox, QSpinBox, QCheckBox,
    QComboBox, QSplitter, QFormLayout, QStatusBar, QPlainTextEdit,
    QListWidget, QListWidgetItem, QInputDialog, QSlider, QAbstractItemView
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings, QWebEngineProfile, QWebEnginePage

try:
    from pynput import mouse, keyboard
except Exception:
    mouse = keyboard = None

APP_NAME = "LIFT MACRO"
VERSION = "12.0.0"
BASE = Path(__file__).resolve().parent
MACRO_DIR = Path.home() / "Documents" / "LIFT Macro"
MACRO_DIR.mkdir(parents=True, exist_ok=True)
PROFILE_DIR = MACRO_DIR / "Profiles"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)
RECOVERY_FILE = MACRO_DIR / "recovery.liftmacro"

DARK_QSS = """
QWidget { background:#0b0c0f; color:#f2f3f5; font-family:'Segoe UI'; font-size:10pt; }
QMainWindow { background:#090b10; }
QMenuBar { background:#10131a; color:#dce2ec; padding:5px; border-bottom:1px solid #242b38; }
QMenuBar::item { padding:7px 11px; border-radius:6px; }
QMenuBar::item:selected { background:#252d3a; }
QMenu { background:#151a23; border:1px solid #303a4a; padding:6px; }
QMenu::item { padding:8px 28px 8px 12px; border-radius:5px; }
QMenu::item:selected { background:#303b4d; }
QToolTip { background:#202735; color:#f4f7fb; border:1px solid #46536a; padding:6px; }
QFrame#panel { background:#131821; border:1px solid #273142; border-radius:15px; }
QLabel#muted { color:#9299a5; }
QLabel#big { font-size:25pt; font-weight:800; }
QLabel#pageTitle { font-size:20pt; font-weight:750; }
QLabel#eyebrow { color:#9299a5; font-size:8pt; font-weight:700; letter-spacing:2px; }
QPushButton { background:#1a202b; color:#f2f3f5; border:1px solid #303b4d; border-radius:9px; padding:10px 14px; font-weight:600; }
QPushButton:hover { background:#273244; border-color:#64748b; }
QPushButton:pressed { background:#343a46; }
QPushButton#primary { background:#f0f1f4; color:#101115; border:0; }
QPushButton#primary:hover { background:#d5d8df; }
QPushButton#danger { color:#ff9b9b; }
QPushButton#nav { text-align:left; padding:12px 14px; background:transparent; border:0; color:#aeb3bd; }
QPushButton#nav:hover { background:#1b1e25; color:white; }
QPushButton#nav[selected="true"] { background:#252a33; border:1px solid #4a515f; color:white; }
QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox,QPlainTextEdit { background:#1a1d24; border:1px solid #303540; border-radius:8px; padding:9px; selection-background-color:#515d70; }
QTreeWidget,QListWidget { background:#14161b; alternate-background-color:#191c22; border:1px solid #292d35; border-radius:10px; padding:5px; }
QTreeWidget::item,QListWidget::item { padding:7px; }
QTreeWidget::item:selected,QListWidget::item:selected { background:#343b48; border-radius:5px; }
QHeaderView::section { background:#1b1e25; color:#aeb3bd; border:0; padding:9px; }
QTabWidget::pane { border:1px solid #303540; border-radius:10px; }
QTabBar::tab { background:#171a20; padding:9px 15px; border-top-left-radius:7px; border-top-right-radius:7px; }
QTabBar::tab:selected { background:#303641; }
QCheckBox { spacing:8px; }
QStatusBar { background:#14161b; color:#aeb3bd; }
QSlider::groove:horizontal { height:5px; background:#303540; border-radius:2px; }
QSlider::handle:horizontal { background:#f0f1f4; width:14px; margin:-5px 0; border-radius:7px; }
"""

class Signals(QObject):
    timeline = Signal()
    status = Signal(str, str)
    playback_done = Signal()

class LiftApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}  |  v{VERSION}")
        icon_path = BASE / "assets" / "lift-icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(1540, 960)
        self.setMinimumSize(1180, 760)
        self.events = []
        self.recording = False
        self.playing = False
        self.paused = False
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.lock = threading.Lock()
        self.started = 0.0
        self.last_move = 0.0
        self.mouse_listener = None
        self.keyboard_listener = None
        self.current_path = None
        self.run_count = 0
        self.total_seconds = 0
        self.record_filters = {"move": True, "click": True, "scroll": True, "keys": False}
        self.hotkey_actions = []
        self.pressed_keys = set()
        self.pressed_buttons = set()
        self.last_error = ""
        self.signals = Signals()
        self.signals.timeline.connect(self.refresh_timeline)
        self.signals.status.connect(self.set_status)
        self.signals.playback_done.connect(self.playback_finished)
        self.setStyleSheet(DARK_QSS)
        self.build_ui()
        self.refresh_library()
        self.clock = QTimer(self)
        self.clock.timeout.connect(self.refresh_dashboard)
        self.clock.start(700)
        self.timeline_clock = QTimer(self)
        self.timeline_clock.timeout.connect(self.refresh_timeline_if_recording)
        self.timeline_clock.start(500)
        self.autosave_clock = QTimer(self)
        self.autosave_clock.timeout.connect(self.write_recovery)
        self.autosave_clock.start(15000)
        self.set_status("Ready", "#8bd6a2")
        if RECOVERY_FILE.exists():
            answer=QMessageBox.question(self,"Recover previous macro","A recovery copy from an earlier session was found. Load it?",QMessageBox.Yes|QMessageBox.No,QMessageBox.Yes)
            if answer==QMessageBox.Yes:
                try:
                    payload=json.loads(RECOVERY_FILE.read_text(encoding="utf-8"))
                    self.load_events_payload(payload); self.refresh_timeline(); self.navigate(1)
                except Exception:
                    QMessageBox.warning(self,"Recovery unavailable","The recovery file could not be loaded.")

    def install_hotkeys(self):
        for action in self.hotkey_actions:
            self.removeAction(action)
        self.hotkey_actions=[]
        mapping=((self.hotkeys["record"],self.start_recording),
                 (self.hotkeys["stop"],self.stop_all),
                 (self.hotkeys["pause"],self.toggle_pause))
        for key,fn in mapping:
            action=QAction(self); action.setShortcut(key); action.setShortcutContext(Qt.WindowShortcut)
            action.triggered.connect(fn); self.addAction(action); self.hotkey_actions.append(action)

    def apply_hotkeys(self):
        values={"record":self.hk_record.currentText(),"stop":self.hk_stop.currentText(),"pause":self.hk_pause.currentText()}
        if len(set(values.values())) != 3:
            QMessageBox.warning(self,"Hotkey conflict","Each action must use a different function key.")
            return
        self.hotkeys=values; self.install_hotkeys()
        self.statusBar().showMessage("Hotkeys updated.",3000)

    def refresh_timeline_if_recording(self):
        if self.recording:
            self.refresh_timeline()

    def write_recovery(self):
        if not self.events or self.playing:
            return
        try:
            temp=RECOVERY_FILE.with_suffix(".tmp")
            with self.lock:
                payload={"app":APP_NAME,"version":VERSION,"recovery":True,"events":list(self.events)}
            temp.write_text(json.dumps(payload,indent=2),encoding="utf-8")
            temp.replace(RECOVERY_FILE)
        except Exception:
            pass

    def save_profile(self):
        name,ok=QInputDialog.getText(self,"Save profile","Profile name:")
        if not ok or not name.strip(): return
        safe="".join(c for c in name.strip() if c.isalnum() or c in " _-").strip()
        if not safe: return
        with self.lock:
            snapshot=list(self.events)
        payload={"version":VERSION,"events":snapshot,"speed":self.speed.value(),"repeat":self.repeat.value(),"forever":self.forever.isChecked()}
        try:
            (PROFILE_DIR/(safe+".liftprofile")).write_text(json.dumps(payload,indent=2),encoding="utf-8")
            self.statusBar().showMessage(f"Profile '{safe}' saved.",3000)
        except Exception as e: QMessageBox.critical(self,"Profile save failed",str(e))

    def load_profile(self):
        path,_=QFileDialog.getOpenFileName(self,"Load profile",str(PROFILE_DIR),"LIFT Profiles (*.liftprofile)")
        if not path: return
        try:
            payload=json.loads(Path(path).read_text(encoding="utf-8"))
            self.load_events_payload(payload)
            self.speed.setValue(float(payload.get("speed",1)))
            self.repeat.setValue(int(payload.get("repeat",1)))
            self.forever.setChecked(bool(payload.get("forever",False)))
            self.refresh_timeline(); self.navigate(1)
            self.statusBar().showMessage("Profile loaded.",3000)
        except Exception as e: QMessageBox.critical(self,"Profile load failed",str(e))

    def move_selected(self, delta):
        if self.recording or self.playing: return
        rows=sorted({self.tree.indexOfTopLevelItem(item) for item in self.tree.selectedItems()})
        if len(rows)!=1: return
        i=rows[0]; j=i+delta
        if not (0<=j<len(self.events)): return
        self.events[i]["t"],self.events[j]["t"]=self.events[j].get("t",0),self.events[i].get("t",0)
        self.events.sort(key=lambda e:e.get("t",0))
        self.refresh_timeline(); self.tree.setCurrentItem(self.tree.topLevelItem(j))

    def move_selected_up(self): self.move_selected(-1)
    def move_selected_down(self): self.move_selected(1)

    def panel(self):
        f = QFrame()
        f.setObjectName("panel")
        return f

    def label(self, text, object_name=None):
        x = QLabel(text)
        if object_name:
            x.setObjectName(object_name)
        return x

    def build_ui(self):
        central = QWidget()
        outer = QHBoxLayout(central)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(12)

        sidebar = self.panel()
        sidebar.setFixedWidth(238)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(12, 15, 12, 14)
        side.setSpacing(7)

        logo_row = QHBoxLayout()
        logo = QLabel()
        svg = (BASE / "assets" / "lift-symbol.svg").read_bytes()
        renderer = QSvgRenderer(svg)
        pix = QPixmap(58, 58)
        pix.fill(Qt.transparent)
        from PySide6.QtGui import QPainter
        painter = QPainter(pix)
        renderer.render(painter)
        painter.end()
        logo.setPixmap(pix)
        logo.setFixedSize(58, 58)
        logo_row.addWidget(logo)
        brand = QVBoxLayout()
        brand.addWidget(self.label("LIFT MACRO"))
        brand.addWidget(self.label("AUTOMATION STUDIO", "eyebrow"))
        logo_row.addLayout(brand)
        logo_row.addStretch()
        side.addLayout(logo_row)
        side.addSpacing(15)

        self.nav_buttons = {}
        nav_items = [
            ("Dashboard", "⌂", 0), ("Macro Studio", "◈", 1),
            ("SoundCloud", "♫", 2), ("Scripts", "▤", 3),
            ("Settings", "⚙", 4), ("Themes", "◐", 5),
            ("Library", "▣", 6), ("Statistics", "▥", 7),
            ("About", "ⓘ", 8)
        ]
        for name, glyph, idx in nav_items:
            b = QPushButton(f"{glyph}    {name}")
            b.setObjectName("nav")
            b.setProperty("selected", idx == 0)
            b.clicked.connect(lambda checked=False, i=idx: self.navigate(i))
            self.nav_buttons[idx] = b
            side.addWidget(b)
        side.addStretch()
        mini = self.panel()
        ml = QVBoxLayout(mini)
        ml.setContentsMargins(12, 12, 12, 12)
        ml.addWidget(self.label("LIFT SYMBOL", "eyebrow"))
        mini_logo = QLabel()
        mini_logo.setPixmap(pix.scaled(76, 76, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        mini_logo.setAlignment(Qt.AlignCenter)
        ml.addWidget(mini_logo)
        ml.addWidget(self.label("Automate. Listen. Relax.", "muted"))
        side.addWidget(mini)

        right = QVBoxLayout()
        top = QHBoxLayout()
        title = QVBoxLayout()
        title.addWidget(self.label("LIFT MACRO", "pageTitle"))
        title.addWidget(self.label("A cleaner workspace for your everyday workflows.", "muted"))
        top.addLayout(title)
        top.addStretch()
        self.status_label = QLabel("● READY")
        self.status_label.setStyleSheet("background:#1b1e25;color:#8bd6a2;padding:10px 15px;border-radius:9px;font-weight:700;")
        top.addWidget(self.status_label)
        right.addLayout(top)

        self.stack = QStackedWidget()
        self.pages = [
            self.page_dashboard(), self.page_studio(), self.page_soundcloud(),
            self.page_scripts(), self.page_settings(), self.page_themes(),
            self.page_library(), self.page_stats(), self.page_about()
        ]
        for p in self.pages:
            self.stack.addWidget(p)
        right.addWidget(self.stack, 1)
        outer.addWidget(sidebar)
        outer.addLayout(right, 1)
        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("F6 Record  •  F7 Stop  •  F8 Pause / Resume")
        self.build_menus()
        self.hotkeys = {"record": "F6", "stop": "F7", "pause": "F8"}
        self.install_hotkeys()

    def navigate(self, idx):
        self.stack.setCurrentIndex(idx)
        for i, b in self.nav_buttons.items():
            b.setProperty("selected", i == idx)
            b.style().unpolish(b)
            b.style().polish(b)
        if idx == 6:
            self.refresh_library()

    def stat_card(self, title, value):
        f = self.panel()
        l = QVBoxLayout(f)
        l.setContentsMargins(17, 14, 17, 14)
        l.addWidget(self.label(title, "eyebrow"))
        v = self.label(value, "big")
        l.addWidget(v)
        f.value = v
        return f

    def page_dashboard(self):
        w = QWidget()
        l = QVBoxLayout(w); l.setContentsMargins(4, 14, 4, 4); l.setSpacing(13)
        hero = self.panel(); h = QHBoxLayout(hero); h.setContentsMargins(22, 20, 22, 20)
        txt = QVBoxLayout()
        txt.addWidget(self.label("WELCOME TO YOUR WORKSPACE", "eyebrow"))
        txt.addWidget(self.label("Make the repetitive effortless.", "pageTitle"))
        txt.addWidget(self.label("Record a workflow, refine it, and replay it when you need it.", "muted"))
        h.addLayout(txt); h.addStretch()
        rec = QPushButton("●  Record a macro"); rec.setObjectName("primary"); rec.clicked.connect(self.start_recording)
        h.addWidget(rec); l.addWidget(hero)
        cards = QGridLayout(); cards.setSpacing(12)
        self.card_runs = self.stat_card("TOTAL RUNS", "0")
        self.card_actions = self.stat_card("SAVED MACROS", "0")
        self.card_runtime = self.stat_card("RECORDED ACTIONS", "0")
        for i,c in enumerate((self.card_runs,self.card_actions,self.card_runtime)): cards.addWidget(c,0,i)
        l.addLayout(cards)
        row = QHBoxLayout()
        quick = self.panel(); q = QVBoxLayout(quick); q.setContentsMargins(18,16,18,16)
        q.addWidget(self.label("QUICK CONTROL", "pageTitle"))
        controls = QGridLayout()
        for text, fn, obj in [
            ("▶  Play", self.play, "primary"), ("Ⅱ  Pause", self.toggle_pause, ""),
            ("■  Stop", self.stop_all, "danger"), ("＋  Add delay", self.add_delay, "")
        ]:
            b=QPushButton(text); b.setObjectName(obj); b.clicked.connect(fn); controls.addWidget(b, controls.count()//2, controls.count()%2)
        q.addLayout(controls)
        extra = QHBoxLayout()
        for text, fn in (("＋ New macro", self.new_macro), ("Open library", lambda: self.navigate(6)),
                         ("Export CSV", self.export_csv)):
            b=QPushButton(text); b.clicked.connect(fn); extra.addWidget(b)
        q.addLayout(extra)
        recent = self.panel(); r = QVBoxLayout(recent); r.setContentsMargins(18,16,18,16)
        r.addWidget(self.label("RECENT MACROS", "pageTitle"))
        self.recent_list = QListWidget(); self.recent_list.itemDoubleClicked.connect(self.open_library_item)
        r.addWidget(self.recent_list)
        row.addWidget(quick,1); row.addWidget(recent,1); l.addLayout(row,1)
        return w

    def page_studio(self):
        w=QWidget(); l=QVBoxLayout(w); l.setContentsMargins(4,14,4,4); l.setSpacing(10)
        bar=self.panel(); bar_layout=QVBoxLayout(bar); bar_layout.setContentsMargins(12,10,12,10); bar_layout.setSpacing(8)
        bl=QHBoxLayout()
        for text,fn,obj in [
            ("● Record",self.start_recording,"primary"),("■ Stop",self.stop_all,"danger"),
            ("▶ Play",self.play,""),("Ⅱ Pause",self.toggle_pause,""),
            ("＋ Delay",self.add_delay,""),("↑ Move",self.move_selected_up,""),
            ("↓ Move",self.move_selected_down,""),("Delete",self.delete_selected,"")
        ]:
            b=QPushButton(text); b.setObjectName(obj); b.clicked.connect(fn); bl.addWidget(b)
        duplicate_btn=QPushButton("Duplicate")
        duplicate_btn.setToolTip("Duplicate the selected timeline actions")
        duplicate_btn.clicked.connect(self.duplicate_selected)
        bl.addWidget(duplicate_btn)
        bl.addStretch(); bar_layout.addLayout(bl)
        filebar=QHBoxLayout()
        for text,fn in (("Open macro",self.open_macro),("Save macro",self.save_macro),
                        ("Save profile",self.save_profile),("Load profile",self.load_profile)):
            b=QPushButton(text); b.clicked.connect(fn); filebar.addWidget(b)
        template_btn=QPushButton("Insert template")
        template_btn.setToolTip("Add a reusable timing sequence to the timeline")
        template_btn.clicked.connect(self.insert_template)
        export_btn=QPushButton("Export CSV")
        export_btn.clicked.connect(self.export_csv)
        edit_btn=QPushButton("Edit selected time")
        edit_btn.clicked.connect(self.edit_selected_time)
        filebar.addWidget(template_btn); filebar.addWidget(export_btn); filebar.addWidget(edit_btn)
        filebar.addStretch(); bar_layout.addLayout(filebar)
        l.addWidget(bar)
        filter_row=QHBoxLayout()
        self.timeline_search=QLineEdit()
        self.timeline_search.setPlaceholderText("Filter timeline by action or details…")
        self.timeline_search.textChanged.connect(self.filter_timeline)
        filter_row.addWidget(self.timeline_search, 1)
        self.timeline_count=self.label("0 ACTIONS", "eyebrow")
        filter_row.addWidget(self.timeline_count)
        l.addLayout(filter_row)
        split=QSplitter(Qt.Horizontal)
        timeline=self.panel(); tl=QVBoxLayout(timeline); tl.setContentsMargins(13,13,13,13)
        tl.addWidget(self.label("MACRO TIMELINE", "pageTitle"))
        self.tree=QTreeWidget(); self.tree.setColumnCount(3); self.tree.setHeaderLabels(["TIME","ACTION","DETAILS"])
        self.tree.setColumnWidth(0,105); self.tree.setColumnWidth(1,140); self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.timeline_hint = self.label("Search, multi-select, duplicate, reorder, edit timing, or export your workflow.", "muted")
        tl.addWidget(self.timeline_hint)
        tl.addWidget(self.tree)
        options=self.panel(); ol=QVBoxLayout(options); ol.setContentsMargins(15,15,15,15)
        ol.addWidget(self.label("PLAYBACK OPTIONS","pageTitle"))
        form=QFormLayout()
        self.speed=QDoubleSpinBox(); self.speed.setRange(.1,5); self.speed.setSingleStep(.1); self.speed.setValue(1); self.speed.setSuffix("×")
        self.repeat=QSpinBox(); self.repeat.setRange(1,10000); self.repeat.setValue(1)
        form.addRow("Speed",self.speed); form.addRow("Repeat",self.repeat); ol.addLayout(form)
        self.forever=QCheckBox("Loop until stopped"); ol.addWidget(self.forever)
        ol.addSpacing(10); ol.addWidget(self.label("RECORDING FILTERS","eyebrow"))
        self.f_move=QCheckBox("Mouse movement"); self.f_move.setChecked(True)
        self.f_click=QCheckBox("Mouse clicks"); self.f_click.setChecked(True)
        self.f_scroll=QCheckBox("Scroll wheel"); self.f_scroll.setChecked(True)
        self.f_keys=QCheckBox("Keyboard input (may capture typed text)"); self.f_keys.setChecked(False)
        for c in (self.f_move,self.f_click,self.f_scroll,self.f_keys): ol.addWidget(c)
        ol.addStretch()
        ol.addWidget(self.label("Review actions before playback. Input is sent to the active desktop.", "muted"))
        split.addWidget(timeline); split.addWidget(options); split.setSizes([850,300])
        l.addWidget(split,1)
        return w

    def page_soundcloud(self):
        w=QWidget(); l=QVBoxLayout(w); l.setContentsMargins(4,14,4,4); l.setSpacing(10)
        intro=self.panel(); il=QVBoxLayout(intro); il.setContentsMargins(16,13,16,13)
        il.addWidget(self.label("SOUNDCLOUD PLAYER","pageTitle"))
        il.addWidget(self.label("Use SoundCloud's official website or load a public track / playlist link.", "muted"))
        l.addWidget(intro)
        authrow=QHBoxLayout()
        signup=QPushButton("Create SoundCloud account"); signup.setObjectName("primary")
        signup.clicked.connect(lambda:self.open_soundcloud_account("https://soundcloud.com/sign-up"))
        login=QPushButton("Log in")
        login.clicked.connect(lambda:self.open_soundcloud_account("https://soundcloud.com/sign-in"))
        authrow.addWidget(signup); authrow.addWidget(login); authrow.addStretch()
        l.addLayout(authrow)
        row=QHBoxLayout()
        self.sc_url=QLineEdit(); self.sc_url.setPlaceholderText("Paste a SoundCloud track or playlist URL…")
        row.addWidget(self.sc_url,1)
        load=QPushButton("Load track / playlist"); load.setObjectName("primary"); load.clicked.connect(self.load_soundcloud); row.addWidget(load)
        home=QPushButton("SoundCloud home"); home.clicked.connect(lambda:self.sc_view.setUrl(QUrl("https://soundcloud.com/"))); row.addWidget(home)
        l.addLayout(row)
        self.sc_view=QWebEngineView()
        # Keep SoundCloud's own session cookies in the user's app data so they can
        # remain signed in between launches. Authentication is still handled by SoundCloud.
        webdata = Path.home() / "AppData" / "Local" / "LIFT Macro" / "SoundCloud"
        if sys.platform != "win32":
            from PySide6.QtCore import QStandardPaths
            webdata = Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)) / "SoundCloud"
        webdata.mkdir(parents=True, exist_ok=True)
        self.sc_profile = QWebEngineProfile("LIFT-SoundCloud", self)
        self.sc_profile.setPersistentStoragePath(str(webdata / "storage"))
        self.sc_profile.setCachePath(str(webdata / "cache"))
        self.sc_profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)
        self.sc_page = QWebEnginePage(self.sc_profile, self.sc_view)
        self.sc_view.setPage(self.sc_page)
        self.sc_view.settings().setAttribute(QWebEngineSettings.JavascriptEnabled,True)
        self.sc_view.settings().setAttribute(QWebEngineSettings.LocalStorageEnabled,True)
        self.sc_view.settings().setAttribute(QWebEngineSettings.JavascriptCanOpenWindows,True)
        self.sc_view.setUrl(QUrl("https://soundcloud.com/"))
        l.addWidget(self.sc_view,1)
        l.addWidget(self.label("Sign-up and login are provided by SoundCloud. Your session is stored locally by the embedded browser. If SoundCloud blocks embedded authentication, use the buttons above to sign in through your normal browser.", "muted"))
        return w

    def open_soundcloud_account(self, url):
        # Open the provider's official auth page in the default browser; LIFT never
        # asks for or stores SoundCloud passwords.
        QDesktopServices.openUrl(QUrl(url))

    def load_soundcloud(self):
        raw=self.sc_url.text().strip()
        if not raw:
            self.sc_view.setUrl(QUrl("https://soundcloud.com/")); return
        u=urllib.parse.urlparse(raw)
        host=(u.hostname or "").lower().rstrip(".")
        if u.scheme not in ("http","https") or not (host=="soundcloud.com" or host.endswith(".soundcloud.com") or host=="snd.sc"):
            QMessageBox.warning(self,"Invalid link","Please paste a valid SoundCloud URL.")
            return
        encoded=urllib.parse.quote(raw,safe="")
        self.sc_view.setUrl(QUrl("https://w.soundcloud.com/player/?url="+encoded+"&auto_play=false&visual=true"))

    def page_scripts(self):
        w=QWidget(); l=QVBoxLayout(w); l.setContentsMargins(4,14,4,4); l.setSpacing(10)
        head=self.panel(); hl=QVBoxLayout(head); hl.setContentsMargins(17,15,17,15)
        hl.addWidget(self.label("SCRIPT WORKSPACE","pageTitle"))
        hl.addWidget(self.label("A local notes area for snippets and workflow documentation. It does not execute code.", "muted"))
        l.addWidget(head)
        self.script_notes=QPlainTextEdit()
        self.script_notes.setPlaceholderText("Write notes, action plans, or code snippets here…")
        l.addWidget(self.script_notes,1)
        row=QHBoxLayout()
        save=QPushButton("Save notes"); save.setObjectName("primary"); save.clicked.connect(self.save_notes)
        openb=QPushButton("Open notes"); openb.clicked.connect(self.open_notes)
        row.addWidget(save); row.addWidget(openb); row.addStretch(); l.addLayout(row)
        return w

    def page_settings(self):
        w=QWidget(); l=QVBoxLayout(w); l.setContentsMargins(4,14,4,4)
        p=self.panel(); pl=QVBoxLayout(p); pl.setContentsMargins(20,18,20,18)
        pl.addWidget(self.label("APPLICATION SETTINGS","pageTitle"))
        pl.addWidget(self.label("Customize the keyboard shortcuts used while LIFT is focused.", "muted"))
        hotform=QFormLayout()
        self.hk_record=QComboBox(); self.hk_record.addItems(["F6","F9","F10","F11","F12"])
        self.hk_stop=QComboBox(); self.hk_stop.addItems(["F7","F9","F10","F11","F12"])
        self.hk_pause=QComboBox(); self.hk_pause.addItems(["F8","F9","F10","F11","F12"])
        hotform.addRow("Record",self.hk_record); hotform.addRow("Stop",self.hk_stop); hotform.addRow("Pause / Resume",self.hk_pause)
        pl.addLayout(hotform)
        applykeys=QPushButton("Apply hotkeys"); applykeys.clicked.connect(self.apply_hotkeys); pl.addWidget(applykeys)
        pl.addWidget(self.label(f"Macro folder: {MACRO_DIR}", "muted"))
        pl.addWidget(self.label("Macro files use the portable .liftmacro JSON format.", "muted"))
        l.addWidget(p)
        privacy=self.panel(); vl=QVBoxLayout(privacy); vl.setContentsMargins(20,18,20,18)
        vl.addWidget(self.label("PRIVACY & SAFE USE","pageTitle"))
        for line in [
            "Keyboard recording is OFF by default. Enable it only when needed; it can capture typed text.",
            "Playback controls the real mouse and keyboard. Save your work and review your timeline first.",
            "Use macros only on your own device and in apps where automation is allowed.",
            "LIFT does not include stealth, anti-detection, credential capture, or remote-control features."
        ]:
            vl.addWidget(self.label("•  "+line))
        l.addWidget(privacy); l.addStretch()
        return w

    def page_themes(self):
        w=QWidget(); l=QVBoxLayout(w); l.setContentsMargins(4,14,4,4)
        p=self.panel(); pl=QVBoxLayout(p); pl.setContentsMargins(20,18,20,18)
        pl.addWidget(self.label("APPEARANCE","pageTitle"))
        pl.addWidget(self.label("Choose the interface accent. The base interface stays dark for readability.", "muted"))
        self.accent_combo=QComboBox(); self.accent_combo.addItems(["Silver","Ice Blue","Violet","Mint"])
        pl.addWidget(self.accent_combo)
        apply=QPushButton("Apply accent"); apply.setObjectName("primary"); apply.clicked.connect(self.apply_accent); pl.addWidget(apply)
        l.addWidget(p); l.addStretch()
        return w

    def apply_accent(self):
        accents={"Silver":"#f0f1f4","Ice Blue":"#9ecbff","Violet":"#c4a5ff","Mint":"#9ce6c2"}
        color=accents[self.accent_combo.currentText()]
        self.setStyleSheet(DARK_QSS + f"\nQPushButton#primary{{background:{color};color:#101115;}}")
        self.statusBar().showMessage("Accent updated for this session.",3000)

    def page_library(self):
        w=QWidget(); l=QVBoxLayout(w); l.setContentsMargins(4,14,4,4)
        p=self.panel(); pl=QVBoxLayout(p); pl.setContentsMargins(15,15,15,15)
        pl.addWidget(self.label("MACRO LIBRARY","pageTitle"))
        self.library_search=QLineEdit(); self.library_search.setPlaceholderText("Search your saved macros…")
        self.library_search.textChanged.connect(self.filter_library)
        pl.addWidget(self.library_search)
        row=QHBoxLayout()
        self.library_list=QListWidget(); self.library_list.itemDoubleClicked.connect(self.open_library_item)
        row.addWidget(self.library_list,1)
        controls=QVBoxLayout()
        for text,fn in (("Refresh",self.refresh_library),("Open selected",self.open_library_item),("Open folder",self.open_macro_folder),("New macro",self.new_macro)):
            b=QPushButton(text); b.clicked.connect(fn); controls.addWidget(b)
        controls.addStretch(); row.addLayout(controls)
        pl.addLayout(row); l.addWidget(p,1)
        return w

    def page_stats(self):
        w=QWidget(); l=QVBoxLayout(w); l.setContentsMargins(4,14,4,4)
        p=self.panel(); pl=QVBoxLayout(p); pl.setContentsMargins(20,18,20,18)
        pl.addWidget(self.label("SESSION STATISTICS","pageTitle"))
        self.stats_text=self.label("No playback runs yet.")
        self.stats_text.setWordWrap(True); pl.addWidget(self.stats_text)
        l.addWidget(p); l.addStretch()
        return w

    def page_about(self):
        w=QWidget(); l=QVBoxLayout(w); l.setContentsMargins(4,14,4,4)
        p=self.panel(); pl=QVBoxLayout(p); pl.setContentsMargins(20,18,20,18)
        pl.addWidget(self.label("ABOUT LIFT MACRO","pageTitle"))
        pl.addWidget(self.label(f"Version {VERSION}  •  Windows desktop application"))
        pl.addWidget(self.label("A redesigned automation workspace with timeline search, action editing, CSV export, macro recording, playback, local library and SoundCloud access.", "muted"))
        icon_preview=QLabel(); icon_preview.setPixmap(QPixmap(str(BASE / "assets" / "lift-icon.png")).scaled(112,112,Qt.KeepAspectRatio,Qt.SmoothTransformation)); pl.addWidget(icon_preview,0,Qt.AlignLeft)
        pl.addWidget(self.label("The LIFT symbol is an original abstract orbital-star mark, separate from the wordmark.", "muted"))
        pl.addWidget(self.label("Windows app icon: custom LIFT emblem, included in the build output.", "muted"))
        l.addWidget(p); l.addStretch()
        return w

    def set_status(self, text, color):
        self.status_label.setText("● "+text.upper())
        self.status_label.setStyleSheet(f"background:#1b1e25;color:{color};padding:10px 15px;border-radius:9px;font-weight:700;")

    def refresh_dashboard(self):
        if not hasattr(self,"card_runs"): return
        self.card_runs.value.setText(str(self.run_count))
        self.card_actions.value.setText(str(len(list(MACRO_DIR.glob("*.liftmacro")))))
        self.card_runtime.value.setText(str(len(self.events)))
        if hasattr(self,"stats_text"):
            self.stats_text.setText(f"Completed playback runs: {self.run_count}\nRecorded actions in current macro: {len(self.events)}\nApproximate playback time: {self.total_seconds:.1f} seconds\nMacro library: {len(list(MACRO_DIR.glob('*.liftmacro')))} saved files")

    def stamp(self):
        return max(0.0,time.perf_counter()-self.started)

    def refresh_timeline(self):
        if not hasattr(self,"tree"): return
        self.tree.clear()
        with self.lock:
            snapshot=sorted([dict(e) for e in self.events],key=lambda e:e.get("t",0))
        for ev in snapshot:
            typ=ev.get("type","")
            if typ=="move": detail=f"x={ev['x']}  y={ev['y']}"
            elif typ=="click": detail=f"{ev['button']} {'down' if ev['pressed'] else 'up'} at ({ev['x']}, {ev['y']})"
            elif typ=="scroll": detail=f"scroll {ev['dx']}, {ev['dy']}"
            elif typ in ("keypress","keyrelease"): detail=ev.get("key","")
            else: detail=f"{ev.get('seconds',0):.2f}s"
            QTreeWidgetItem(self.tree,[f"{ev.get('t',0):.3f}s",typ.upper(),detail])
        self.refresh_dashboard()
        if hasattr(self, "timeline_search"):
            self.filter_timeline(self.timeline_search.text())

    def filter_timeline(self, query):
        if not hasattr(self, "tree"): return
        query = (query or "").strip().casefold()
        visible = 0
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            match = not query or query in " ".join(item.text(c) for c in range(self.tree.columnCount())).casefold()
            item.setHidden(not match)
            visible += int(match)
        if hasattr(self, "timeline_count"):
            self.timeline_count.setText(f"{visible} / {self.tree.topLevelItemCount()} ACTIONS")

    def edit_selected_time(self):
        if self.recording or self.playing: return
        selected = self.tree.selectedItems()
        if len(selected) != 1:
            QMessageBox.information(self, "Select one action", "Select exactly one timeline action first.")
            return
        index = self.tree.indexOfTopLevelItem(selected[0])
        if not (0 <= index < len(self.events)): return
        current = float(self.events[index].get("t", 0))
        value, ok = QInputDialog.getDouble(self, "Edit action time", "Time from start (seconds):", current, 0, 86400, 3)
        if not ok: return
        self.events[index]["t"] = value
        self.events.sort(key=lambda e: e.get("t", 0))
        self.refresh_timeline()
        self.statusBar().showMessage("Action timing updated.", 3000)

    def insert_template(self):
        if self.recording or self.playing: return
        choices = {
            "Quick pause (0.5s)": [0.5],
            "Three-step timing (0.5s / 1s / 0.5s)": [0.5, 1.0, 0.5],
            "Short cooldown (2s / 5s / 2s)": [2.0, 5.0, 2.0],
            "Long wait (10s)": [10.0],
        }
        choice, ok = QInputDialog.getItem(self, "Insert timing template",
                                          "Choose a delay sequence:", list(choices), 0, False)
        if not ok or choice not in choices: return
        durations = choices[choice]
        selected = self.tree.currentIndex().row()
        insert_at = selected + 1 if selected >= 0 else len(self.events)
        base = float(self.events[insert_at-1].get("t", 0)) if insert_at > 0 else 0.0
        shift = sum(durations)
        for i in range(insert_at, len(self.events)):
            self.events[i]["t"] = float(self.events[i].get("t", 0)) + shift
        cursor = base
        added = []
        for seconds in durations:
            cursor += seconds
            added.append({"t": cursor, "type": "delay", "seconds": seconds})
        self.events[insert_at:insert_at] = added
        self.refresh_timeline()
        self.statusBar().showMessage(f"Inserted timing template: {choice}", 4000)

    def export_csv(self):
        if not self.events:
            QMessageBox.information(self, "Nothing to export", "Record or open a macro first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export timeline", str(MACRO_DIR / "macro-timeline.csv"), "CSV files (*.csv)")
        if not path: return
        import csv
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle)
                writer.writerow(["time_seconds", "action", "details"])
                for event in sorted(self.events, key=lambda e: e.get("t", 0)):
                    details = {k:v for k,v in event.items() if k not in ("t", "type")}
                    writer.writerow([f"{float(event.get('t', 0)):.4f}", event.get("type", ""), json.dumps(details, ensure_ascii=False)])
            self.statusBar().showMessage(f"Timeline exported to {path}", 5000)
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))

    def start_recording(self):
        if self.recording or self.playing: return
        if mouse is None or keyboard is None:
            QMessageBox.critical(self,"Missing dependency","Install requirements with build_exe.bat, or run: python -m pip install pynput")
            return
        if self.f_keys.isChecked():
            answer=QMessageBox.warning(self,"Keyboard capture enabled",
                "Keyboard recording may capture anything typed, including private text. Do not record passwords or sensitive information. Continue?",
                QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
            if answer != QMessageBox.Yes: return
        self.events=[]; self.started=time.perf_counter(); self.last_move=0.0; self.recording=True
        self.record_filters={"move":self.f_move.isChecked(),"click":self.f_click.isChecked(),
                             "scroll":self.f_scroll.isChecked(),"keys":self.f_keys.isChecked()}
        self.refresh_timeline(); self.set_status("Recording","#ff8585")
        try:
            self.mouse_listener=mouse.Listener(on_move=self.on_move,on_click=self.on_click,on_scroll=self.on_scroll)
            self.keyboard_listener=keyboard.Listener(on_press=self.on_press,on_release=self.on_release)
            self.mouse_listener.start(); self.keyboard_listener.start()
        except Exception as e:
            self.recording=False
            self.stop_recording()
            QMessageBox.critical(self,"Recording failed",str(e))

    def on_move(self,x,y):
        if self.recording and self.record_filters["move"]:
            now=time.perf_counter()
            if now-self.last_move>=.075:
                self.last_move=now
                with self.lock: self.events.append({"t":self.stamp(),"type":"move","x":int(x),"y":int(y)})

    def on_click(self,x,y,button,pressed):
        if self.recording and self.record_filters["click"]:
            with self.lock: self.events.append({"t":self.stamp(),"type":"click","x":int(x),"y":int(y),"button":str(button).replace("Button.",""),"pressed":bool(pressed)})

    def on_scroll(self,x,y,dx,dy):
        if self.recording and self.record_filters["scroll"]:
            with self.lock: self.events.append({"t":self.stamp(),"type":"scroll","x":int(x),"y":int(y),"dx":int(dx),"dy":int(dy)})

    def key_name(self,key):
        try:
            if key.char is not None: return key.char
        except AttributeError: pass
        return "KEY_"+str(key).replace("Key.","").upper()

    def on_press(self,key):
        if self.recording and self.record_filters["keys"]:
            with self.lock: self.events.append({"t":self.stamp(),"type":"keypress","key":self.key_name(key)})

    def on_release(self,key):
        if self.recording and self.record_filters["keys"]:
            with self.lock: self.events.append({"t":self.stamp(),"type":"keyrelease","key":self.key_name(key)})

    def stop_recording(self):
        self.recording=False
        for listener in (self.mouse_listener,self.keyboard_listener):
            if listener:
                try: listener.stop()
                except Exception: pass
        self.mouse_listener=self.keyboard_listener=None
        self.set_status("Ready","#8bd6a2")
        self.refresh_timeline()
        self.write_recovery()

    def stop_all(self):
        if self.recording: self.stop_recording()
        if self.playing:
            self.stop_event.set(); self.pause_event.set()
            self.set_status("Stopping","#ff8585")

    def toggle_pause(self):
        if not self.playing: return
        if self.paused:
            self.paused=False; self.pause_event.set(); self.set_status("Playing","#8bd6a2")
        else:
            self.paused=True; self.pause_event.clear(); self.set_status("Paused","#e6c36a")

    def add_delay(self):
        if self.recording or self.playing: return
        sec,ok=QInputDialog.getDouble(self,"Insert delay","Delay duration (seconds):",.5,.01,3600,2)
        if not ok: return
        selected=self.tree.currentIndex().row()
        insert_at=selected+1 if selected>=0 else len(self.events)
        base=self.events[insert_at-1].get("t",0) if insert_at>0 else 0
        marker_time=base+sec
        for i in range(insert_at,len(self.events)):
            self.events[i]["t"]+=sec
        self.events.insert(insert_at,{"t":marker_time,"type":"delay","seconds":sec})
        self.refresh_timeline()

    def delete_selected(self):
        if self.recording or self.playing: return
        indices={self.tree.indexOfTopLevelItem(x) for x in self.tree.selectedItems()}
        self.events=[e for i,e in enumerate(self.events) if i not in indices]
        self.refresh_timeline()

    def duplicate_selected(self):
        if self.recording or self.playing: return
        indices=sorted({self.tree.indexOfTopLevelItem(x) for x in self.tree.selectedItems()})
        if not indices: return
        additions=[]
        for index in indices:
            if 0 <= index < len(self.events):
                clone=dict(self.events[index])
                clone["t"]=float(clone.get("t",0)) + 0.05
                additions.append(clone)
        self.events.extend(additions)
        self.events.sort(key=lambda e:e.get("t",0))
        self.refresh_timeline()
        self.statusBar().showMessage(f"Duplicated {len(additions)} action(s).",3000)

    def clear_timeline(self):
        if self.recording or self.playing or not self.events: return
        if QMessageBox.question(self,"Clear timeline","Remove every action from the current macro? This cannot be undone.") != QMessageBox.Yes:
            return
        self.events=[]; self.refresh_timeline(); self.set_status("Timeline cleared","#e6c36a")

    def build_menus(self):
        file_menu=self.menuBar().addMenu("File")
        for title,shortcut,callback in (("New macro","Ctrl+N",self.new_macro),("Open macro…","Ctrl+O",self.open_macro),("Save macro…","Ctrl+S",self.save_macro)):
            action=QAction(title,self); action.setShortcut(shortcut); action.triggered.connect(callback); file_menu.addAction(action)
        file_menu.addSeparator()
        exit_action=QAction("Exit",self); exit_action.triggered.connect(self.close); file_menu.addAction(exit_action)
        edit_menu=self.menuBar().addMenu("Edit")
        for title,shortcut,callback in (("Add delay","",self.add_delay),("Duplicate selected","Ctrl+D",self.duplicate_selected),("Delete selected","Delete",self.delete_selected),("Clear timeline","",self.clear_timeline)):
            action=QAction(title,self)
            if shortcut: action.setShortcut(shortcut)
            action.triggered.connect(callback); edit_menu.addAction(action)
        view_menu=self.menuBar().addMenu("View")
        for index,name in enumerate(("Dashboard","Macro Studio","SoundCloud","Scripts","Settings","Themes","Library","Statistics","About")):
            action=QAction(name,self); action.triggered.connect(lambda checked=False,i=index:self.navigate(i)); view_menu.addAction(action)

    def save_macro(self):
        default=str(self.current_path or (MACRO_DIR/"New Macro.liftmacro"))
        path,_=QFileDialog.getSaveFileName(self,"Save macro",default,"LIFT Macro (*.liftmacro)")
        if not path: return
        if not path.lower().endswith(".liftmacro"): path += ".liftmacro"
        try:
            with open(path,"w",encoding="utf-8") as f:
                with self.lock:
                    snapshot=list(self.events)
                json.dump({"app":APP_NAME,"version":VERSION,"events":snapshot},f,indent=2)
            self.current_path=Path(path); self.refresh_library(); self.set_status("Saved","#8bd6a2")
        except Exception as e: QMessageBox.critical(self,"Save failed",str(e))

    def open_macro(self):
        path,_=QFileDialog.getOpenFileName(self,"Open macro",str(MACRO_DIR),"LIFT Macro (*.liftmacro *.json)")
        if path: self.load_macro_path(path)

    def load_events_payload(self,payload):
        data=payload.get("events") if isinstance(payload,dict) else payload
        allowed={"move","click","scroll","keypress","keyrelease","delay"}
        if not isinstance(data,list) or len(data)>100000: raise ValueError("Invalid or oversized macro.")
        cleaned=[]
        for item in data:
            if not isinstance(item,dict) or item.get("type") not in allowed: raise ValueError("Unsupported macro action.")
            e=dict(item)
            stamp=float(e.get("t",0))
            if not (0 <= stamp <= 86400): raise ValueError("Action timestamps must be between 0 and 24 hours.")
            e["t"]=stamp
            if e["type"]=="move": e["x"]=int(e["x"]); e["y"]=int(e["y"])
            elif e["type"]=="click":
                e["x"]=int(e["x"]); e["y"]=int(e["y"])
                if e.get("button") not in ("left","right","middle"): raise ValueError("Unsupported mouse button.")
                e["pressed"]=bool(e.get("pressed",False))
            elif e["type"]=="scroll":
                e["x"]=int(e["x"]); e["y"]=int(e["y"]); e["dx"]=int(e.get("dx",0)); e["dy"]=int(e.get("dy",0))
            elif e["type"] in ("keypress","keyrelease"):
                key=e.get("key")
                if not isinstance(key,str) or len(key)>40: raise ValueError("Invalid keyboard event.")
            elif e["type"]=="delay": e["seconds"]=max(0,min(3600,float(e.get("seconds",0))))
            cleaned.append(e)
        self.events=sorted(cleaned,key=lambda e:e["t"])

    def load_macro_path(self,path):
        try:
            payload=json.loads(Path(path).read_text(encoding="utf-8"))
            self.load_events_payload(payload)
            self.current_path=Path(path); self.refresh_timeline(); self.navigate(1)
            self.set_status("Macro loaded","#8bd6a2")
        except Exception as e: QMessageBox.critical(self,"Open failed",str(e))

    def refresh_library(self):
        if not hasattr(self,"library_list"): return
        self.library_list.clear()
        files=sorted(MACRO_DIR.glob("*.liftmacro"),key=lambda p:p.stat().st_mtime,reverse=True)
        for p in files:
            item=QListWidgetItem("◈   "+p.stem); item.setData(Qt.UserRole,str(p)); self.library_list.addItem(item)
        if hasattr(self,"library_search"):
            self.filter_library(self.library_search.text())
        if hasattr(self,"recent_list"):
            self.recent_list.clear()
            for p in files[:6]:
                item=QListWidgetItem(p.stem); item.setData(Qt.UserRole,str(p)); self.recent_list.addItem(item)
        self.refresh_dashboard()

    def filter_library(self, query):
        if not hasattr(self,"library_list"): return
        query=query.strip().casefold()
        for i in range(self.library_list.count()):
            item=self.library_list.item(i)
            item.setHidden(query not in item.text().casefold())

    def new_macro(self):
        if self.recording or self.playing: return
        if self.events and QMessageBox.question(self,"Start a new macro","Clear the current timeline? Save it first if you want to keep it.") != QMessageBox.Yes:
            return
        self.events=[]; self.current_path=None; self.refresh_timeline(); self.navigate(1)
        self.set_status("New macro","#8bd6a2")

    def open_library_item(self,item=None):
        if item is None:
            item=self.library_list.currentItem() if hasattr(self,"library_list") else None
        if item:
            path=item.data(Qt.UserRole)
            if path: self.load_macro_path(path)

    def open_macro_folder(self):
        try:
            if sys.platform == "win32": os.startfile(str(MACRO_DIR))
            else: QDesktopServices.openUrl(QUrl.fromLocalFile(str(MACRO_DIR)))
        except Exception as e: QMessageBox.warning(self,"Folder unavailable",str(e))

    def save_notes(self):
        path,_=QFileDialog.getSaveFileName(self,"Save notes","","Text files (*.txt)")
        if path:
            try: Path(path).write_text(self.script_notes.toPlainText(),encoding="utf-8")
            except Exception as e: QMessageBox.critical(self,"Save failed",str(e))

    def open_notes(self):
        path,_=QFileDialog.getOpenFileName(self,"Open notes","","Text files (*.txt)")
        if path:
            try: self.script_notes.setPlainText(Path(path).read_text(encoding="utf-8"))
            except Exception as e: QMessageBox.critical(self,"Open failed",str(e))

    def resolve_key(self,name):
        if name.startswith("KEY_"):
            return getattr(keyboard.Key,name[4:].lower(),None)
        return name if len(name)==1 else None

    def wait_play(self,seconds):
        end=time.perf_counter()+max(0,seconds)
        while time.perf_counter()<end:
            if self.stop_event.is_set(): return False
            self.pause_event.wait(.04)
            if self.stop_event.is_set(): return False
        return not self.stop_event.is_set()

    def play(self):
        if self.recording or self.playing: return
        if not self.events:
            QMessageBox.information(self,"No macro","Record or open a macro first."); return
        if mouse is None:
            QMessageBox.critical(self,"Missing dependency","Install pynput first."); return
        if QMessageBox.question(self,"Confirm playback","This macro sends real mouse and keyboard input. Save your work and review the timeline before continuing.") != QMessageBox.Yes:
            return
        self.stop_event.clear(); self.pause_event.set(); self.playing=True; self.paused=False
        with self.lock:
            self._play_events=sorted([dict(e) for e in self.events],key=lambda e:e.get("t",0))
        self._repeat_count=self.repeat.value(); self._forever=self.forever.isChecked(); self._speed=self.speed.value()
        self.pressed_keys=set(); self.pressed_buttons=set()
        self.set_status("Playing","#8bd6a2")
        threading.Thread(target=self.play_worker,daemon=True).start()

    def play_worker(self):
        m=None; k=None; runs=0; errors=[]
        try:
            m=mouse.Controller(); k=keyboard.Controller()
            while not self.stop_event.is_set() and (self._forever or runs<self._repeat_count):
                previous=0.0
                for e in self._play_events:
                    if self.stop_event.is_set(): break
                    current=max(previous,float(e.get("t",previous)))
                    if not self.wait_play((current-previous)/max(.1,self._speed)): break
                    previous=current; typ=e["type"]
                    try:
                        if typ=="move": m.position=(e["x"],e["y"])
                        elif typ=="click":
                            m.position=(e["x"],e["y"])
                            button=getattr(mouse.Button,e.get("button","left"),mouse.Button.left)
                            if e.get("pressed"):
                                m.press(button); self.pressed_buttons.add(button)
                            else:
                                m.release(button); self.pressed_buttons.discard(button)
                        elif typ=="scroll": m.position=(e["x"],e["y"]); m.scroll(e.get("dx",0),e.get("dy",0))
                        elif typ in ("keypress","keyrelease"):
                            key=self.resolve_key(e.get("key",""))
                            if key is not None:
                                if typ=="keypress": k.press(key); self.pressed_keys.add(key)
                                else: k.release(key); self.pressed_keys.discard(key)
                        # Delay is represented by the gap in event timestamps; no second wait.
                    except Exception as exc:
                        errors.append(str(exc))
                # Never carry a held mouse button or key into another loop iteration.
                for held_key in list(self.pressed_keys):
                    try: k.release(held_key)
                    except Exception: pass
                    self.pressed_keys.discard(held_key)
                for held_button in list(self.pressed_buttons):
                    try: m.release(held_button)
                    except Exception: pass
                    self.pressed_buttons.discard(held_button)
                if self.stop_event.is_set(): break
                runs+=1
                if not self._forever and runs>=self._repeat_count: break
            self.run_count += runs
            if self._play_events:
                self.total_seconds += max(0,self._play_events[-1].get("t",0))*runs
        except Exception as exc:
            errors.append(str(exc))
        finally:
            # Release any held inputs even when playback is stopped midway.
            for key in list(self.pressed_keys):
                try:
                    if k is not None: k.release(key)
                except Exception: pass
            for button in list(self.pressed_buttons):
                try:
                    if m is not None: m.release(button)
                except Exception: pass
            self.pressed_keys.clear(); self.pressed_buttons.clear()
            if errors:
                self.last_error = errors[0][:300]
            self.signals.playback_done.emit()

    def playback_finished(self):
        self.playing=False; self.paused=False
        if self.last_error:
            self.set_status("Finished with warnings","#e6c36a")
            self.statusBar().showMessage(self.last_error, 10000)
            self.last_error = ""
        else:
            self.set_status("Ready","#8bd6a2")
        self.refresh_dashboard()

    def closeEvent(self,event):
        self.stop_event.set(); self.pause_event.set()
        if self.recording: self.stop_recording()
        if self.playing:
            self.stop_event.set(); self.pause_event.set()
        self.write_recovery()
        event.accept()

def main():
    app=QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window=LiftApp()
    window.show()
    sys.exit(app.exec())

if __name__=="__main__":
    main()
