import sys
import time
import queue
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QPainter, QColor, QBrush, QPen

# 配置123
MAX_FLOOR = 20
ELEVATOR_NUM = 5

STOP = 0
UP = 1
DOWN = 2
OPEN = 3
ALARM = 4

# --- 七段数码管显示类（完全保留） ---
class DigitalFloorDisplay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.number = 1
        self.setFixedSize(120, 80)
        
        self.color_on = QColor(255, 30, 30)
        self.color_off = QColor(60, 20, 20)

    def setNumber(self, num):
        if 1 <= num <= 20:
            self.number = num
            self.update()

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

# --- 电梯门动画（保留） ---
class DoorAnimation(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(120, 60)
        self._open_ratio = 0.0

        self.animation = QPropertyAnimation(self, b"open_ratio")
        self.animation.setDuration(600)
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

# ====================== 核心：极简电梯类，回到最稳定的FIFO逻辑 ======================
class Elevator(QThread):
    update_ui = pyqtSignal(int, int) # (电梯id, 到达的楼层)
    sig_open_door = pyqtSignal(int)
    sig_close_door = pyqtSignal(int)

    def __init__(self, eid):
        super().__init__()
        self.id = eid
        self.floor = 1
        self.state = STOP
        self.targets = queue.Queue() # 只用一个简单队列，FIFO，绝对不乱
        self.alarm = False
        self.last_arrived_floor = None # 专门记录上一次到达的楼层，用于恢复按钮

    def add_target(self, f):
        if 1 <= f <= 20:
            self.targets.put(f)

    def run(self):
        while True:
            if self.alarm:
                time.sleep(0.2)
                continue

            if self.targets.empty():
                self.state = STOP
                self.update_ui.emit(self.id, -1) # -1表示不需要恢复按钮
                time.sleep(0.2)
                continue

            tar = self.targets.get()
            self.last_arrived_floor = tar

            # 移动到目标
            while self.floor != tar:
                if self.alarm: break
                if self.floor < tar:
                    self.state = UP
                    self.floor += 1
                else:
                    self.state = DOWN
                    self.floor -= 1
                self.update_ui.emit(self.id, -1)
                time.sleep(0.3)

            if self.alarm: continue

            # 到达
            self.state = OPEN
            self.update_ui.emit(self.id, self.last_arrived_floor) # 发送到达楼层，恢复按钮
            self.sig_open_door.emit(self.id)
            time.sleep(1.5)
            self.sig_close_door.emit(self.id)
            time.sleep(0.8)
            self.state = STOP
            self.update_ui.emit(self.id, -1)

# 主窗口
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("电梯调度系统 20层 5部")
        self.setGeometry(100, 100, 1400, 950)

        self.elevators = [Elevator(i) for i in range(ELEVATOR_NUM)]
        self.floor_displays = []
        self.state_labels = []
        self.door_animations = []
        self.elevator_buttons = [{} for _ in range(ELEVATOR_NUM)]
        self.external_buttons = {}

        for e in self.elevators:
            e.update_ui.connect(self.refresh_ui)
            e.sig_open_door.connect(lambda eid: self.door_animations[eid].open_door())
            e.sig_close_door.connect(lambda eid: self.door_animations[eid].close_door())
            e.start()

        self.initUI()

    def initUI(self):
        main = QWidget()
        self.setCentralWidget(main)
        layout = QHBoxLayout(main)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # ====================== 完全恢复你原来的左侧UI ======================
        left_layout = QVBoxLayout()
        left_layout.setSpacing(8)
        left_layout.addWidget(QLabel("📢 楼层呼叫"))

        for f in range(MAX_FLOOR, 0, -1):
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{f}F"))
            btn_up = QPushButton("↑")
            btn_down = QPushButton("↓")
            btn_up.clicked.connect(lambda _, x=f, btn=btn_up: self.dispatch(x, btn))
            btn_down.clicked.connect(lambda _, x=f, btn=btn_down: self.dispatch(x, btn))
            row.addWidget(btn_up)
            row.addWidget(btn_down)
            left_layout.addLayout(row)
            self.external_buttons[(f, "up")] = btn_up
            self.external_buttons[(f, "down")] = btn_down

        # 右侧电梯
        right_layout = QHBoxLayout()
        right_layout.setSpacing(30)

        for i in range(ELEVATOR_NUM):
            col = QVBoxLayout()
            col.setSpacing(10)
            col.setAlignment(Qt.AlignHCenter)

            title = QLabel(f"电梯 {i+1}")
            title.setAlignment(Qt.AlignCenter)
            title.setStyleSheet("font-size:20px; font-weight:bold;")
            col.addWidget(title)

            # 数码管
            fd = DigitalFloorDisplay()
            self.floor_displays.append(fd)
            hbox = QHBoxLayout()
            hbox.addStretch()
            hbox.addWidget(fd)
            hbox.addStretch()
            col.addLayout(hbox)

            # 状态
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

            # 门动画
            door = DoorAnimation()
            self.door_animations.append(door)
            dh = QHBoxLayout()
            dh.addStretch()
            dh.addWidget(door)
            dh.addStretch()
            col.addLayout(dh)

            # 按钮从下往上 1→20
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

            # 开门/关门按钮
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

    def on_elevator_btn_click(self,eid,floor,btn):
        btn.setStyleSheet("background:#4CAF50; color:white; font-weight:bold;")
        self.elevators[eid].add_target(floor)

    # 简单调度：找最近的
    def dispatch(self,f,clicked_btn):
        clicked_btn.setStyleSheet("background:#4CAF50; color:white; font-weight:bold;")
        best = 0
        min_d = 999
        for i,e in enumerate(self.elevators):
            if e.alarm: continue
            d = abs(e.floor - f)
            if d < min_d:
                min_d = d
                best = i
        self.elevators[best].add_target(f)

    def manual_open(self, eid):
        e = self.elevators[eid]
        if e.state != UP and e.state != DOWN and not e.alarm:
            self.door_animations[eid].open_door()
            e.state = OPEN

    def manual_close(self, eid):
        e = self.elevators[eid]
        if e.state != UP and e.state != DOWN and not e.alarm:
            self.door_animations[eid].close_door()
            e.state = STOP

    def toggle_alarm(self,eid):
        e = self.elevators[eid]
        e.alarm = not e.alarm
        e.state = ALARM if e.alarm else STOP

    # ====================== 核心：UI刷新，直接根据到达楼层恢复按钮 ======================
    def refresh_ui(self,eid, arrived_floor):
        e = self.elevators[eid]
        self.floor_displays[eid].setNumber(e.floor)

        m = {STOP:"静止",UP:"↑上升",DOWN:"↓下降",OPEN:"门开",ALARM:"报警"}
        self.state_labels[eid].setText(m[e.state])

        # 如果 arrived_floor 不是 -1，说明到达了新楼层，恢复按钮
        if arrived_floor != -1:
            # 恢复内部按钮
            btn = self.elevator_buttons[eid].get(arrived_floor)
            if btn:
                btn.setStyleSheet("")
            # 恢复外部按钮（同楼层所有）
            for key in self.external_buttons:
                if key[0] == arrived_floor:
                    self.external_buttons[key].setStyleSheet("")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())