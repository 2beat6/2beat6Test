import sys
import os
import requests
import datetime
import json
import time
import random
from collections import defaultdict
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton, QComboBox, QVBoxLayout, QHBoxLayout, QWidget, QProgressBar,
    QTreeWidget, QTreeWidgetItem, QLineEdit, QCalendarWidget, QDialog, QDialogButtonBox, QListWidget, QListWidgetItem,
    QMessageBox, QAction, QFormLayout, QToolBar, QSizePolicy, QTabWidget, QColorDialog, QInputDialog, QGridLayout,
    QCheckBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QSize
from PyQt5.QtGui import QIcon, QColor, QBrush, QTextDocument

from queue import Queue
import threading

# Replace with your actual live access token
ACCESS_TOKEN = 'EAAAl3pIAhQrKkoBcqkkzu1ZEKkRZYlggAFDUQkZlz_v57rjWy_aPAGaKp8ABmn7'
API_VERSION = '2024-07-01'

class InventoryManager:
    def __init__(self, json_file):
        with open(json_file) as f:
            self.inventory_data = json.load(f)
    
    def get_item_details(self, variation_id):
        for item_id, item in self.inventory_data.items():
            if item['variation_id'] == variation_id:
                return item
        return None

class CalendarDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Select Date')
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(self.calendar)
        layout.addWidget(self.button_box)
        self.setLayout(layout)

    def selected_date(self):
        return self.calendar.selectedDate()

class CustomDateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Select Custom Date Range')
        
        self.start_calendar = QCalendarWidget()
        self.end_calendar = QCalendarWidget()
        
        self.start_time_combo = QComboBox()
        self.start_time_combo.addItems([f"{i % 12 or 12} {'AM' if i < 12 else 'PM'}" for i in range(24)])
        self.start_time_combo.setCurrentIndex(6)  # Default to 6 AM
        
        self.end_time_combo = QComboBox()
        self.end_time_combo.addItems([f"{i % 12 or 12} {'AM' if i < 12 else 'PM'}" for i in range(24)])
        self.end_time_combo.setCurrentIndex(6)  # Default to 6 AM
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        
        layout = QFormLayout()
        layout.addRow("Start Date:", self.start_calendar)
        layout.addRow("Start Time:", self.start_time_combo)
        layout.addRow("End Date:", self.end_calendar)
        layout.addRow("End Time:", self.end_time_combo)
        layout.addRow(self.button_box)
        
        self.setLayout(layout)
    
    def get_date_range(self):
        start_date = self.start_calendar.selectedDate()
        end_date = self.end_calendar.selectedDate()
        start_time = self.start_time_combo.currentText()
        end_time = self.end_time_combo.currentText()
        return start_date, start_time, end_date, end_time

class Flag:
    def __init__(self, name, icon, color, condition, value):
        self.name = name
        self.icon = icon
        self.color = color
        self.condition = condition
        self.value = value

class FlagsManager:
    def __init__(self):
        self.flags = []

    def add_flag(self, flag):
        self.flags.append(flag)

    def remove_flag(self, flag):
        self.flags.remove(flag)

    def get_flags(self):
        return self.flags

class FlagsDialog(QDialog):
    def __init__(self, flags_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Flags')
        self.flags_manager = flags_manager

        self.layout = QVBoxLayout()

        self.create_flag_button = QPushButton("+ Create Flag")
        self.create_flag_button.clicked.connect(self.open_create_flag_dialog)
        
        self.flags_list = QListWidget()
        self.flags_list.itemDoubleClicked.connect(self.edit_flag)

        self.layout.addWidget(self.flags_list)
        self.layout.addWidget(self.create_flag_button)

        self.setLayout(self.layout)
        self.update_flags_list()

    def open_create_flag_dialog(self):
        create_flag_dialog = CreateFlagDialog(self.flags_manager, self)
        if create_flag_dialog.exec():
            self.update_flags_list()

    def edit_flag(self, item):
        flag = item.data(Qt.UserRole)
        create_flag_dialog = CreateFlagDialog(self.flags_manager, self, flag)
        if create_flag_dialog.exec():
            self.update_flags_list()

    def update_flags_list(self):
        self.flags_list.clear()
        for flag in self.flags_manager.get_flags():
            item = QListWidgetItem(flag.name)
            item.setData(Qt.UserRole, flag)
            if flag.icon:
                item.setIcon(QIcon(flag.icon))
            self.flags_list.addItem(item)

class CreateFlagDialog(QDialog):
    def __init__(self, flags_manager, parent=None, flag=None):
        super().__init__(parent)
        self.setWindowTitle('Create Flag')
        self.flags_manager = flags_manager
        self.flag = flag

        self.flag_name = QLineEdit()
        self.condition_combo = QComboBox()
        self.condition_combo.addItems(["Greater than", "Less than", "Equal to"])
        self.value_type_combo = QComboBox()
        self.value_type_combo.addItems(["$", "%"])
        self.value_input = QLineEdit()
        self.highlight_color_checkbox = QCheckBox("Highlight Color")
        self.highlight_color_button = QPushButton("Select Color")
        self.highlight_color_button.clicked.connect(self.select_color)
        self.highlight_color_button.setEnabled(False)
        self.highlight_color_checkbox.stateChanged.connect(self.highlight_color_button.setEnabled)

        self.icon_checkbox = QCheckBox("Icon")
        self.icon_picker_button = QPushButton("Select Icon")
        self.icon_picker_button.clicked.connect(self.open_icon_picker)
        self.icon_picker_button.setEnabled(False)
        self.icon_checkbox.stateChanged.connect(self.icon_picker_button.setEnabled)
        self.selected_icon_path = None
        self.selected_color = None

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout = QFormLayout()
        layout.addRow("Flag Name:", self.flag_name)
        layout.addRow("Condition:", self.condition_combo)
        layout.addRow("Value Type:", self.value_type_combo)
        layout.addRow("Value:", self.value_input)
        layout.addRow(self.highlight_color_checkbox)
        layout.addRow("Select Color:", self.highlight_color_button)
        layout.addRow(self.icon_checkbox)
        layout.addRow("Select Icon:", self.icon_picker_button)
        layout.addWidget(self.button_box)

        self.setLayout(layout)

        if self.flag:
            self.load_flag_details()

    def load_flag_details(self):
        self.flag_name.setText(self.flag.name)
        self.condition_combo.setCurrentText(self.flag.condition)
        self.value_input.setText(str(self.flag.value))
        self.highlight_color_checkbox.setChecked(self.flag.color is not None)
        if self.flag.color:
            self.selected_color = self.flag.color
        self.icon_checkbox.setChecked(self.flag.icon is not None)
        if self.flag.icon:
            self.selected_icon_path = self.flag.icon

    def select_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.selected_color = color

    def open_icon_picker(self):
        icon_picker_dialog = IconPickerDialog(self)
        if icon_picker_dialog.exec():
            self.selected_icon_path = icon_picker_dialog.get_selected_icon_path()

    def accept(self):
        flag_name = self.flag_name.text()
        condition = self.condition_combo.currentText()
        value_type = self.value_type_combo.currentText()
        value = float(self.value_input.text()) if self.value_input.text() else None
        color = self.selected_color if self.highlight_color_checkbox.isChecked() else None
        icon = self.selected_icon_path if self.icon_checkbox.isChecked() else None

        if flag_name and condition and value_type and value is not None:
            if self.flag:
                self.flag.name = flag_name
                self.flag.icon = icon
                self.flag.color = color
                self.flag.condition = condition
                self.flag.value = value
            else:
                new_flag = Flag(flag_name, icon, color, condition, value)
                self.flags_manager.add_flag(new_flag)
            super().accept()

class IconPickerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Select Icon')
        self.selected_icon_path = None

        self.grid_layout = QGridLayout()
        self.load_icons()

        self.setLayout(self.grid_layout)

    def load_icons(self):
        icon_dir = os.path.join(os.path.dirname(__file__), 'icon')  # Ensure the path is correct
        if not os.path.exists(icon_dir):
            QMessageBox.critical(self, "Error", f"Icon directory not found: {icon_dir}")
            return

        icons = [f for f in os.listdir(icon_dir) if os.path.isfile(os.path.join(icon_dir, f))]
        row = 0
        col = 0
        for icon in icons:
            icon_path = os.path.join(icon_dir, icon)
            icon_button = QPushButton()
            icon_button.setIcon(QIcon(icon_path))
            icon_button.setIconSize(QSize(64, 64))
            icon_button.clicked.connect(lambda _, path=icon_path: self.select_icon(path))
            self.grid_layout.addWidget(icon_button, row, col)
            col += 1
            if col > 3:  # 4 icons per row
                col = 0
                row += 1

    def select_icon(self, icon_path):
        self.selected_icon_path = icon_path
        self.accept()

    def get_selected_icon_path(self):
        return self.selected_icon_path

class WorkerThread(QThread):
    update_progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict, float, dict)

    def __init__(self, start_time, end_time, selected_locations):
        super().__init__()
        self.start_time = start_time
        self.end_time = end_time
        self.selected_locations = selected_locations
        self.lock = threading.Lock()
        self.all_orders = defaultdict(list)
        self.total_tips = 0.0
        self.tips_by_location = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    def exponential_backoff(self, retries):
        return min(60, (2 ** retries) + (random.randint(0, 1000) / 1000))

    def run(self):
        queue = Queue()
        
        def fetch_location_data(location):
            location_id, location_name = location
            retries = 0
            max_retries = 5
            cursor = None
            while True:
                endpoint = f'https://connect.squareup.com/v2/orders/search'
                headers = {
                    'Square-Version': API_VERSION,
                    'Authorization': f'Bearer {ACCESS_TOKEN}',
                    'Content-Type': 'application/json'
                }
                body = {
                    "location_ids": [location_id],
                    "query": {
                        "filter": {
                            "date_time_filter": {
                                "created_at": {
                                    "start_at": self.start_time.isoformat(),
                                    "end_at": self.end_time.isoformat()
                                }
                            }
                        }
                    }
                }
                if cursor:
                    body['cursor'] = cursor
                response = requests.post(endpoint, headers=headers, json=body)
                if response.status_code == 200:
                    retries = 0  # Reset retries on success
                    order_data = response.json()
                    orders = order_data.get('orders', [])
                    with self.lock:
                        self.all_orders[location_name].extend(orders)
                    for order in orders:
                        tip_amount = float(order.get('total_tip_money', {}).get('amount', 0)) / 100
                        order_date = order['created_at'].split('T')[0]
                        try:
                            order_time = datetime.datetime.strptime(order['created_at'], "%Y-%m-%dT%H:%M:%S.%f%z").astimezone()
                        except ValueError:
                            try:
                                order_time = datetime.datetime.strptime(order['created_at'], "%Y-%m-%dT%H:%M:%S%z").astimezone()
                            except ValueError:
                                order_time = datetime.datetime.strptime(order['created_at'], "%Y-%m-%dT%H:%M:%SZ").astimezone()

                        order_hour = order_time.strftime('%I %p').lower()
                        next_hour = (order_time + datetime.timedelta(hours=1)).strftime('%I %p').lower()
                        time_range = f"{order_hour} - {next_hour}"
                        items_purchased = [line_item['name'] for line_item in order.get('line_items', [])]
                        with self.lock:
                            self.tips_by_location[location_name][order_date][time_range].append((tip_amount, items_purchased))
                            if tip_amount > 0:  # Only consider orders with tips
                                self.total_tips += tip_amount
                    cursor = order_data.get('cursor')
                    if not cursor:
                        break
                else:
                    if retries < max_retries:
                        retries += 1
                        time.sleep(self.exponential_backoff(retries))
                    else:
                        with open('error_log.txt', 'w') as f:
                            f.write(f'Error fetching order data for location {location_id}: {response.status_code} - {response.text}')
                        break
            self.update_progress.emit(int((queue.qsize() / len(self.selected_locations)) * 100), f"Fetching data for location {location_name}")
            queue.task_done()

        for location in self.selected_locations:
            queue.put(location)
            threading.Thread(target=fetch_location_data, args=(location,)).start()

        queue.join()
        self.finished.emit(self.all_orders, self.total_tips, self.tips_by_location)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Concorde Square Item Sales Report")
        self.resize(800, 600)

        self.sales_status_label = QLabel("Status: Ready")
        self.sales_progress_bar = QProgressBar()
        
        self.tips_status_label = QLabel("Status: Ready")
        self.tips_progress_bar = QProgressBar()

        self.tabs = QTabWidget()
        self.sales_tab = QWidget()
        self.tips_tab = QWidget()

        self.tabs.addTab(self.sales_tab, "Sales")
        self.tabs.addTab(self.tips_tab, "Tips")

        self.sales_layout = QVBoxLayout()
        self.tips_layout = QVBoxLayout()

        self.sales_tree = QTreeWidget()
        self.sales_tree.setColumnCount(3)
        self.sales_tree.setHeaderLabels(["Item Name", "Quantity Sold", "Total Price"])
        self.sales_tree.setSelectionMode(QTreeWidget.ExtendedSelection)  # Enable multiple selection
        self.sales_tree.itemSelectionChanged.connect(self.update_totals)

        self.tips_tree = QTreeWidget()
        self.tips_tree.setColumnCount(2)
        self.tips_tree.setHeaderLabels(["Location", "Tip Amount"])
        self.tips_tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.tips_tree.itemSelectionChanged.connect(self.update_tip_totals)

        self.total_quantity_label = QLabel("Total Quantity: 0")
        self.total_price_label = QLabel("Total Price: $0.00")
        self.total_tips_label = QLabel("Total Tips: $0.00")
        self.total_flags_label = QLabel("Total Flags: 0")  # Add this label to show the total number of flags

        # Button layouts
        self.sales_buttons = self.create_button_layout()
        self.tips_buttons = self.create_button_layout()

        # Select location button
        self.sales_location_button = QPushButton("Select Locations")
        self.sales_location_button.clicked.connect(self.create_location_selector)
        
        self.tips_location_button = QPushButton("Select Locations")
        self.tips_location_button.clicked.connect(self.create_location_selector)

        self.sales_layout.addWidget(self.sales_status_label)
        self.sales_layout.addWidget(self.sales_progress_bar)
        self.sales_layout.addLayout(self.sales_buttons)
        self.sales_layout.addWidget(self.sales_location_button)
        self.sales_layout.addWidget(self.sales_tree)

        totals_layout = QHBoxLayout()
        totals_layout.addWidget(self.total_quantity_label)
        totals_layout.addWidget(self.total_price_label)
        self.sales_layout.addLayout(totals_layout)

        self.sales_tab.setLayout(self.sales_layout)
        
        self.tips_layout.addWidget(self.tips_status_label)
        self.tips_layout.addWidget(self.tips_progress_bar)
        self.tips_layout.addLayout(self.tips_buttons)
        self.tips_layout.addWidget(self.tips_location_button)
        self.tips_layout.addWidget(self.tips_tree)
        self.tips_layout.addWidget(self.total_tips_label)
        self.tips_layout.addWidget(self.total_flags_label)  # Add this to the tips layout

        self.flags_button = QPushButton("Flags")
        self.flags_button.clicked.connect(self.open_flags_dialog)
        self.apply_flags_button = QPushButton("Apply Flags")
        self.apply_flags_button.clicked.connect(self.apply_flags)
        flags_layout = QHBoxLayout()
        flags_layout.addWidget(self.apply_flags_button)
        flags_layout.addStretch()
        flags_layout.addWidget(self.flags_button)
        self.tips_layout.addLayout(flags_layout)
        
        self.tips_tab.setLayout(self.tips_layout)

        container = QWidget()
        container_layout = QVBoxLayout()
        container_layout.addWidget(self.tabs)
        container.setLayout(container_layout)
        self.setCentralWidget(container)

        self.locations = self.fetch_location_ids()
        self.selected_locations = self.locations

        self.inventory_manager = InventoryManager('location_inventory_dict.json')

        # Ensure columns adjust as window expands
        self.sales_tree.header().setStretchLastSection(True)
        self.tips_tree.header().setStretchLastSection(True)

        self.flags_manager = FlagsManager()
        self.all_orders = {}

    def create_button_layout(self, include_buttons=['last_hour', 'last_12_hours', 'all_day', 'custom']):
        layout = QHBoxLayout()
        button_dict = {
            'last_hour': QPushButton("Last Hour"),
            'last_12_hours': QPushButton("Last 12 Hours"),
            'all_day': QPushButton("All Day (6AM - 6AM)"),
            'custom': QPushButton("Custom")
        }

        for btn_name, btn in button_dict.items():
            if btn_name in include_buttons:
                if btn_name == 'last_hour':
                    btn.clicked.connect(lambda: self.generate_report("last_hour"))
                elif btn_name == 'last_12_hours':
                    btn.clicked.connect(lambda: self.generate_report("last_12_hours"))
                elif btn_name == 'all_day':
                    btn.clicked.connect(lambda: self.generate_report("all_day"))
                elif btn_name == 'custom':
                    btn.clicked.connect(self.open_custom_date_dialog)
                layout.addWidget(btn)
        return layout

    def create_actions(self):
        self.release_info_action = QAction(QIcon('question.png'), '&Release Information', self)
        self.release_info_action.setStatusTip('Show release information')
        self.release_info_action.triggered.connect(self.show_release_info)

    def create_toolbar(self):
        toolbar = QToolBar()
        toolbar.setMovable(False)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)
        toolbar.addAction(self.release_info_action)
        self.addToolBar(Qt.TopToolBarArea, toolbar)

    def fetch_location_ids(self):
        try:
            print("Fetching location IDs...")
            endpoint = 'https://connect.squareup.com/v2/locations'
            headers = {
                'Square-Version': API_VERSION,
                'Authorization': f'Bearer {ACCESS_TOKEN}',
                'Content-Type': 'application/json'
            }
            response = requests.get(endpoint, headers=headers)
            if response.status_code == 200:
                locations_data = response.json()
                print("Fetched location IDs successfully.")
                return [(location['id'], location['name']) for location in locations_data['locations']]
            else:
                with open('error_log.txt', 'w') as f:
                    f.write(f'Error fetching location IDs: {response.status_code} - {response.text}')
                return []
        except Exception as e:
            print(f"Error fetching location IDs: {e}")
            return []

    def open_custom_date_dialog(self):
        dialog = CustomDateDialog(self)
        if dialog.exec():
            start_date, start_time, end_date, end_time = dialog.get_date_range()
            self.generate_custom_report(start_date, start_time, end_date, end_time)

    def open_flags_dialog(self):
        dialog = FlagsDialog(self.flags_manager, self)
        dialog.exec()

    def create_location_selector(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Locations")
        dialog.resize(400, 300)

        layout = QVBoxLayout()
        search_bar = QLineEdit()
        search_bar.setPlaceholderText("Search...")
        layout.addWidget(search_bar)

        self.location_list = QListWidget()
        layout.addWidget(self.location_list)

        for loc_id, loc_name in self.locations:
            item = QListWidgetItem(loc_name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.location_list.addItem(item)

        search_bar.textChanged.connect(self.update_location_listbox)

        self.select_deselect_button = QPushButton("Deselect All")
        self.select_deselect_button.clicked.connect(self.toggle_select_deselect)
        button_box_layout = QHBoxLayout()
        button_box_layout.addWidget(self.select_deselect_button)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addLayout(button_box_layout)
        layout.addWidget(button_box)

        dialog.setLayout(layout)
        if dialog.exec():
            self.selected_locations = [(self.locations[idx][0], self.locations[idx][1])
                                       for idx in range(self.location_list.count())
                                       if self.location_list.item(idx).checkState() == Qt.Checked]

    def toggle_select_deselect(self):
        if self.select_deselect_button.text() == "Select All":
            for idx in range(self.location_list.count()):
                self.location_list.item(idx).setCheckState(Qt.Checked)
            self.select_deselect_button.setText("Deselect All")
        else:
            for idx in range(self.location_list.count()):
                self.location_list.item(idx).setCheckState(Qt.Unchecked)
            self.select_deselect_button.setText("Select All")

    def update_location_listbox(self, search_text):
        for idx in range(self.location_list.count()):
            item = self.location_list.item(idx)
            item.setHidden(search_text.lower() not in item.text().lower())

    def generate_report(self, time_range):
        end_time = datetime.datetime.now(datetime.timezone.utc).astimezone()
        if time_range == "last_hour":
            start_time = end_time - datetime.timedelta(hours=1)
        elif time_range == "last_12_hours":
            start_time = end_time - datetime.timedelta(hours=12)
        elif time_range == "all_day":
            end_time = end_time.replace(hour=6, minute=0, second=0, microsecond=0)
            start_time = end_time - datetime.timedelta(days=1)
        self.fetch_and_display_orders(start_time, end_time)

    def generate_custom_report(self, start_date, start_time, end_date, end_time):
        start_time_str = start_date.toString("yyyy-MM-dd") + f' {start_time}'
        end_time_str = end_date.toString("yyyy-MM-dd") + f' {end_time}'
        start_time = datetime.datetime.strptime(start_time_str, '%Y-%m-%d %I %p').astimezone()
        end_time = datetime.datetime.strptime(end_time_str, '%Y-%m-%d %I %p').astimezone()
        self.fetch_and_display_orders(start_time, end_time)

    def fetch_and_display_orders(self, start_time, end_time):
        self.sales_status_label.setText("Status: Fetching data...")
        self.sales_progress_bar.setValue(0)
        self.tips_status_label.setText("Status: Fetching data...")
        self.tips_progress_bar.setValue(0)

        self.worker_thread = WorkerThread(start_time, end_time, self.selected_locations)
        self.worker_thread.update_progress.connect(self.update_progress)
        self.worker_thread.finished.connect(self.display_sales_by_location)
        self.worker_thread.start()

    @pyqtSlot(int, str)
    def update_progress(self, value, status):
        self.sales_progress_bar.setValue(value)
        self.tips_progress_bar.setValue(value)
        self.sales_status_label.setText(f"Status: {status}")
        self.tips_status_label.setText(f"Status: {status}")

    @pyqtSlot(dict, float, dict)
    def display_sales_by_location(self, all_orders, total_tips, tips_by_location):
        self.sales_tree.clear()
        self.tips_tree.clear()
        self.all_orders = all_orders  # Store orders for flagging
        no_info_item = QTreeWidgetItem(["No Information"])
        has_info = False

        # Display sales data
        for location, orders in all_orders.items():
            location_item = QTreeWidgetItem([location])
            item_sales = self.aggregate_item_sales(orders)
            total_price = sum(price for quantity, price in item_sales.values())
            location_item.setText(0, f"{location} (Total: ${total_price:.2f})")
            if item_sales:
                has_info = True
                self.sales_tree.addTopLevelItem(location_item)
                for item, (quantity, price) in item_sales.items():
                    item_details = self.inventory_manager.get_item_details(item)
                    details_text = f" (Inventory: {item_details})" if item_details else ""
                    QTreeWidgetItem(location_item, [item + details_text, f"{quantity}", f"${price:.2f}"])
            else:
                QTreeWidgetItem(no_info_item, [location])
        if not has_info:
            self.sales_tree.addTopLevelItem(no_info_item)
        self.total_tips_label.setText(f"Total Tips: ${total_tips:.2f}")
        self.sales_status_label.setText("Status: Ready")
        self.tips_status_label.setText("Status: Ready")

        # Display tips data
        self.total_tips_label.setText(f"Total Tips: ${total_tips:.2f}")
        self.tips_status_label.setText("Status: Ready")
        for location, dates in tips_by_location.items():
            location_item = QTreeWidgetItem([location])
            self.tips_tree.addTopLevelItem(location_item)
            for date, time_ranges in dates.items():
                for time_range, tips in time_ranges.items():
                    for tip_amount, items in tips:
                        if tip_amount > 0:
                            tip_item = QTreeWidgetItem([f"{time_range}", f"${tip_amount:.2f}"])
                            location_item.addChild(tip_item)
        self.apply_flags()
        self.update_totals()

    def aggregate_item_sales(self, orders):
        item_sales = defaultdict(lambda: [0, 0.0])  # quantity, total price
        for order in orders:
            for item in order.get('line_items', []):
                item_name = item['name']
                quantity = float(item['quantity'])
                price = float(item['base_price_money']['amount']) / 100 * quantity
                item_sales[item_name][0] += quantity
                item_sales[item_name][1] += price
        return item_sales

    def apply_flags(self):
        print("Applying flags...")
        flags = self.flags_manager.get_flags()
        alert_counts = defaultdict(lambda: defaultdict(int))  # To keep track of alert counts per location and flag
        total_flags = 0  # To count the total number of flags

        for flag in flags:
            print(f"Checking flag: {flag.name} with condition {flag.condition} and value {flag.value}")
            for i in range(self.tips_tree.topLevelItemCount()):
                location_item = self.tips_tree.topLevelItem(i)
                location_name = location_item.text(0)  # Use location name as the key
                for j in range(location_item.childCount()):
                    tip_item = location_item.child(j)
                    tip_amount_text = tip_item.text(1).replace('$', '')
                    try:
                        tip_amount = float(tip_amount_text)
                    except ValueError:
                        continue

                    highlight = False
                    if flag.value is not None:
                        print(f"Checking amount: {tip_amount} against range: {flag.value}")
                        if self.check_condition(tip_amount, flag.value, flag):
                            highlight = True

                    if highlight:
                        print(f"Highlighting tip item with amount: {tip_amount}, color: {flag.color}, icon: {flag.icon}")
                        for k in range(tip_item.columnCount()):
                            tip_item.setBackground(k, QBrush(flag.color))
                        alert_counts[location_name][flag] += 1  # Increment the alert count for the location and flag
                        total_flags += 1  # Increment the total flag count

        # Update the location items with the alert counts
        for location_item in self.tips_tree.findItems("", Qt.MatchContains | Qt.MatchRecursive):
            location_name = location_item.text(0)
            if location_name in alert_counts:
                self.update_location_item_text(location_item, alert_counts[location_name])

        self.total_flags_label.setText(f"Total Flags: {total_flags}")  # Update the label with the total number of flags

    def update_location_item_text(self, location_item, flags_count):
        original_text = location_item.text(0)
        new_text_parts = [original_text]
        for flag, count in flags_count.items():
            flag_text = f'<span style="color: {flag.color.name()};">{flag.name}: {count}</span>'
            new_text_parts.append(flag_text)
        new_text = f"{original_text} ({', '.join(new_text_parts[1:])})"

        # Set HTML-styled text with individual colors for flags
        document = QTextDocument()
        document.setHtml(new_text)
        location_item.setData(0, Qt.DisplayRole, document.toPlainText())

        # Set the tooltip to display the HTML text properly
        location_item.setToolTip(0, new_text)

    def check_condition(self, value, threshold, flag):
        condition = flag.condition.lower()
        if condition == "greater than":
            return value > threshold
        elif condition == "less than":
            return value < threshold
        elif condition == "equal to":
            return value == threshold
        return False

    def get_transaction_total(self, tip_item):
        parent = tip_item.parent()
        location_name = parent.text(0)
        time_range = tip_item.text(0)

        for order in self.all_orders[location_name]:
            try:
                order_time = datetime.datetime.strptime(order['created_at'], "%Y-%m-%dT%H:%M:%S.%f%z").astimezone()
            except ValueError:
                try:
                    order_time = datetime.datetime.strptime(order['created_at'], "%Y-%m-%dT%H:%M:%S%z").astimezone()
                except ValueError:
                    order_time = datetime.datetime.strptime(order['created_at'], "%Y-%m-%dT%H:%M:%SZ").astimezone()
            order_time_formatted = order_time.strftime('%I %p').lower()
            if order_time_formatted == time_range.split(' - ')[0]:
                return float(order['total_money']['amount']) / 100
        return None

    @pyqtSlot()
    def update_totals(self):
        total_quantity = 0
        total_price = 0.0
        selected_items = self.sales_tree.selectedItems()
        if not selected_items:
            selected_items = self.sales_tree.findItems('', Qt.MatchContains | Qt.MatchRecursive)
        for item in selected_items:
            try:
                quantity = float(item.text(1))
                price = float(item.text(2).replace('$', ''))
                total_quantity += quantity
                total_price += price
            except ValueError:
                continue
        self.total_quantity_label.setText(f"Total Quantity: {total_quantity}")
        self.total_price_label.setText(f"Total Price: ${total_price:.2f}")

    @pyqtSlot()
    def update_tip_totals(self):
        total_tips = 0.0
        selected_items = self.tips_tree.selectedItems()
        for item in selected_items:
            try:
                tip_amount = float(item.text(1).replace('$', ''))
                total_tips += tip_amount
            except ValueError:
                continue
        self.total_tips_label.setText(f"Selected Tips: ${total_tips:.2f}")

    def show_release_info(self):
        QMessageBox.information(self, "Release Information", "Concorde Square Item Sales Report\nVersion 1.0")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
