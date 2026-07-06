import sys
import pickle
import os
import time
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem,
                             QTableWidget, QTableWidgetItem, QPushButton, QWidget,
                             QVBoxLayout, QHBoxLayout, QMessageBox,
                             QDialog, QTextEdit, QHeaderView, QLabel,
                             QStatusBar, QSplitter, QMenu, QAction, QToolBar,
                             QLineEdit, QAbstractItemView)
from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtGui import QIcon, QColor, QPixmap

# ==========系统常量============
BLOCK_COUNT = 128          # 磁盘总块数
BLOCK_SIZE = 64            # 每块字节数
SAVE_FILES = ["disk.dat", "fat.dat", "bitmap.dat", "dir.dat"]  # 持久化文件名

# ── 全局磁盘数据结构 ──
# disk[i] : 第 i 块的原始字节数据
# fat[i]  : -2=未使用, -1=链尾, 其他值=下一块号（显式链接分配）
# bitmap[i]: 0=空闲, 1=已占用
disk = [bytearray(BLOCK_SIZE) for _ in range(BLOCK_COUNT)]
fat = [-2] * BLOCK_COUNT
bitmap = [0] * BLOCK_COUNT


class FCB:
    
    def __init__(self, name, is_dir):
        self.name = name                # 文件/目录名
        self.is_dir = is_dir            # True=目录, False=文件
        self.start_block = -1           # 起始磁盘块号（-1 表示空文件）
        self.file_len = 0               # 文件字节数
        self.create_time = time.strftime("%Y-%m-%d %H:%M:%S")
        self.child = dict()             # 子节点映射 name → FCB（仅目录有效）
        self.parent = None              # 父目录 FCB（根目录为 None）


root = FCB("/", True)   # 根目录
cur_dir = root           # 当前工作目录指针


# =========磁盘操作============
def alloc_block():
    """分配一个空闲磁盘块，返回块号。位图扫描 + FAT 初始化。无空闲块时返回 -1。"""
    for idx in range(BLOCK_COUNT):
        if bitmap[idx] == 0:
            bitmap[idx] = 1
            fat[idx] = -1    # 暂时标记为链尾
            return idx
    return -1
def free_block(blk_id):
    """释放单个磁盘块：清零位图、重置 FAT、擦除数据。"""
    if 0 <= blk_id < BLOCK_COUNT:
        bitmap[blk_id] = 0
        fat[blk_id] = -2
        disk[blk_id][:] = b'\x00' * BLOCK_SIZE
def free_all_blocks(start):
    """沿 FAT 链释放从 start 开始的所有磁盘块。"""
    cur = start
    while cur != -1:
        nxt = fat[cur]
        free_block(cur)
        cur = nxt
def format_disk():
    """格式化：重置所有全局数据结构为初始状态。"""
    global disk, fat, bitmap, root, cur_dir
    disk = [bytearray(BLOCK_SIZE) for _ in range(BLOCK_COUNT)]
    fat = [-2] * BLOCK_COUNT
    bitmap = [0] * BLOCK_COUNT
    root = FCB("/", True)
    cur_dir = root


def save_system():
    """将当前文件系统状态序列化到 4 个 .dat 文件。"""
    with open("disk.dat", "wb") as f:
        pickle.dump(disk, f)
    with open("fat.dat", "wb") as f:
        pickle.dump(fat, f)
    with open("bitmap.dat", "wb") as f:
        pickle.dump(bitmap, f)
    with open("dir.dat", "wb") as f:
        pickle.dump(root, f)


def load_system():
    """从 .dat 文件恢复文件系统状态。任一文件缺失则自动格式化。"""
    global disk, fat, bitmap, root, cur_dir
    all_exist = all(os.path.exists(f) for f in SAVE_FILES)
    if not all_exist:
        format_disk()
        return
    try:
        with open("disk.dat", "rb") as f:
            disk = pickle.load(f)
        with open("fat.dat", "rb") as f:
            fat = pickle.load(f)
        with open("bitmap.dat", "rb") as f:
            bitmap = pickle.load(f)
        with open("dir.dat", "rb") as f:
            root = pickle.load(f)
        cur_dir = root
    except:
        format_disk()


def write_to_fcb(fcb, content: str):
    """将字符串内容写入 FCB 对应的文件。
    采用显式链接分配：按需分配磁盘块，通过 FAT 表串联。
    先释放旧块链，再逐块写入新数据。磁盘空间不足时返回 False 并回滚。
    """
    if fcb.start_block != -1:
        free_all_blocks(fcb.start_block)
        fcb.start_block = -1
        fcb.file_len = 0
    data = content.encode("utf-8")
    length = len(data)
    if length == 0:
        return True
    pos = 0
    pre = -1        # 前一个块号
    first = -1      # 起始块号
    while pos < length:
        blk = alloc_block()
        if blk == -1:
            free_all_blocks(first)   # 空间不足，回滚已分配的块
            return False
        if pre == -1:
            first = blk
        else:
            fat[pre] = blk           # 将前一块的 FAT 指向当前块
        wlen = min(BLOCK_SIZE, length - pos)
        disk[blk][:wlen] = data[pos:pos + wlen]
        pos += wlen
        pre = blk
    fat[pre] = -1    # 最后一块标记为链尾
    fcb.start_block = first
    fcb.file_len = length
    return True


def read_from_fcb(fcb):
    """沿 FAT 链读取 FCB 对应文件的全部内容，返回字符串。"""
    if fcb.start_block == -1:
        return ""
    buf = b""
    now = fcb.start_block
    while now != -1:
        buf += disk[now]
        now = fat[now]
    return buf[:fcb.file_len].decode("utf-8")   # 截断多余填充字节


# =========全局样式表（Qt QSS，仿 Windows 资源管理器风格）============
GLOBAL_QSS = """
QMainWindow {
    background-color: #f0f0f0;
}
QWidget#sidePanel {
    background-color: #fafafa;
    border-right: 1px solid #e0e0e0;
}
QWidget#mainPanel {
    background-color: #ffffff;
}
QWidget#addressBar {
    background-color: #f0f0f0;
    border-bottom: 1px solid #e0e0e0;
}

/* 全局默认字体 — 与地址栏统一 */
* {
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
}

/* 工具栏 */
QToolBar {
    background-color: #f5f5f5;
    border-bottom: 1px solid #e0e0e0;
    spacing: 4px;
    padding: 4px 8px;
}
QToolBar QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 5px 10px;
    color: #333;
    font-size: 14px;
}
QToolBar QToolButton:hover {
    background-color: #e0e0e0;
    border-color: #ccc;
}
QToolBar QToolButton:pressed {
    background-color: #d0d0d0;
}

/* 地址栏 */
QLineEdit#addrEdit {
    background-color: #ffffff;
    border: 1px solid #ccc;
    border-radius: 4px;
    padding: 6px 12px;
    font-size: 15px;
    color: #333;
}
QLineEdit#addrEdit:focus {
    border-color: #0078d4;
}

/* 树形控件 - 左侧导航 */
QTreeWidget {
    background-color: #fafafa;
    border: none;
    color: #333;
    font-size: 15px;
    outline: none;
    padding: 4px;
}
QTreeWidget::item {
    padding: 6px 10px;
    border-radius: 4px;
    min-height: 26px;
}
QTreeWidget::item:hover {
    background-color: #e8e8e8;
}
QTreeWidget::item:selected {
    background-color: #cce5ff;
    color: #1a1a1a;
}
QTreeWidget::branch:has-children:!has-siblings:closed,
QTreeWidget::branch:closed:has-children:has-siblings {
    image: none;
}
QTreeWidget::branch:open:has-children:!has-siblings,
QTreeWidget::branch:open:has-children:has-siblings {
    image: none;
}

/* 表格 - 右侧文件列表 */
QTableWidget {
    background-color: #ffffff;
    border: none;
    color: #333;
    font-size: 14px;
    gridline-color: #f0f0f0;
    outline: none;
    selection-background-color: #cce5ff;
    selection-color: #1a1a1a;
}
QTableWidget::item {
    padding: 8px 12px;
    border-bottom: 1px solid #f5f5f5;
}
QTableWidget::item:hover {
    background-color: #f0f7ff;
}
QTableWidget::item:selected {
    background-color: #cce5ff;
    color: #1a1a1a;
}
QTableWidget QHeaderView::section {
    background-color: #fafafa;
    color: #555;
    border: none;
    border-bottom: 1px solid #e0e0e0;
    border-right: 1px solid #eee;
    padding: 10px 12px;
    font-size: 13px;
    font-weight: 600;
}

/* 状态栏 */
QStatusBar {
    background-color: #f0f0f0;
    color: #666;
    border-top: 1px solid #e0e0e0;
    font-size: 13px;
    padding: 2px 8px;
}

/* 按钮 */
QPushButton {
    background-color: #ffffff;
    color: #333;
    border: 1px solid #ccc;
    border-radius: 4px;
    padding: 7px 18px;
    font-size: 14px;
}
QPushButton:hover {
    background-color: #e5f0fc;
    border-color: #0078d4;
}
QPushButton:pressed {
    background-color: #cce5ff;
}

/* 右键菜单 */
QMenu {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    padding: 6px 2px;
    border-radius: 8px;
}
QMenu::item {
    padding: 10px 40px 10px 18px;
    font-size: 14px;
}
QMenu::item:selected {
    background-color: #e5f0fc;
}
QMenu::separator {
    height: 1px;
    background-color: #e0e0e0;
    margin: 6px 10px;
}

/* 滚动条 */
QScrollBar:vertical {
    background: transparent;
    width: 12px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #c0c0c0;
    border-radius: 6px;
    min-height: 40px;
}
QScrollBar::handle:vertical:hover {
    background: #a0a0a0;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background: transparent;
    height: 12px;
}
QScrollBar::handle:horizontal {
    background: #c0c0c0;
    border-radius: 6px;
    min-width: 40px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* 分割器 */
QSplitter::handle {
    background-color: #e0e0e0;
    width: 1px;
}

/* 输入对话框 */
QInputDialog {
    background-color: #ffffff;
}
QInputDialog QLineEdit {
    padding: 8px 12px;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 14px;
}

/* 信息框 */
QMessageBox {
    background-color: #ffffff;
    font-size: 14px;
}
QMessageBox QPushButton {
    min-width: 80px;
    padding: 7px 18px;
    font-size: 14px;
}
"""

# =========简洁输入弹窗（无问号图标）============
class NameInputDialog(QDialog):
    """通用命名输入弹窗 —— 用于新建文件/文件夹、重命名等场景。"""
    def __init__(self, title, label, default=""):
        super().__init__()
        self.result_name = ""
        self.setWindowTitle(title)
        self.setFixedSize(380, 140)
        self.setStyleSheet("""
            QDialog { background-color: #ffffff; }
            QLabel { font-size: 14px; color: #333; }
            QLineEdit {
                padding: 6px 10px; border: 1px solid #ccc;
                border-radius: 4px; font-size: 14px;
            }
            QLineEdit:focus { border-color: #0078d4; }
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 12)
        lay.setSpacing(10)
        lbl = QLabel(label)
        lay.addWidget(lbl)
        self.edit = QLineEdit(default)
        self.edit.selectAll()                    # 默认全选，方便直接覆盖输入
        self.edit.returnPressed.connect(self._ok)
        lay.addWidget(self.edit)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_ok = QPushButton("确定")
        btn_ok.setStyleSheet("background:#0078d4;color:#fff;border:none;border-radius:4px;padding:6px 24px;font-size:14px;")
        btn_ok.clicked.connect(self._ok)
        btn_cancel = QPushButton("取消")
        btn_cancel.setStyleSheet("background:#fff;color:#333;border:1px solid #ccc;border-radius:4px;padding:6px 24px;font-size:14px;")
        btn_cancel.clicked.connect(self.close)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        lay.addLayout(btn_row)

    def _ok(self):
        self.result_name = self.edit.text().strip()
        self.accept()


# =========文件编辑弹窗============
class FileEditDialog(QDialog):
    """文本文件编辑器 —— 双击文件或右键编辑时弹出。
    读取文件内容到 QTextEdit，保存时写回 FCB 链。"""
    def __init__(self, fcb):
        super().__init__()
        self.fcb = fcb
        self.setWindowTitle(f"编辑 - {fcb.name}")
        self.resize(620, 460)
        self.setMinimumSize(400, 300)
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
            QTextEdit {
                background-color: #fafafa;
                color: #333;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 10px;
                font-size: 14px;
                font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
            }
            QTextEdit:focus {
                border-color: #0078d4;
            }
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        header = QLabel(f"<b style='color:#333;font-size:15px;'>{fcb.name}</b>"
                        f"<span style='color:#999;font-size:12px;'>  |  {fcb.create_time}</span>")
        lay.addWidget(header)

        self.text = QTextEdit()
        self.text.setText(read_from_fcb(fcb))
        lay.addWidget(self.text)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_save = QPushButton("保存")
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #0078d4; color: #fff; border: none;
                border-radius: 4px; padding: 8px 28px; font-size: 13px;
            }
            QPushButton:hover { background-color: #106ebe; }
            QPushButton:pressed { background-color: #005a9e; }
        """)
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.clicked.connect(self.save)
        btn_cancel = QPushButton("取消")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.close)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        lay.addLayout(btn_row)

    def save(self):
        """将编辑器内容写回 FCB 对应的磁盘块链。空间不足时弹出警告。"""
        cont = self.text.toPlainText()
        if write_to_fcb(self.fcb, cont):
            QMessageBox.information(self, "提示", "文件保存成功")
            self.close()
        else:
            QMessageBox.warning(self, "错误", "磁盘空间不足，保存失败")


# =========主窗口============
class MainWin(QMainWindow):
    """文件管理器主窗口。
    布局：顶部工具栏 + 地址栏 / 左侧目录树 / 右侧文件表格 / 底部状态栏。
    _cur_file_name 用于记住地址栏显示时当前选中的文件名。
    """
    def __init__(self):
        super().__init__()
        self._base_title = "文件管理器 - FAT 模拟文件系统"
        self._cur_file_name = None    # 非 None 表示地址栏定位到某个文件
        self.resize(1100, 700)
        self.setMinimumSize(800, 500)
        load_system()                 # 启动时恢复上次保存的状态
        self.setStyleSheet(GLOBAL_QSS)
        self.init_ui()
        self.refresh_tree()
        self.refresh_filelist()
        self.update_status()
        self._update_path_display()

    # ── 图标生成 ──
    def _file_icon(self):
        """用 emoji 渲染到 QPixmap 生成文件图标。"""
        pix = QPixmap(24, 24)
        pix.fill(Qt.transparent)
        lbl = QLabel("📄")
        lbl.setStyleSheet("font-size:18px;")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setFixedSize(24, 24)
        lbl.render(pix)
        return QIcon(pix)

    def _dir_icon(self):
        """用 emoji 渲染到 QPixmap 生成文件夹图标。"""
        pix = QPixmap(24, 24)
        pix.fill(Qt.transparent)
        lbl = QLabel("📁")
        lbl.setStyleSheet("font-size:18px;")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setFixedSize(24, 24)
        lbl.render(pix)
        return QIcon(pix)

    def init_ui(self):
        """构建主界面：工具栏 → 地址栏 → 左右分栏（树+表格） → 状态栏。"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── 工具栏 ──
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setIconSize(QPixmap(20, 20).size())

        act_newfile = QAction(self._file_icon(), "新建文件", self)
        act_newfile.triggered.connect(self.new_file)
        act_newdir = QAction(self._dir_icon(), "新建文件夹", self)
        act_newdir.triggered.connect(self.new_dir)
        act_rename = QAction("✎  重命名", self)
        act_rename.triggered.connect(self.rename_item)
        act_del = QAction("🗑  删除", self)
        act_del.triggered.connect(self.del_item)
        act_back = QAction("↩  上级", self)
        act_back.triggered.connect(self.go_parent)
        act_format = QAction("⚠  格式化", self)
        act_format.triggered.connect(self.format_disk)

        toolbar.addAction(act_back)
        toolbar.addSeparator()
        toolbar.addAction(act_newfile)
        toolbar.addAction(act_newdir)
        toolbar.addSeparator()
        toolbar.addAction(act_rename)
        toolbar.addAction(act_del)
        toolbar.addSeparator()
        toolbar.addAction(act_format)

        toolbar.addSeparator()
        addr_label = QLabel("  地址：")
        toolbar.addWidget(addr_label)
        self.addr_edit = QLineEdit()
        self.addr_edit.setObjectName("addrEdit")
        self.addr_edit.setFixedWidth(280)
        self.addr_edit.setPlaceholderText("输入路径后回车跳转...")
        self.addr_edit.returnPressed.connect(self.goto_path)
        toolbar.addWidget(self.addr_edit)

        main_layout.addWidget(toolbar)

        # ── 主体：左右分割 ──
        splitter = QSplitter(Qt.Horizontal)

        # 左侧边栏 — 目录树
        left_panel = QWidget()
        left_panel.setObjectName("sidePanel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 4, 8)
        left_layout.setSpacing(4)

        side_header = QLabel("  导航窗格")
        side_header.setStyleSheet("color:#555;font-size:14px;font-weight:bold;padding:4px 8px;")
        left_layout.addWidget(side_header)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(18)
        self.tree.setAnimated(True)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.tree_context_menu)
        self.tree.itemClicked.connect(self.tree_click)
        self.tree.itemDoubleClicked.connect(self.tree_double_click)
        self.tree.itemExpanded.connect(self.tree_item_expanded)
        self.tree.itemCollapsed.connect(self.tree_item_collapsed)
        left_layout.addWidget(self.tree)

        # 右侧 — 文件列表
        right_panel = QWidget()
        right_panel.setObjectName("mainPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(4, 8, 8, 8)
        right_layout.setSpacing(4)

        self.file_count_label = QLabel("")
        self.file_count_label.setStyleSheet("color:#888;font-size:14px;padding:4px 8px;")
        right_layout.addWidget(self.file_count_label)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["名称", "类型", "大小", "修改日期"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.table_context_menu)
        self.table.doubleClicked.connect(self.double_open)
        self.table.setSortingEnabled(True)
        # 单击也响应（文件夹导航）
        self.table.clicked.connect(self.single_click)
        right_layout.addWidget(self.table)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)
        splitter.setHandleWidth(1)
        main_layout.addWidget(splitter)

        # ── 状态栏 ──
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    # ── 辅助 ──
    def update_status(self):
        """更新状态栏：显示磁盘使用情况（已用块/总块/KB）和文件总数。"""
        used = sum(1 for b in bitmap if b == 1)
        free = BLOCK_COUNT - used
        total_kb = BLOCK_COUNT * BLOCK_SIZE / 1024
        used_kb = used * BLOCK_SIZE / 1024
        file_count = sum(1 for _ in self._iter_files(root))
        self.status_bar.showMessage(
            f"  磁盘: {total_kb:.0f} KB  |  已用 {used}/{BLOCK_COUNT} 块 ({used_kb:.0f} KB)  |  "
            f"空闲 {free}/{BLOCK_COUNT} 块  |  文件数: {file_count}"
        )

    def _iter_files(self, node):
        """递归遍历 FCB 树，生成所有文件节点（不含目录）。"""
        for v in node.child.values():
            if not v.is_dir:
                yield v
            else:
                yield from self._iter_files(v)

    def _full_path(self, node):
        """从 FCB 节点向上追溯到根，拼接出完整路径字符串。"""
        parts = []
        while node is not None:
            parts.append(node.name)
            node = node.parent
        return "/".join(reversed(parts)).replace("//", "/")

    def _update_path_display(self):
        """同步地址栏和窗口标题为当前路径（若 _cur_file_name 非空则拼上文件名）。"""
        path = self._full_path(cur_dir)
        if self._cur_file_name:
            path = path.rstrip("/") + "/" + self._cur_file_name
        self.addr_edit.setText(path)
        self.setWindowTitle(f"{self._base_title}  —  {path}")

    # ── 地址栏跳转 ──
    def goto_path(self):
        """解析地址栏路径并导航到目标目录/文件。
        路径最后一节若是文件则定位到该文件所在目录并高亮该文件。
        """
        global cur_dir
        path = self.addr_edit.text().strip()
        if not path:
            return
        self._cur_file_name = None
        if path == "/":
            cur_dir = root
        else:
            parts = [p for p in path.strip("/").split("/") if p]
            now = root
            for i, p in enumerate(parts):
                found = None
                for k, v in now.child.items():
                    if k == p:
                        found = v
                        break
                if found is None:
                    QMessageBox.warning(self, "路径错误", f"找不到: {p}")
                    return
                if found.is_dir:
                    now = found
                elif i == len(parts) - 1:        # 最后一节是文件
                    cur_dir = now
                    self._cur_file_name = p
                    self._update_path_display()
                    self.refresh_tree()
                    self.restore_tree_selection(cur_dir)
                    self.refresh_filelist()
                    self._select_file_in_table(p)
                    return
                else:
                    QMessageBox.warning(self, "路径错误", f"「{p}」不是目录")
                    return
            cur_dir = now
        self._update_path_display()
        self.refresh_tree()
        self.restore_tree_selection(cur_dir)
        self.refresh_filelist()

    def _select_file_in_table(self, name):
        """在右侧表格中按名称查找并选中某一行。"""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.text() == name:
                self.table.selectRow(row)
                self.table.scrollToItem(item)
                return

    # ── 返回上级 ──
    def go_parent(self):
        """返回父目录（根目录无父节点时不响应）。"""
        global cur_dir
        if cur_dir.parent is not None:
            self._cur_file_name = None
            cur_dir = cur_dir.parent
            self._update_path_display()
            self.refresh_tree()
            self.restore_tree_selection(cur_dir)
            self.refresh_filelist()

    def restore_tree_selection(self, target_fcb):
        """刷新树后恢复对目标 FCB 的高亮选中。"""
        def match(item, parts):
            if not parts:
                return item
            target = parts[0]
            for i in range(item.childCount()):
                child = item.child(i)
                if child.text(0) == target:
                    return match(child, parts[1:])
            return None
        path = self._full_path(target_fcb).strip("/").split("/")
        root_item = self.tree.topLevelItem(0)
        if root_item:
            matched = match(root_item, path[1:] if len(path) > 0 and path[0] == "" else path)
            if matched:
                self.tree.setCurrentItem(matched)
                self.tree.scrollToItem(matched)

    # ── 刷新树 ──
    def refresh_tree(self):
        """重建左侧目录树，从根 FCB 递归填充，默认全部展开。"""
        self.tree.clear()
        root_item = QTreeWidgetItem([root.name])
        root_item.setIcon(0, self._dir_icon())
        root_item.setData(0, Qt.UserRole, root)   # QTreeWidgetItem 关联 FCB 引用
        self.tree.addTopLevelItem(root_item)
        self.fill_tree(root_item, root)
        self.tree.expandAll()

    def fill_tree(self, qitem, fcb_node):
        """递归填充树节点：文件夹可展开子节点，文件非空则添加占位符以显示展开箭头。"""
        items = list(fcb_node.child.items())
        items.sort(key=lambda x: (not x[1].is_dir, x[0].lower()))
        for name, child_fcb in items:
            new_item = QTreeWidgetItem([name])
            new_item.setData(0, Qt.UserRole, child_fcb)  # 存储 FCB 引用
            if child_fcb.is_dir:
                new_item.setIcon(0, self._dir_icon())
                qitem.addChild(new_item)
                self.fill_tree(new_item, child_fcb)
            else:
                new_item.setIcon(0, self._file_icon())
                qitem.addChild(new_item)
                # 非空文件才显示展开箭头（展开后逐行显示内容）
                if child_fcb.file_len > 0:
                    new_item.addChild(QTreeWidgetItem(["..."]))

    # ── 树点击 ──
    def tree_click(self, item):
        """单击左侧目录树：目录则导航并刷新右侧列表。"""
        global cur_dir
        fcb = item.data(0, Qt.UserRole)
        if fcb is None:
            return
        if fcb.is_dir:
            self._cur_file_name = None
            cur_dir = fcb
            self._update_path_display()
            self.refresh_filelist()

    def tree_double_click(self, item):
        """双击左侧目录树：文件则打开编辑弹窗。"""
        fcb = item.data(0, Qt.UserRole)
        if fcb is None:
            return
        if not fcb.is_dir:
            dlg = FileEditDialog(fcb)
            dlg.exec_()
            self.refresh_filelist()

    # ── 树展开/折叠文件内容 ──
    def tree_item_expanded(self, item):
        """展开文件节点时：移除占位符 '...'，逐行加载文件内容作为只读子节点。"""
        fcb = item.data(0, Qt.UserRole)
        if fcb is None or fcb.is_dir:
            return
        item.takeChildren()
        content = read_from_fcb(fcb)
        for line in content.splitlines():
            child = QTreeWidgetItem([line])
            child.setDisabled(True)  # 只读，不可点击
            item.addChild(child)

    def tree_item_collapsed(self, item):
        """折叠文件节点时：清空内容行，放回占位符以保留展开箭头。"""
        fcb = item.data(0, Qt.UserRole)
        if fcb is None or fcb.is_dir:
            return
        item.takeChildren()
        item.addChild(QTreeWidgetItem(["..."]))

    # ── 刷新文件列表 ──
    def refresh_filelist(self):
        """刷新右侧表格，显示当前目录下所有子项。文件夹排在文件前面。"""
        self.table.setSortingEnabled(False)   # 填充数据时禁用排序，避免闪烁
        self.table.setRowCount(0)
        items = list(cur_dir.child.items())
        items.sort(key=lambda x: (not x[1].is_dir, x[0].lower()))
        self.file_count_label.setText(f"  {len(items)} 个项目")
        for row, (name, fcb) in enumerate(items):
            self.table.insertRow(row)

            name_item = QTableWidgetItem(name)
            name_item.setIcon(self._dir_icon() if fcb.is_dir else self._file_icon())

            if fcb.is_dir:
                type_item = QTableWidgetItem("文件夹")
                size_item = QTableWidgetItem("")
                color = QColor("#0066cc")
                name_item.setForeground(color)    # 目录名用蓝色
                type_item.setForeground(QColor("#666"))
                f = name_item.font()
                f.setBold(True)
                name_item.setFont(f)
            else:
                type_item = QTableWidgetItem("文本文档")
                size_str = f"{fcb.file_len} B" if fcb.file_len < 1024 else f"{fcb.file_len / 1024:.1f} KB"
                size_item = QTableWidgetItem(size_str)
                size_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                type_item.setForeground(QColor("#666"))

            time_item = QTableWidgetItem(fcb.create_time)
            time_item.setForeground(QColor("#888"))

            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, type_item)
            self.table.setItem(row, 2, size_item)
            self.table.setItem(row, 3, time_item)

            row_height = 36
            self.table.setRowHeight(row, row_height)

        self.table.setSortingEnabled(True)
        self.update_status()

    # ── 表格单击 ──
    def single_click(self, idx):
        """单击右侧表格：目录则导航，文件则在地址栏显示文件名。"""
        global cur_dir
        row = idx.row()
        if row >= self.table.rowCount():
            return
        name = self.table.item(row, 0)
        if name is None:
            return
        fcb = cur_dir.child.get(name.text())
        if fcb and fcb.is_dir:
            self._cur_file_name = None
            cur_dir = fcb
            self._update_path_display()
            self.refresh_tree()
            self.restore_tree_selection(cur_dir)
            self.refresh_filelist()
        elif fcb:
            self._cur_file_name = name.text()
            self._update_path_display()

    # ── 双击 ──
    def double_open(self, idx):
        """双击右侧表格：目录则进入，文件则打开编辑弹窗。"""
        global cur_dir
        row = idx.row()
        name_item = self.table.item(row, 0)
        if name_item is None:
            return
        name = name_item.text()
        fcb = cur_dir.child.get(name)
        if fcb is None:
            return
        if fcb.is_dir:
            self._cur_file_name = None
            cur_dir = fcb
            self._update_path_display()
            self.refresh_tree()
            self.restore_tree_selection(cur_dir)
            self.refresh_filelist()
        else:
            self._cur_file_name = name
            self._update_path_display()
            dlg = FileEditDialog(fcb)
            dlg.exec_()
            self.refresh_filelist()

    # ── 当前选中条目 ──
    def _selected_fcb(self):
        """获取右侧表格当前选中行对应的 FCB 引用。"""
        sel = self.table.selectedItems()
        if not sel:
            return None
        row = sel[0].row()
        name = self.table.item(row, 0)
        if name is None:
            return None
        return cur_dir.child.get(name.text())

    # ══════════ 右键菜单：文件列表 ══════════
    def table_context_menu(self, pos: QPoint):
        """右侧表格右键菜单 —— 根据是否有选中项动态启用/禁用操作。"""
        row = self.table.rowAt(pos.y())
        if row >= 0:
            self.table.selectRow(row)    # 右键前自动选中目标行

        menu = QMenu(self)

        act_open = menu.addAction("📂 打开")
        act_open.triggered.connect(lambda *_: QTimer.singleShot(0, self._menu_open))

        menu.addSeparator()

        act_newfile = menu.addAction("📄 新建文件")
        act_newfile.triggered.connect(lambda *_: QTimer.singleShot(0, self.new_file))
        act_newdir = menu.addAction("📁 新建文件夹")
        act_newdir.triggered.connect(lambda *_: QTimer.singleShot(0, self.new_dir))

        menu.addSeparator()

        act_rename = menu.addAction("✎ 重命名")
        act_rename.triggered.connect(lambda *_: QTimer.singleShot(0, self.rename_item))
        act_del = menu.addAction("🗑 删除")
        act_del.triggered.connect(lambda *_: QTimer.singleShot(0, self.del_item))

        menu.addSeparator()

        act_refresh = menu.addAction("🔄 刷新")
        act_refresh.triggered.connect(lambda: (self.refresh_tree(), self.refresh_filelist()))

        # 根据是否选中条目调整菜单项
        fcb = self._selected_fcb()
        if fcb is None:
            act_open.setEnabled(False)
            act_rename.setEnabled(False)
            act_del.setEnabled(False)
        else:
            if not fcb.is_dir:
                act_open.setText("✏ 编辑")    # 文件显示"编辑"，目录显示"打开"

        menu.exec_(self.table.viewport().mapToGlobal(pos))

    def _menu_open(self):
        """右键菜单"打开/编辑"回调：目录则导航，文件则弹出编辑器。"""
        global cur_dir
        fcb = self._selected_fcb()
        if fcb is None:
            return
        if fcb.is_dir:
            self._cur_file_name = None
            cur_dir = fcb
            self._update_path_display()
            self.refresh_tree()
            self.restore_tree_selection(cur_dir)
            self.refresh_filelist()
        else:
            self._cur_file_name = fcb.name
            self._update_path_display()
            dlg = FileEditDialog(fcb)
            dlg.exec_()
            self.refresh_filelist()

    # ══════════ 右键菜单：目录树 ══════════
    def tree_context_menu(self, pos: QPoint):
        """左侧目录树右键菜单 —— 右键目录时先切换到该目录，再弹出操作菜单。"""
        global cur_dir
        menu = QMenu(self)

        item = self.tree.itemAt(pos)
        fcb = item.data(0, Qt.UserRole) if item is not None else None
        clicked_is_dir = fcb is not None and fcb.is_dir

        # 右键文件夹时，先切到该目录（后续新建/重命名等操作作用于此目录）
        if clicked_is_dir:
            cur_dir = fcb

        # ── 打开 / 编辑 ──
        if fcb is not None:
            if fcb.is_dir:
                act_open = menu.addAction("📂 打开")
                act_open.triggered.connect(lambda *_, f=fcb: QTimer.singleShot(0, lambda: self._nav_to_dir(f)))
            else:
                act_edit = menu.addAction("✏ 编辑")
                act_edit.triggered.connect(lambda *_, f=fcb: QTimer.singleShot(0, lambda: self._edit_file(f)))
            menu.addSeparator()

        # ── 新建（仅在目录或空白处可用） ──
        if fcb is None or clicked_is_dir:
            act_newfile = menu.addAction("📄 新建文件")
            act_newfile.triggered.connect(lambda *_: QTimer.singleShot(0, self.new_file))
            act_newdir = menu.addAction("📁 新建文件夹")
            act_newdir.triggered.connect(lambda *_: QTimer.singleShot(0, self.new_dir))
            menu.addSeparator()

        # ── 重命名 / 删除（根目录不可操作） ──
        if fcb is not None and fcb is not root:
            act_rename = menu.addAction("✎ 重命名")
            act_rename.triggered.connect(lambda *_, f=fcb: QTimer.singleShot(0, lambda: self._rename_fcb(f)))
            act_del = menu.addAction("🗑 删除")
            act_del.triggered.connect(lambda *_, f=fcb: QTimer.singleShot(0, lambda: self._del_fcb(f)))
            menu.addSeparator()

        act_refresh = menu.addAction("🔄 刷新")
        act_refresh.triggered.connect(lambda: (self.refresh_tree(), self.refresh_filelist()))

        menu.exec_(self.tree.viewport().mapToGlobal(pos))

    # ── 树菜单辅助方法 ──
    def _nav_to_dir(self, fcb):
        """导航到指定目录并刷新界面。"""
        global cur_dir
        self._cur_file_name = None
        cur_dir = fcb
        self._update_path_display()
        self.refresh_tree()
        self.restore_tree_selection(cur_dir)
        self.refresh_filelist()

    def _edit_file(self, fcb):
        """打开文件编辑弹窗，关闭后刷新树和列表。"""
        self._cur_file_name = fcb.name
        self._update_path_display()
        dlg = FileEditDialog(fcb)
        dlg.exec_()
        self.refresh_tree()
        self.refresh_filelist()

    def _rename_fcb(self, fcb):
        """重命名 FCB：检查名称冲突后更新父目录的 child 映射。"""
        if fcb is root:
            QMessageBox.warning(self, "禁止操作", "根目录不能重命名")
            return
        old = fcb.name
        dlg = NameInputDialog("重命名", "请输入新名称：", default=old)
        if dlg.exec_() != QDialog.Accepted or not dlg.result_name or dlg.result_name == old:
            return
        new = dlg.result_name
        parent = fcb.parent if fcb.parent is not None else root
        if new in parent.child:
            QMessageBox.warning(self, "名称冲突", f"「{new}」已存在")
            return
        del parent.child[old]
        fcb.name = new
        parent.child[new] = fcb
        self.refresh_tree()
        self.restore_tree_selection(parent)
        self.refresh_filelist()

    def _del_fcb(self, fcb):
        """删除 FCB：非空目录拒绝删除，文件需先释放磁盘块链。"""
        global cur_dir
        if fcb is root:
            QMessageBox.warning(self, "禁止操作", "根目录不能删除")
            return
        if fcb.is_dir and len(fcb.child) > 0:
            QMessageBox.warning(self, "无法删除", f"文件夹「{fcb.name}」非空，请先清空内部文件")
            return
        ret = QMessageBox.question(self, "确认删除",
                                   f"确定要删除「{fcb.name}」吗？\n此操作不可恢复。")
        if ret != QMessageBox.Yes:
            return
        if not fcb.is_dir:
            free_all_blocks(fcb.start_block)    # 先释放磁盘空间
        parent = fcb.parent if fcb.parent is not None else root
        del parent.child[fcb.name]
        if cur_dir == fcb:
            cur_dir = parent    # 如果当前目录被删除，回退到父目录
        self._cur_file_name = None
        self._update_path_display()
        self.refresh_tree()
        self.restore_tree_selection(cur_dir)
        self.refresh_filelist()

    # ══════════ 操作 ══════════
    def format_disk(self):
        """格式化磁盘：二次确认后重置全部数据并刷新界面。"""
        ret = QMessageBox.question(self, "格式化磁盘",
                                   "⚠ 格式化将清空所有数据，此操作不可恢复！\n\n确定继续吗？")
        if ret == QMessageBox.Yes:
            format_disk()
            self._cur_file_name = None
            self.refresh_tree()
            self.refresh_filelist()
            self._update_path_display()
            QMessageBox.information(self, "完成", "磁盘已格式化")

    def new_file(self):
        """在当前目录下创建新文件 FCB（不分配磁盘块，编辑时才分配）。"""
        dlg = NameInputDialog("新建文件", "请输入文件名：")
        if dlg.exec_() != QDialog.Accepted or not dlg.result_name:
            return
        name = dlg.result_name
        if name in cur_dir.child:
            QMessageBox.warning(self, "名称冲突", f"「{name}」已存在")
            return
        newf = FCB(name, False)
        newf.parent = cur_dir
        cur_dir.child[name] = newf
        self.refresh_tree()
        self.restore_tree_selection(cur_dir)
        self.refresh_filelist()

    def new_dir(self):
        """在当前目录下创建新目录 FCB。"""
        dlg = NameInputDialog("新建文件夹", "请输入文件夹名：")
        if dlg.exec_() != QDialog.Accepted or not dlg.result_name:
            return
        name = dlg.result_name
        if name in cur_dir.child:
            QMessageBox.warning(self, "名称冲突", f"「{name}」已存在")
            return
        newd = FCB(name, True)
        newd.parent = cur_dir
        cur_dir.child[name] = newd
        self.refresh_tree()
        self.refresh_filelist()

    def del_item(self):
        """工具栏删除按钮：获取选中项后委托 _del_fcb 执行。"""
        fcb = self._selected_fcb()
        if fcb is None:
            QMessageBox.warning(self, "提示", "请先选中要删除的文件或文件夹")
            return
        self._del_fcb(fcb)

    def rename_item(self):
        """工具栏重命名按钮：获取选中项后委托 _rename_fcb 执行。"""
        fcb = self._selected_fcb()
        if fcb is None:
            QMessageBox.warning(self, "提示", "请先选中要重命名的项目")
            return
        self._rename_fcb(fcb)

    # ── 关闭 ──
    def closeEvent(self, e):
        """窗口关闭时询问是否持久化文件系统状态。"""
        res = QMessageBox.question(self, "退出",
                                   "是否保存文件系统到本地？\n\n"
                                   "「保存」— 保存后退出\n"
                                   "「不保存」— 直接退出（修改丢失）\n"
                                   "「取消」— 返回")
        if res == QMessageBox.Yes:
            save_system()
            e.accept()
        elif res == QMessageBox.No:
            e.accept()
        else:
            e.ignore()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")      # 跨平台一致外观
    win = MainWin()
    win.show()
    sys.exit(app.exec_())