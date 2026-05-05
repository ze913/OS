import sys
import time
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QPainter, QColor, QBrush, QPen

# ====================== 系统资源配置 ======================
MAX_FLOOR = 20    # 最大楼层数
ELEVATOR_NUM = 5   # 电梯数量

# ====================== 电梯状态常量 ======================
STOP = 0       # 静止待机：进程处于就绪态
UP = 1         # 上行运行：进程处于运行态（上升）
DOWN = 2       # 下行运行：进程处于运行态（下降）
OPEN = 3       # 门开状态：进程处于阻塞态，等待开门操作完成
MANUAL_OPEN = 4# 手动开门状态：进程处于用户干预阻塞态，等待用户手动关门
ALARM = 5      # 报警锁定状态：进程处于中断处理态，优先响应报警中断

# --- 七段数码管类，用于显示电梯当前楼层 ---
class DigitalFloorDisplay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.number = 1  # 当前显示的楼层号（类比I/O设备的缓冲区）
        self.setFixedSize(120, 80)
        
        self.color_on = QColor(255, 30, 30)   # 数码管亮段颜色
        self.color_off = QColor(60, 20, 20)    # 数码管灭段颜色

    def setNumber(self, num):
        if 1 <= num <= 20:
            self.number = num
            self.update()  # 触发重绘

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), Qt.black)
        
        tens = self.number // 10
        ones = self.number % 10
        
        total_width = self.width()
        total_height = self.height()
        digit_width = (total_width - 20) // 2
        digit_height = total_height - 10
        margin_x = 5
        margin_y = 5

        self.draw_digit(painter, margin_x, margin_y, digit_width, digit_height, tens)
        self.draw_digit(painter, margin_x + digit_width + 10, margin_y, digit_width, digit_height, ones)

    def draw_digit(self, painter, x, y, w, h, digit):
        seg_map = {
            0: [1,1,1,1,1,1,0], 1: [0,1,1,0,0,0,0], 2: [1,1,0,1,1,0,1],
            3: [1,1,1,1,0,0,1], 4: [0,1,1,0,0,1,1], 5: [1,0,1,1,0,1,1],
            6: [1,0,1,1,1,1,1], 7: [1,1,1,0,0,0,0], 8: [1,1,1,1,1,1,1],
            9: [1,1,1,1,0,1,1]
        }
        
        if digit == 0 and x < self.width()//2: 
            segs = [0]*7
        else:
            segs = seg_map.get(digit, [0]*7)

        sw = max(4, int(w * 0.15))
        painter.setPen(Qt.NoPen)

        color = self.color_on if segs[0] else self.color_off
        painter.setBrush(QBrush(color))
        painter.drawRect(x + sw, y, w - 2*sw, sw)
        
        color = self.color_on if segs[1] else self.color_off
        painter.setBrush(QBrush(color))
        painter.drawRect(x + w - sw, y + sw, sw, (h//2) - sw - 2)
        
        color = self.color_on if segs[2] else self.color_off
        painter.setBrush(QBrush(color))
        painter.drawRect(x + w - sw, y + (h//2) + 2, sw, (h//2) - sw - 2)
        
        color = self.color_on if segs[3] else self.color_off
        painter.setBrush(QBrush(color))
        painter.drawRect(x + sw, y + h - sw, w - 2*sw, sw)
        
        color = self.color_on if segs[4] else self.color_off
        painter.setBrush(QBrush(color))
        painter.drawRect(x, y + (h//2) + 2, sw, (h//2) - sw - 2)
        
        color = self.color_on if segs[5] else self.color_off
        painter.setBrush(QBrush(color))
        painter.drawRect(x, y + sw, sw, (h//2) - sw - 2)
        
        color = self.color_on if segs[6] else self.color_off
        painter.setBrush(QBrush(color))
        painter.drawRect(x + sw, y + (h//2) - (sw//2), w - 2*sw, sw)

# --- 电梯门动画类，用于控制电梯门的开关 ---
class DoorAnimation(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(120, 60)
        self._open_ratio = 0.0  # 门开比例

        # 动画对象，异步执行门开关操作
        self.animation = QPropertyAnimation(self, b"open_ratio")
        self.animation.setDuration(600)  # 门开关时间
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

    @pyqtProperty(float)
    def open_ratio(self):
        return self._open_ratio

    @open_ratio.setter
    def open_ratio(self, value):
        self._open_ratio = max(0.0, min(1.0, value))
        self.update()

    def open_door(self):
        self.animation.stop()
        self.animation.setStartValue(self.open_ratio)
        self.animation.setEndValue(1.0)
        self.animation.start()

    def close_door(self):
        self.animation.stop()
        self.animation.setStartValue(self.open_ratio)
        self.animation.setEndValue(0.0)
        self.animation.start()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(30, 30, 30))
        
        w = self.width()
        h = self.height()
        door_width = int(w / 2 * (1 - self.open_ratio))

        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(200, 200, 200)))
        p.drawRect(0, 0, door_width, h)
        p.drawRect(w - door_width, 0, door_width, h)

        if self.open_ratio < 0.05:
            pen = QPen(QColor(0, 0, 0), 2)
            p.setPen(pen)
            p.drawLine(w//2, 0, w//2, h)

# ====================== 电梯类：继承QThread，模拟系统中的一个独立进程 ======================
class Elevator(QThread):
    # 信号量：模拟进程间通信机制，用于与父进程通信
    update_ui = pyqtSignal(int, int)  # 信号：通知UI线程刷新显示
    sig_open_door = pyqtSignal(int)   # 信号：发送开门请求
    sig_close_door = pyqtSignal(int)  # 信号：发送关门请求

    def __init__(self, eid):
        super().__init__()
        # ====================== 进程控制块（PCB） ======================
        self.id = eid          # 进程ID（PID）
        self.floor = 1         # 当前楼层（程序计数器PC）
        self.state = STOP      # 进程状态：state
        self.alarm = False     # 中断标志位：是否响应报警中断
        self.door_processing = False  # 互斥锁（Mutex）：保护开门临界区
        
        # ====================== 任务队列 ======================
        self.internal_tasks = set()       # 内部任务队列：电梯内按钮请求（高优先级就绪队列）
        self.external_up_tasks = set()    # 外部上行任务队列：楼层外上行呼叫（中优先级就绪队列）
        self.external_down_tasks = set()  # 外部下行任务队列：楼层外下行呼叫（低优先级就绪队列）

    # 添加内部任务到就绪队列
    def add_internal_task(self, floor):
        if 1 <= floor <= MAX_FLOOR:
            self.internal_tasks.add(floor)  # 加入高优先级就绪队列，set去重避免重复PCB

    # 添加外部任务到就绪队列
    def add_external_task(self, floor, direction):
        if 1 <= floor <= MAX_FLOOR:
            if direction == UP:
                self.external_up_tasks.add(floor)   # 加入上行就绪队列
            elif direction == DOWN:
                self.external_down_tasks.add(floor) # 加入下行就绪队列

    # 手动开门
    def manual_open_door(self):
        # 检查当前进程状态是否允许手动开门（运行态/中断态/临界区中禁止）
        if self.state in (UP, DOWN, ALARM) or self.door_processing:
            return False
        self.state = MANUAL_OPEN  # 切换到用户干预阻塞态
        self.sig_open_door.emit(self.id)  # 发送I/O请求到UI线程
        self.update_ui.emit(self.id, -1)  # 通知UI刷新状态
        return True

    # 手动关门
    def manual_close_door(self):
        # 检查是否处于手动开门状态且不在临界区
        if self.state != MANUAL_OPEN or self.door_processing:
            return False
        self.sig_close_door.emit(self.id)  # 发送关门I/O请求
        time.sleep(0.8)  # 等待I/O操作完成
        self.state = STOP  # 切换回就绪态
        self.update_ui.emit(self.id, -1)  # 通知UI刷新
        return True

    # 调度：检查当前楼层是否需要停靠
    def need_stop_current_floor(self):
        # 内部任务优先级最高，必停靠，抢占
        if self.floor in self.internal_tasks:
            return True
        # 外部任务仅同方向停靠
        if self.state == UP and self.floor in self.external_up_tasks:
            return True
        if self.state == DOWN and self.floor in self.external_down_tasks:
            return True
        return False

    # 调度：检查当前方向是否有未完成任务（SCAN调度算法的同方向任务检查）
    def has_same_direction_task(self):
        # 获取所有需要前往的目标楼层
        all_targets = self.get_all_task_floors()
        if self.state == UP:
            # 到达顶层无法继续上行，无同方向任务
            if self.floor >= MAX_FLOOR:
                return False
            # 上行：检查当前楼层以上是否有需要前往的目标
            for f in all_targets:
                if f > self.floor:
                    return True
            return False
        elif self.state == DOWN:
            # 到达底层无法继续下行，无同方向任务
            if self.floor <= 1:
                return False
            # 下行：检查当前楼层以下是否有需要前往的目标
            for f in all_targets:
                if f < self.floor:
                    return True
            return False
        return False

    # 调度：检查反方向是否有任务
    def has_reverse_direction_task(self):
        # 获取所有需要前往的目标楼层（无论任务方向）
        all_targets = self.get_all_task_floors()
        if self.state == UP:
            # 当前上行，检查当前楼层及以下是否有需要前往的目标（需换向下行）
            for f in all_targets:
                if f <= self.floor:
                    return True
            return False
        elif self.state == DOWN:
            # 当前下行，检查当前楼层及以上是否有需要前往的目标（需换向上行）
            for f in all_targets:
                if f >= self.floor:
                    return True
            return False
        return False

    # 调度：获取所有任务楼层
    def get_all_task_floors(self):
        return list(self.internal_tasks) + list(self.external_up_tasks) + list(self.external_down_tasks)

    # ====================== 进程主函数 ======================
    def run(self):
        while True:
            # ========== 中断处理：最高优先级 ==========
            if self.alarm:
                self.door_processing = False  # 释放临界区锁，防止死锁
                time.sleep(0.2)  # 等待
                continue

            # ========== 用户干预阻塞：等待用户手动关门 ==========
            if self.state == MANUAL_OPEN:
                time.sleep(0.2)  # 等待
                continue

            # ========== 临界区互斥：防止多个控制流同时进入开门流程 ==========
            if self.door_processing:
                time.sleep(0.1)  # 等待
                continue

            # ========== 状态1：就绪态（无任务），类似进程挂起 ==========
            total_tasks = len(self.get_all_task_floors())
            if total_tasks == 0:
                self.state = STOP  # 切换到就绪挂起态
                self.update_ui.emit(self.id, -1)  # 通知UI刷新状态
                time.sleep(0.2)  # 时间片轮转：等待下一个时间片
                continue

            # ========== 状态2：就绪态（有任务），调度器选择初始运行方向 ==========
            if self.state == STOP:
                all_tasks = self.get_all_task_floors()
                # 短作业优先：选择距离最近的任务作为初始方向
                nearest_floor = min(all_tasks, key=lambda x: abs(x - self.floor))
                if nearest_floor > self.floor:
                    self.state = UP    # 切换到上行运行态
                elif nearest_floor < self.floor:
                    self.state = DOWN  # 切换到下行运行态
                else:
                    # 刚好在任务楼层，直接开门
                    self.state = OPEN
                self.update_ui.emit(self.id, -1)  
                continue

            # ========== 状态3：阻塞态（自动开门） ==========
            if self.state == OPEN:
                self.door_processing = True  # 加锁：进入临界区
                arrived_floor = self.floor

                # 从就绪队列中移除已完成的任务
                if arrived_floor in self.internal_tasks:
                    self.internal_tasks.remove(arrived_floor)
                if arrived_floor in self.external_up_tasks:
                    self.external_up_tasks.remove(arrived_floor)
                if arrived_floor in self.external_down_tasks:
                    self.external_down_tasks.remove(arrived_floor)

                # 开门-保持-关门
                self.update_ui.emit(self.id, arrived_floor)  # 通知UI到达楼层
                self.sig_open_door.emit(self.id)             # 发送开门请求
                time.sleep(1.5)                               # 阻塞等待开门保持
                self.sig_close_door.emit(self.id)            # 发送关门请求
                time.sleep(0.8)                               # 阻塞等待关门完成

                # 退出临界区：释放锁
                self.door_processing = False
                self.state = STOP  # 切换回就绪态，等待下一次调度
                self.update_ui.emit(self.id, -1)  
                continue

            # ========== 状态4：运行态（上行/下行），SCAN调度算法 ==========
            # 先检查当前楼层是否需要停靠
            if self.need_stop_current_floor():
                self.state = OPEN  # 切换到阻塞态（开门）
                continue

            # SCAN算法：同方向任务全部处理完才换向
            if not self.has_same_direction_task():
                if self.has_reverse_direction_task():
                    # 换向
                    self.state = DOWN if self.state == UP else UP
                else:
                    # 无任务：切换回就绪态
                    self.state = STOP
                continue

            # 进程执行：楼层移动
            if self.state == UP and self.floor < MAX_FLOOR:
                self.floor += 1  # 上行：楼层+1
            elif self.state == DOWN and self.floor > 1:
                self.floor -= 1  # 下行：楼层-1

            # 时间片轮转：刷新UI后等待下一个时间片
            self.update_ui.emit(self.id, -1)
            time.sleep(0.3)  # 时间片长度：0.3秒

# ====================== 主窗口类：作业调度器和UI管理器 ======================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("电梯调度系统")
        self.setGeometry(100, 100, 1400, 950)

        # 创建ELEVATOR_NUM个电梯进程
        self.elevators = [Elevator(i) for i in range(ELEVATOR_NUM)]
        # UI组件数组：对应每个进程的I/O设备
        self.floor_displays = []
        self.state_labels = []
        self.door_animations = []
        self.elevator_buttons = [{} for _ in range(ELEVATOR_NUM)]  # 内部按钮：每个进程的用户输入设备
        self.external_buttons = {}  # 外部按钮：系统的全局输入设备

        # 绑定进程间通信信号
        for e in self.elevators:
            e.update_ui.connect(self.refresh_ui)  # UI刷新信号处理函数
            e.sig_open_door.connect(lambda eid: self.door_animations[eid].open_door())  # 开门信号处理
            e.sig_close_door.connect(lambda eid: self.door_animations[eid].close_door()) # 关门信号处理
            e.start()  # 启动电梯进程

        self.initUI()  # 初始化UI

    def initUI(self):
        main = QWidget()
        self.setCentralWidget(main)
        layout = QHBoxLayout(main)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # 左侧楼层呼叫面板
        left_layout = QVBoxLayout()
        left_layout.setSpacing(8)
        left_layout.addWidget(QLabel("📢 楼层呼叫"))

        for f in range(MAX_FLOOR, 0, -1):
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{f}F"))
            btn_up = QPushButton("↑")
            btn_down = QPushButton("↓")
            # 绑定作业提交事件：用户点击按钮提交作业，触发调度器的dispatch方法
            btn_up.clicked.connect(lambda _, x=f, btn=btn_up: self.dispatch(x, UP, btn))
            btn_down.clicked.connect(lambda _, x=f, btn=btn_down: self.dispatch(x, DOWN, btn))
            row.addWidget(btn_up)
            row.addWidget(btn_down)
            left_layout.addLayout(row)
            self.external_buttons[(f, "up")] = btn_up
            self.external_buttons[(f, "down")] = btn_down

        # 右侧电梯面板
        right_layout = QHBoxLayout()
        right_layout.setSpacing(30)

        for i in range(ELEVATOR_NUM):
            col = QVBoxLayout()
            col.setSpacing(10)
            col.setAlignment(Qt.AlignHCenter)

            # 电梯标题
            title = QLabel(f"电梯 {i+1}")
            title.setAlignment(Qt.AlignCenter)
            title.setStyleSheet("font-size:20px; font-weight:bold;")
            col.addWidget(title)

            # 七段数码管楼层显示
            fd = DigitalFloorDisplay()
            self.floor_displays.append(fd)
            hbox = QHBoxLayout()
            hbox.addStretch()
            hbox.addWidget(fd)
            hbox.addStretch()
            col.addLayout(hbox)

            # 状态显示
            sl = QLabel("静止")
            sl.setAlignment(Qt.AlignCenter)
            sl.setFixedSize(120,80)
            sl.setStyleSheet("background:black; color:white; font-size:18px; border-radius:3px;")
            self.state_labels.append(sl)
            sh = QHBoxLayout()
            sh.addStretch()
            sh.addWidget(sl)
            sh.addStretch()
            col.addLayout(sh)

            # 电梯门动画
            door = DoorAnimation()
            self.door_animations.append(door)
            dh = QHBoxLayout()
            dh.addStretch()
            dh.addWidget(door)
            dh.addStretch()
            col.addLayout(dh)

            # 电梯内楼层按钮
            grid = QGridLayout()
            grid.setSpacing(8)
            grid.setAlignment(Qt.AlignHCenter)
            numbers = list(range(1,21))
            numbers.reverse()

            for idx, n in enumerate(numbers):
                btn = QPushButton(str(n))
                btn.setFixedSize(55,45)
                btn.clicked.connect(lambda _,i=i,n=n,b=btn: self.on_elevator_btn_click(i,n,b))
                row = idx % 10
                col_idx = idx // 10
                grid.addWidget(btn, row, col_idx)
                self.elevator_buttons[i][n] = btn

            col.addLayout(grid)

            # 手动开关门按钮
            door_hbox = QHBoxLayout()
            door_hbox.setSpacing(5)
            door_hbox.addStretch()
            open_btn = QPushButton("开门")
            close_btn = QPushButton("关门")
            open_btn.setFixedSize(57,40)
            close_btn.setFixedSize(57,40)
            open_btn.clicked.connect(lambda _,i=i: self.manual_open(i))
            close_btn.clicked.connect(lambda _,i=i: self.manual_close(i))
            door_hbox.addWidget(open_btn)
            door_hbox.addWidget(close_btn)
            door_hbox.addStretch()
            col.addLayout(door_hbox)

            # 警报按钮
            alarm_hbox = QHBoxLayout()
            alarm_hbox.addStretch()
            alarm_btn = QPushButton("警报")
            alarm_btn.setFixedSize(120,50)
            alarm_btn.setStyleSheet("background:#ff4444; color:white; font-weight:bold;")
            alarm_btn.clicked.connect(lambda _,i=i: self.toggle_alarm(i))
            alarm_hbox.addWidget(alarm_btn)
            alarm_hbox.addStretch()
            col.addLayout(alarm_hbox)

            right_layout.addLayout(col)

        layout.addLayout(left_layout,1)
        layout.addLayout(right_layout,5)

    # 电梯内按钮点击事件
    def on_elevator_btn_click(self,eid,floor,btn):
        # 去重：已在任务列表中不重复添加
        if floor in self.elevators[eid].internal_tasks:
            return
        btn.setStyleSheet("background:#4CAF50; color:white; font-weight:bold;")
        self.elevators[eid].add_internal_task(floor)

    # ====================== 作业调度器：三级优先级调度算法 ======================
    def dispatch(self, f, direction, clicked_btn):
        # 全局去重：避免同一作业被重复提交到多个进程的就绪队列
        for e in self.elevators:
            if e.alarm:
                continue
            if direction == UP and f in e.external_up_tasks:
                return
            if direction == DOWN and f in e.external_down_tasks:
                return

        # 作业提交成功：按钮高亮
        clicked_btn.setStyleSheet("background:#4CAF50; color:white; font-weight:bold;")

        # 筛选可用进程：排除中断态和用户干预阻塞态的进程（只选择就绪态进程）
        available_elevators = [e for e in self.elevators if not e.alarm and e.state != MANUAL_OPEN]
        if not available_elevators:
            return

        # ========== 第一级调度：同方向优先（高优先级队列） ==========
        level1_candidates = []
        for e in available_elevators:
            # 规则1：运行方向与请求方向一致
            if e.state != direction:
                continue
            # 规则2：请求楼层在运行路径上
            if direction == UP and f < e.floor:
                continue
            if direction == DOWN and f > e.floor:
                continue
            level1_candidates.append(e)
        
        if level1_candidates:
            # 规则3：选距离最近的电梯
            best_elevator = min(level1_candidates, key=lambda x: abs(x.floor - f))
            best_elevator.add_external_task(f, direction)  # 作业提交到该进程的就绪队列
            return

        # ========== 第二级调度：静止优先（中优先级队列） ==========
        level2_candidates = [e for e in available_elevators if e.state == STOP]
        if level2_candidates:
            # 选距离最近的静止进程
            best_elevator = min(level2_candidates, key=lambda x: abs(x.floor - f))
            best_elevator.add_external_task(f, direction)
            return

        # ========== 第三级调度：最近距离兜底（低优先级队列） ==========
        best_elevator = min(available_elevators, key=lambda x: abs(x.floor - f))
        best_elevator.add_external_task(f, direction)

    # 手动开门
    def manual_open(self, eid):
        self.elevators[eid].manual_open_door()

    # 手动关门
    def manual_close(self, eid):
        self.elevators[eid].manual_close_door()

    # 报警开关
    def toggle_alarm(self,eid):
        e = self.elevators[eid]
        e.alarm = not e.alarm
        if e.alarm:
            e.state = ALARM  # 切换到中断处理态
            e.sig_close_door.emit(eid)  # 中断处理
        else:
            e.state = STOP  # 中断恢复：切换回就绪态
        e.update_ui.emit(eid, -1)  # 通知UI刷新

    # ====================== 中断处理程序：UI刷新 ======================
    def refresh_ui(self,eid, arrived_floor):
        e = self.elevators[eid]
        # 七段数码管显示当前楼层
        self.floor_displays[eid].setNumber(e.floor)

        # 刷新进程状态显示
        state_map = {
            STOP:"静止", UP:"↑上升", DOWN:"↓下降",
            OPEN:"门开", MANUAL_OPEN:"手动开门", ALARM:"报警"
        }
        state_text = state_map.get(e.state, "异常")
        self.state_labels[eid].setText(state_text)

        # 状态颜色区分
        if e.state == ALARM:
            self.state_labels[eid].setStyleSheet("background:#ff4444; color:white; font-size:18px; border-radius:3px;")
        elif e.state in (OPEN, MANUAL_OPEN):
            self.state_labels[eid].setStyleSheet("background:#2196F3; color:white; font-size:18px; border-radius:3px;")
        else:
            self.state_labels[eid].setStyleSheet("background:black; color:white; font-size:18px; border-radius:3px;")

        # 作业完成：恢复按钮样式
        if arrived_floor != -1:
            # 恢复内部按钮：该进程的内部任务完成
            inner_btn = self.elevator_buttons[eid].get(arrived_floor)
            if inner_btn:
                inner_btn.setStyleSheet("")
            
            # 恢复外部上行按钮：所有进程都无该上行任务时才恢复
            has_up_task = any(arrived_floor in ele.external_up_tasks for ele in self.elevators)
            if not has_up_task:
                up_btn = self.external_buttons.get((arrived_floor, "up"))
                if up_btn:
                    up_btn.setStyleSheet("")
            
            # 恢复外部下行按钮：所有进程都无该下行任务时才恢复
            has_down_task = any(arrived_floor in ele.external_down_tasks for ele in self.elevators)
            if not has_down_task:
                down_btn = self.external_buttons.get((arrived_floor, "down"))
                if down_btn:
                    down_btn.setStyleSheet("")

if __name__ == "__main__":
    app = QApplication(sys.argv)  # 初始化UI进程
    win = MainWindow()             # 创建主窗口
    win.show()                     # 显示UI
    sys.exit(app.exec_())          # 进入UI事件循环