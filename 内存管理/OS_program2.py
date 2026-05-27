import sys
import random
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor

# -------------------------- 操作系统内存管理 配置参数 --------------------------
TOTAL_INSTR = 320     # 作业总指令数
PAGE_SIZE = 10        # 页面大小：每个页面存放的指令数量
PAGE_COUNT = TOTAL_INSTR // PAGE_SIZE  # 32页
FRAME_COUNT = 4       # 物理内存块数量

# -------------------------- 界面配色方案 --------------------------
COLOR_PRIMARY = "#4F46E5"       
COLOR_PRIMARY_LIGHT = "#818CF8"
COLOR_ACCENT = "#06B6D4"       
COLOR_DANGER = "#EF4444"        
COLOR_SUCCESS = "#10B981"     
COLOR_WARNING = "#F59E0B"       
COLOR_BG = "#F1F5F9"           
COLOR_CARD = "#FFFFFF"          
COLOR_TEXT = "#1E293B"         
COLOR_TEXT_SECONDARY = "#64748B" 
COLOR_BORDER = "#E2E8F0"        
COLOR_FRAME_BG = "#F8FAFC"          
COLOR_FRAME_ACCENT = "#4F46E5"    
COLOR_HIGHLIGHT = "#F59E0B"        

# -------------------------- 全局界面样式表 --------------------------
GLOBAL_STYLE = """
QMainWindow {
    background-color: #F1F5F9;
}
QGroupBox {
    font-size: 15px;
    font-weight: bold;
    color: #1E293B;
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    margin-top: 16px;
    padding: 20px;
    padding-top: 32px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 16px;
    padding: 4px 12px;
    background-color: #4F46E5;
    color: white;
    border-radius: 6px;
}
QLabel {
    color: #1E293B;
}
QTableWidget {
    background-color: #FFFFFF;
    alternate-background-color: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    gridline-color: #E2E8F0;
    font-size: 13px;
    selection-background-color: #E0E7FF;
    selection-color: #1E293B;
}
QTableWidget::item {
    padding: 6px 8px;
}
QHeaderView::section {
    background-color: #4F46E5;
    color: white;
    font-weight: bold;
    font-size: 13px;
    padding: 10px 8px;
    border: none;
    border-right: 1px solid rgba(255,255,255,0.2);
}
QSpinBox {
    border: 2px solid #E2E8F0;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 13px;
    background: white;
}
QSpinBox:focus {
    border-color: #4F46E5;
}
QScrollBar:vertical {
    background: #F1F5F9;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #CBD5E1;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #94A3B8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""

# -------------------------- 页面置换模拟类 --------------------------
class PageSimulator:
    def __init__(self, algo='FIFO'):
        # 页面置换算法：FIFO/ LRU
        self.algo = algo
        # 物理内存块列表：存储(页号, 加载到内存的时间, 最近访问时间)
        self.frames = []         
        # 页表：操作系统核心数据结构，记录逻辑页号 → 物理内存块索引，-1表示不在内存
        self.page_table = {}     
        # 缺页次数：统计页面失效次数
        self.miss_count = 0
        # 执行步数：记录当前执行到第几条指令
        self.step = 0
        # 生成模拟的指令访问序列
        self.instr_seq = self._generate_instr_seq()

    def _generate_instr_seq(self):
        """按操作系统局部性原理生成指令序列:50%顺序执行,25%访问前半段,25%访问后半段"""
        seq = []
        m = random.randint(0, TOTAL_INSTR - 1)
        while len(seq) < TOTAL_INSTR:
            seq.append(m)
            if len(seq) >= TOTAL_INSTR:
                break
            # 顺序执行指令
            m = (m + 1) % TOTAL_INSTR
            seq.append(m)
            if len(seq) >= TOTAL_INSTR:
                break
            # 向前跳转（访问前半段）
            m = random.randint(0, m-1) if m > 0 else 0
            seq.append(m)
            if len(seq) >= TOTAL_INSTR:
                break
            # 向后跳转（访问后半段）
            m = random.randint(m+1, TOTAL_INSTR-1) if m < TOTAL_INSTR-1 else TOTAL_INSTR-1
        return seq[:TOTAL_INSTR]

    def addr_trans(self, instr):
        """操作系统地址转换：逻辑指令地址 → 逻辑页号 + 页内偏移"""
        return instr // PAGE_SIZE, instr % PAGE_SIZE

    def access(self, instr):
        """访问一条指令，执行分页管理流程：查页表→缺页/命中→页面置换"""
        self.step += 1
        # 地址转换，获取当前指令所属的逻辑页号
        page, _ = self.addr_trans(instr)
        evict_page = None
        is_miss = False

        # 情况1：缺页中断（页不在内存中）
        if self.page_table.get(page, -1) == -1:
            self.miss_count += 1
            is_miss = True
            # 子情况1：物理内存还有空闲块，直接加载页面
            if len(self.frames) < FRAME_COUNT:
                self.frames.append([page, self.step, self.step])
                self.page_table[page] = len(self.frames) - 1
            # 子情况2：内存已满，执行页面置换算法
            else:
                # FIFO：淘汰最早进入内存的页面
                if self.algo == 'FIFO':
                    idx = min(range(len(self.frames)), key=lambda x: self.frames[x][1])
                # LRU：淘汰最近最少使用的页面
                else:
                    idx = min(range(len(self.frames)), key=lambda x: self.frames[x][2])
                # 更新页表和内存块，完成页面置换
                evict_page = self.frames[idx][0]  # 1. 获取即将被淘汰（置换出去）的页面页号
                self.page_table[evict_page] = -1  # 2. 更新被淘汰页面的页表项：将其置为 -1，表示该页已不在物理内存中
                self.frames.pop(idx)              # 3. 从物理内存块中移除被淘汰的旧页面，释放该内存块空间
                self.frames.insert(idx, [page, self.step, self.step])# 4. 将新页面装入刚才释放的内存块位置
                self.page_table[page] = idx       # 5. 更新新页面的页表项：建立虚拟页 -> 物理内存块的映射关系
        # 情况2：页面命中（页已在内存中），更新最近访问时间
        else:
            idx = self.page_table[page]
            self.frames[idx][2] = self.step

        return page, evict_page, is_miss

    def reset(self, algo='FIFO'):
        """重置模拟环境，重新开始内存管理模拟"""
        self.algo = algo
        self.frames = []
        self.page_table = {}
        self.miss_count = 0
        self.step = 0
        self.instr_seq = self._generate_instr_seq()


# -------------------------- 主界面类 --------------------------
class PageSimulatorUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("内存管理 - 请求分页分配方式")
        self.setGeometry(100, 100, 1680, 780)
        # 绑定核心模拟逻辑
        self.sim = PageSimulator()
        # 定时器：用于连续执行指令
        self.timer = QTimer()
        self.timer.timeout.connect(self.step_execute)
        self.is_running = False
        # 记录已访问的指令，用于界面高亮
        self.accessed_instrs = {}     
        self.last_accessed_instr = None
        # 初始化界面
        self.init_ui()

    def init_ui(self):
        # 主窗口布局初始化
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setStyleSheet(f"background-color: {COLOR_BG};")
        self.setStyleSheet(GLOBAL_STYLE)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # 左侧：内存配置+统计信息面板
        left_panel = self._build_left_panel()
        main_layout.addWidget(left_panel)

        # 中间：物理内存块可视化面板
        mid_panel = self._build_mid_panel()
        main_layout.addWidget(mid_panel, 4)

        # 右侧：指令执行记录表面板
        right_panel = self._build_right_panel()
        main_layout.addWidget(right_panel, 3)

        self.update_ui()

    # ---------- 左侧：内存基本信息面板 ----------
    def _build_left_panel(self):
        panel = QGroupBox("基本信息")
        panel.setFixedWidth(310)
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)

        # 显示分页管理的核心配置参数
        config_card = QWidget()
        config_card.setStyleSheet(self._card_style("#F8FAFC"))
        config_layout = QVBoxLayout(config_card)
        config_layout.setSpacing(8)

        for label, value in [
            ("作业指令总数", f"{TOTAL_INSTR} 条"),
            ("每页存放指令数", f"{PAGE_SIZE} 条"),
            ("内存块数量", f"{FRAME_COUNT} 块"),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet("color:#64748B; font-size:12px; font-weight:normal;")
            val = QLabel(value)
            val.setStyleSheet("color:#1E293B; font-size:14px; font-weight:bold;")
            val.setAlignment(Qt.AlignRight)
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(val)
            config_layout.addLayout(row)

        # 置换算法切换按钮
        algo_label = QLabel("置换算法")
        algo_label.setStyleSheet("color:#64748B; font-size:12px; font-weight:normal;")
        config_layout.addWidget(algo_label)

        algo_btn_layout = QHBoxLayout()
        algo_btn_layout.setSpacing(0)
        self.btn_fifo = QPushButton("FIFO")
        self.btn_lru = QPushButton("LRU")
        for btn, algo in [(self.btn_fifo, "FIFO"), (self.btn_lru, "LRU")]:
            btn.setCheckable(True)
            btn.setFixedHeight(34)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, a=algo: self.switch_algo(a))
        self.btn_fifo.setChecked(True)
        self._update_algo_btn_style()

        algo_btn_layout.addWidget(self.btn_fifo)
        algo_btn_layout.addWidget(self.btn_lru)
        config_layout.addLayout(algo_btn_layout)

        layout.addWidget(config_card)

        # 运行时统计：缺页次数、缺页率、执行进度
        stats_card = QWidget()
        stats_card.setStyleSheet(self._card_style("#F8FAFC"))
        stats_layout = QVBoxLayout(stats_card)
        stats_layout.setSpacing(10)

        self.lbl_next_addr = self._make_stat_row(stats_layout, "下一条指令", "0", COLOR_PRIMARY)
        self.lbl_miss_count = self._make_stat_row(stats_layout, "缺页次数", "0", COLOR_DANGER)
        self.lbl_miss_rate = self._make_stat_row(stats_layout, "缺页率", "0%", COLOR_WARNING)

        # 执行进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, TOTAL_INSTR)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%v / %m")
        self.progress_bar.setFixedHeight(22)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 11px;
                background-color: #E2E8F0;
                text-align: center;
                font-size: 11px;
                color: #64748B;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4F46E5, stop:1 #818CF8);
                border-radius: 11px;
            }
        """)
        stats_layout.addWidget(self.progress_bar)

        layout.addWidget(stats_card)
        layout.addStretch()
        return panel

    def _make_stat_row(self, parent_layout, label, value, color):
        # 构造统计信息行
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setStyleSheet("color:#64748B; font-size:12px; font-weight:normal;")
        val = QLabel(value)
        val.setStyleSheet(f"color:{color}; font-size:20px; font-weight:bold;")
        val.setAlignment(Qt.AlignRight)
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(val)
        parent_layout.addLayout(row)
        return val

    def _card_style(self, bg_color):
        # 界面卡片样式
        return f"""
            background-color: {bg_color};
            border: 1px solid {COLOR_BORDER};
            border-radius: 10px;
            padding: 14px;
        """

    def _update_algo_btn_style(self):
        # 更新算法按钮样式
        fifo_active = self.btn_fifo.isChecked()
        lru_active = self.btn_lru.isChecked()
        self.btn_fifo.setStyleSheet(self._algo_btn_css(fifo_active, "left"))
        self.btn_lru.setStyleSheet(self._algo_btn_css(lru_active, "right"))

    def _algo_btn_css(self, active, side):
        # 算法按钮样式表
        if active:
            return f"""
                QPushButton {{
                    background: {COLOR_PRIMARY};
                    color: white;
                    border: 2px solid {COLOR_PRIMARY};
                    font-size: 13px;
                    font-weight: bold;
                    padding: 6px 16px;
                    {'border-top-left-radius: 8px; border-bottom-left-radius: 8px;' if side == 'left' else 'border-top-right-radius: 8px; border-bottom-right-radius: 8px;'}
                }}
            """
        else:
            return f"""
                QPushButton {{
                    background: white;
                    color: #94A3B8;
                    border: 2px solid #E2E8F0;
                    font-size: 13px;
                    padding: 6px 16px;
                    {'border-top-left-radius: 8px; border-bottom-left-radius: 8px;' if side == 'left' else 'border-top-right-radius: 8px; border-bottom-right-radius: 8px;'}
                }}
                QPushButton:hover {{
                    color: {COLOR_PRIMARY};
                    border-color: {COLOR_PRIMARY_LIGHT};
                }}
            """

    # ---------- 中间：内存块可视化面板 ----------
    def _build_mid_panel(self):
        panel = QGroupBox("内存页面图示")
        layout = QVBoxLayout(panel)
        layout.setSpacing(16)

        self.frame_widgets = []
        frame_layout = QHBoxLayout()
        frame_layout.setSpacing(12)

        frame_labels = ["内存块 0", "内存块 1", "内存块 2", "内存块 3"]
        # 创建4个物理内存块的可视化组件
        for i in range(FRAME_COUNT):
            card = QWidget()
            card.setObjectName(f"frame_{i}")
            card.setStyleSheet(f"""
                QWidget#{card.objectName()} {{
                    background: {COLOR_FRAME_BG};
                    border: 2px solid {COLOR_FRAME_ACCENT}22;
                    border-radius: 12px;
                }}
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 12, 12, 12)
            card_layout.setSpacing(8)

            # 内存块标题
            header = QHBoxLayout()
            block_tag = QLabel(frame_labels[i])
            block_tag.setStyleSheet(f"""
                background: {COLOR_FRAME_ACCENT};
                color: white;
                font-size: 11px;
                font-weight: bold;
                padding: 3px 10px;
                border-radius: 10px;
            """)
            header.addWidget(block_tag)
            header.addStretch()
            card_layout.addLayout(header)

            # 页号显示
            lbl_title = QLabel("— 空闲 —")
            lbl_title.setAlignment(Qt.AlignCenter)
            lbl_title.setStyleSheet(f"""
                font-size: 18px;
                font-weight: bold;
                color: {COLOR_FRAME_ACCENT};
                padding: 8px;
                background: {COLOR_FRAME_ACCENT}15;
                border-radius: 8px;
            """)
            card_layout.addWidget(lbl_title)

            # 指令地址滚动列表
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll.setStyleSheet(f"""
                QScrollArea {{ border: none; background: transparent; }}
                QScrollBar:vertical {{ width: 4px; background: transparent; }}
                QScrollBar::handle:vertical {{
                    background: {COLOR_FRAME_ACCENT}40;
                    border-radius: 2px;
                }}
            """)
            instr_container = QWidget()
            instr_container.setStyleSheet("background: transparent;")
            instr_list = QVBoxLayout(instr_container)
            instr_list.setSpacing(4)
            instr_list.setContentsMargins(0, 0, 0, 0)
            instr_list.addStretch()
            scroll.setWidget(instr_container)
            card_layout.addWidget(scroll)

            # 页面置换标记：提示即将被淘汰的页面
            marker = QLabel("")
            marker.setAlignment(Qt.AlignCenter)
            marker.setVisible(False)
            card_layout.addWidget(marker)

            self.frame_widgets.append({
                "widget": card,
                "title": lbl_title,
                "instr_list": instr_list,
                "marker": marker,
                "accent": COLOR_FRAME_ACCENT,
                "bg": COLOR_FRAME_BG,
            })
            frame_layout.addWidget(card)

        layout.addLayout(frame_layout)

        # 图例：缺页/命中标识
        legend = QHBoxLayout()
        legend.addStretch()
        for color, text in [(COLOR_DANGER, "缺页"), (COLOR_SUCCESS, "命中")]:
            dot = QLabel("●")
            dot.setStyleSheet(f"color:{color}; font-size:10px;")
            txt = QLabel(text)
            txt.setStyleSheet(f"color:#64748B; font-size:11px;")
            legend.addWidget(dot)
            legend.addWidget(txt)
            legend.addSpacing(12)
        layout.addLayout(legend)

        # 控制按钮：单步/连续/重置
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_single = QPushButton("▶ 单步执行")
        self.btn_continuous = QPushButton("▶▶ 连续执行")
        self.btn_reset = QPushButton("↻ 重置")

        self.btn_single.setStyleSheet(self._btn_css(COLOR_PRIMARY))
        self.btn_continuous.setStyleSheet(self._btn_css(COLOR_ACCENT))
        self.btn_reset.setStyleSheet(self._btn_css("#64748B"))

        self.btn_single.setCursor(Qt.PointingHandCursor)
        self.btn_continuous.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setCursor(Qt.PointingHandCursor)

        self.btn_single.clicked.connect(self.step_execute)
        self.btn_continuous.clicked.connect(self.toggle_continuous)
        self.btn_reset.clicked.connect(self.reset)

        for btn in [self.btn_single, self.btn_continuous, self.btn_reset]:
            btn.setFixedHeight(38)
            btn.setMinimumWidth(110)
            btn_layout.addWidget(btn)

        layout.addLayout(btn_layout)
        return panel

    def _btn_css(self, color):
        # 按钮样式
        return f"""
            QPushButton {{
                background: {color};
                color: white;
                border: none;
                border-radius: 19px;
                font-size: 14px;
                font-weight: bold;
                padding: 8px 22px;
            }}
            QPushButton:hover {{
                background: {color}DD;
            }}
            QPushButton:pressed {{
                background: {color}BB;
            }}
        """

    # ---------- 右侧：指令执行记录表 ----------
    def _build_right_panel(self):
        panel = QGroupBox("执行记录")
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        # 执行统计摘要
        summary = QHBoxLayout()
        self.lbl_summary = QLabel("等待执行...")
        self.lbl_summary.setStyleSheet("""
            font-size: 13px;
            color: #64748B;
            background: #F8FAFC;
            padding: 8px 14px;
            border-radius: 8px;
        """)
        summary.addWidget(self.lbl_summary)
        layout.addLayout(summary)

        # 执行记录表：序号、指令地址、命中/缺页、换出页、换入页
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["#", "指令地址", "状态", "换出页", "换入页"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 45)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        layout.addWidget(self.table)

        return panel

    # ---------- 界面控制逻辑 ----------
    def switch_algo(self, algo):
        """切换页面置换算法，重置模拟"""
        self.timer.stop()
        self.is_running = False
        self.btn_continuous.setText("▶▶ 连续执行")
        self.btn_fifo.setChecked(algo == "FIFO")
        self.btn_lru.setChecked(algo == "LRU")
        self._update_algo_btn_style()
        self.sim.reset(algo)
        self.reset()

    def toggle_continuous(self):
        """开始/暂停连续执行指令"""
        if self.is_running:
            self.timer.stop()
            self.btn_continuous.setText("▶▶ 连续执行")
            self.is_running = False
        else:
            self.timer.start(200)
            self.btn_continuous.setText("⏸ 暂停")
            self.is_running = True

    def step_execute(self):
        """单步执行：访问一条指令，完成一次内存管理流程"""
        # 执行完毕则停止
        if self.sim.step >= TOTAL_INSTR:
            self.timer.stop()
            self.btn_continuous.setText("▶▶ 连续执行")
            self.is_running = False
            return

        # 获取当前指令并执行内存访问
        instr = self.sim.instr_seq[self.sim.step]
        page, evict, missing = self.sim.access(instr)

        # 记录访问的指令
        if page not in self.accessed_instrs:
            self.accessed_instrs[page] = set()
        self.accessed_instrs[page].add(instr)
        self.last_accessed_instr = instr

        # 更新执行记录表格
        row = self.table.rowCount()
        self.table.insertRow(row)

        seq_item = QTableWidgetItem(str(self.sim.step))
        seq_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 0, seq_item)

        addr_item = QTableWidgetItem(str(instr))
        addr_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 1, addr_item)

        # 标记缺页/命中状态
        status_item = QTableWidgetItem("缺页 ▲" if missing else "命中 ●")
        status_item.setTextAlignment(Qt.AlignCenter)
        if missing:
            status_item.setForeground(QColor(COLOR_DANGER))
            status_item.setFont(QFont(status_item.font().family(), -1, QFont.Bold))
        else:
            status_item.setForeground(QColor(COLOR_SUCCESS))
        self.table.setItem(row, 2, status_item)

        # 换出页（置换时显示）
        evict_item = QTableWidgetItem(str(evict) if evict is not None else "—")
        evict_item.setTextAlignment(Qt.AlignCenter)
        evict_item.setForeground(QColor("#94A3B8") if evict is None else QColor(COLOR_DANGER))
        self.table.setItem(row, 3, evict_item)

        # 换入页
        in_item = QTableWidgetItem(str(page))
        in_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 4, in_item)

        self.table.scrollToBottom()
        # 高亮最新执行的记录
        self.table.selectRow(row)

        # 刷新整个界面
        self.update_ui()

    def update_ui(self):
        """刷新界面所有显示内容：统计信息、内存块、置换标记"""
        # 更新基础统计信息
        if self.sim.step < TOTAL_INSTR:
            self.lbl_next_addr.setText(str(self.sim.instr_seq[self.sim.step]))
        else:
            self.lbl_next_addr.setText("完成")
        self.lbl_miss_count.setText(str(self.sim.miss_count))
        rate = self.sim.miss_count / self.sim.step * 100 if self.sim.step > 0 else 0
        self.lbl_miss_rate.setText(f"{rate:.1f}%")
        self.progress_bar.setValue(self.sim.step)

        # 更新执行摘要
        self.lbl_summary.setText(f"已执行 {self.sim.step}/{TOTAL_INSTR} 条指令")

        # 更新内存块可视化：显示页号和指令地址
        for i, frame in enumerate(self.sim.frames):
            page_num, _, _ = frame
            fw = self.frame_widgets[i]
            fw["title"].setText(f"第 {page_num} 页")
            fw["title"].setStyleSheet(f"""
                font-size: 18px;
                font-weight: bold;
                color: {fw['accent']};
                padding: 8px;
                background: {fw['accent']}15;
                border-radius: 8px;
            """)
            # 清空原有指令，重新绘制
            while fw["instr_list"].count():
                item = fw["instr_list"].takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            # 显示当前页面的所有指令地址
            start = page_num * PAGE_SIZE
            end = start + PAGE_SIZE
            for addr in range(start, end):
                lbl = QLabel(f"{addr:03d}")
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setFixedHeight(30)
                # 高亮最近访问的指令
                if addr == self.last_accessed_instr:
                    lbl.setStyleSheet(f"""
                        background: {COLOR_HIGHLIGHT};
                        color: white;
                        font-size: 13px;
                        font-weight: bold;
                        border-radius: 4px;
                    """)
                else:
                    lbl.setStyleSheet(f"""
                        background: {fw['accent']}20;
                        color: {fw['accent']};
                        font-size: 13px;
                        font-weight: 500;
                        border-radius: 4px;
                    """)
                fw["instr_list"].addWidget(lbl)
            fw["instr_list"].addStretch()

        # 清空未使用的内存块，显示空闲
        for i in range(len(self.sim.frames), FRAME_COUNT):
            fw = self.frame_widgets[i]
            fw["title"].setText("— 空闲 —")
            fw["title"].setStyleSheet(f"""
                font-size: 18px;
                font-weight: bold;
                color: {fw['accent']}80;
                padding: 8px;
                background: {fw['accent']}10;
                border-radius: 8px;
            """)
            while fw["instr_list"].count():
                item = fw["instr_list"].takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            fw["instr_list"].addStretch()

        # 内存满时，标记即将被置换的页面（FIFO/LRU）
        if len(self.sim.frames) == FRAME_COUNT:
            if self.sim.algo == 'FIFO':
                evict_idx = min(range(len(self.sim.frames)), key=lambda x: self.sim.frames[x][1])
                marker_text = "⟵ 最先进入（将被替换）"
            else:
                evict_idx = min(range(len(self.sim.frames)), key=lambda x: self.sim.frames[x][2])
                marker_text = "⟵ 最久未用（将被替换）"
            for i in range(FRAME_COUNT):
                fw = self.frame_widgets[i]
                if i == evict_idx:
                    fw["marker"].setText(marker_text)
                    fw["marker"].setStyleSheet(f"""
                        font-size: 13px;
                        font-weight: bold;
                        color: {COLOR_HIGHLIGHT};
                        background: {COLOR_HIGHLIGHT}18;
                        padding: 6px 12px;
                        border-radius: 6px;
                    """)
                    fw["marker"].setVisible(True)
                else:
                    fw["marker"].setVisible(False)
        else:
            # 内存未满，隐藏置换标记
            for i in range(FRAME_COUNT):
                self.frame_widgets[i]["marker"].setVisible(False)

    def reset(self):
        """重置整个模拟程序和界面"""
        self.timer.stop()
        self.is_running = False
        self.btn_continuous.setText("▶▶ 连续执行")
        self.table.setRowCount(0)
        self.accessed_instrs = {}
        self.last_accessed_instr = None
        self.sim.reset(self.sim.algo)
        self.update_ui()


# -------------------------- 程序入口 --------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))
    window = PageSimulatorUI()
    window.show()
    sys.exit(app.exec_())