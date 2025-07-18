import sys
import os
import json
import openai
import dashscope
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QMessageBox, QTabWidget,
    QFormLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QSizePolicy,QScrollArea
)
from PyQt5.QtGui import QFont
from openai import OpenAI

# 解包资源路径
def resource_path(relative_path):
    """
    获取资源文件路径，兼容开发环境与 PyInstaller 打包后。
    - relative_path: 相对路径，如 'assets/app_icon.ico'
    """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包后的临时目录
        return os.path.join(sys._MEIPASS, relative_path)
    # 开发环境下的绝对路径
    return os.path.join(os.path.abspath("."), relative_path)


#引入通义千问qwen-plus
def generate_dynamic_goods_description(rmb_amount):
    if not QWEN_API_KEY:
        return "💡 未配置通义千问API Key，无法生成购买力描述。"

    prompt = (
        f"我有 {rmb_amount:.2f} 元人民币，"
        "请基于2025年中国大陆的物价水平，列举对应上面人民币等值的商品及数量、旅游手段等。"
        "输出格式为三行，每行一句话。第一行为我能用这些人民币能买到的最贵的一个物品，第二行从现代角度，第三行从古代角度。"
        "不需要有后缀形容，只用讲能买什么即可，保持尽量精简，数量需要具体，价格换算需要合理严谨。"
    )

    try:
        dashscope.api_key = QWEN_API_KEY
        response = dashscope.Generation.call(
            model='qwen-plus',
            prompt=prompt,
            max_tokens = 200,
            result_format='message'
        )

        if response.status_code == 200:
            content = response['output']['choices'][0]['message']['content']
            return "💡 通义千问生成购买力参考：\n" + content
        else:
            print("通义千问API调用失败:", response)
            return "💡 生成购买力描述失败，通义千问API错误。"
    except Exception as e:
        print("调用通义千问失败:", e)
        return "💡 通义千问调用失败，请检查API Key或网络。"


# 引入api key文件

CONFIG_FILE = "./config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

config = load_config()
QWEN_API_KEY = config.get("qwen_api_key")




# 初始化，自动载入最新汇率
import requests

def fetch_latest_rates():
    url = "https://open.er-api.com/v6/latest/CNY"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if data['result'] == 'success':
            rates = data['rates']
            return {
                "美国": {"美元": {"rate_to_rmb": 1 / rates.get("USD", 0)}},
                "日本": {"日元": {"rate_to_rmb": 1 / rates.get("JPY", 0)}},
                "英国": {"英镑": {"rate_to_rmb": 1 / rates.get("GBP", 0)}},
                "中国台湾": {"新台币": {"rate_to_rmb": 1 / rates.get("TWD", 0)}},
                "中国香港": {"港币": {"rate_to_rmb": 1 / rates.get("HKD", 0)}}
            }
        else:
            return None
    except Exception as e:
        print(f"获取汇率失败: {e}")
        return None


RATE_FILE = "./exchange_rates.json"

def load_exchange_data():
    if os.path.exists(RATE_FILE):
        try:
            with open(RATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_exchange_data(data):
    with open(RATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class CurrencyRow(QWidget):
    def __init__(self, exchange_data, parent=None):
        super().__init__(parent)
        self.exchange_data = exchange_data
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout()

        self.country_box = QComboBox()
        self.country_box.addItems(self.exchange_data.keys())
        self.country_box.currentTextChanged.connect(self.update_currency_box)
        self.country_box.setMinimumWidth(150)

        self.currency_box = QComboBox()
        self.currency_box.setMinimumWidth(150)

        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("数量")
        self.amount_input.setFixedWidth(100)

        self.remove_button = QPushButton("删除")
        self.remove_button.setFixedWidth(60)

        layout.addWidget(self.country_box)
        layout.addWidget(self.currency_box)
        layout.addWidget(self.amount_input)
        layout.addWidget(self.remove_button)
        self.setLayout(layout)

        self.update_currency_box()

    def update_currency_box(self):
        country = self.country_box.currentText()
        self.currency_box.clear()
        if country in self.exchange_data:
            self.currency_box.addItems(self.exchange_data[country].keys())

    def get_data(self):
        try:
            country = self.country_box.currentText()
            currency = self.currency_box.currentText()
            amount = float(self.amount_input.text())

            info = self.exchange_data[country][currency]
            if isinstance(info, dict):
                rate_to_rmb = info['rate_to_rmb']
            else:
                rate_to_rmb = info

            rmb = amount * rate_to_rmb
            return f"{amount} {currency} = {rmb:.2f} 人民币", rmb
        except:
            return None, 0.0

class CurrencyConverter(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("全自定义货币换算器V1.0")
        self.setFixedSize(850, 750)
        self.setWindowIcon(QIcon('./money.ico'))
        self.exchange_data = load_exchange_data() or {}

        latest_rates = fetch_latest_rates()
        if latest_rates:
            # 只更新指定国家的汇率
            for country, currencies in latest_rates.items():
                if country not in self.exchange_data:
                    self.exchange_data[country] = {}
                self.exchange_data[country].update(currencies)

            print("已更新最新汇率。")
        else:
            print("无法获取最新汇率，保留本地数据。")

        save_exchange_data(self.exchange_data)

        self.currency_rows = []

        self.init_ui()

    def init_ui(self):
        font = QFont("微软雅黑", 12)
        self.setFont(font)

        main_layout = QVBoxLayout()
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.tab_convert = QWidget()
        self.tab_add = QWidget()
        self.tab_manage = QWidget()
        self.tab_config = QWidget()

        self.tabs.addTab(self.tab_convert, "货币换算")
        self.tabs.addTab(self.tab_add, "添加/更新汇率")
        self.tabs.addTab(self.tab_manage, "国家/币种管理")
        self.tabs.addTab(self.tab_config, "配置")

        self.init_tab_convert()
        self.init_tab_add()
        self.init_tab_manage()
        self.init_tab_config()

        self.setLayout(main_layout)

    # ===== 货币换算 TAB =====
    def init_tab_convert(self):
        layout = QVBoxLayout()

        btn_add_row = QPushButton("添加币种行")
        btn_add_row.clicked.connect(self.add_currency_row)

        # 滚动区域设置
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFixedHeight(350)  # 固定高度1000

        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout()
        self.scroll_widget.setLayout(self.scroll_layout)

        self.scroll_area.setWidget(self.scroll_widget)

        self.btn_calculate = QPushButton("🧮 开始换算 🧮")
        self.btn_calculate.clicked.connect(self.calculate_total)

        self.result_label = QLabel("💰 总人民币：0.00 元")
        self.result_label.setStyleSheet("font-size: 40px; color: green;")
        self.result_label.setAlignment(Qt.AlignHCenter)

        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)

        layout.addWidget(btn_add_row)
        layout.addWidget(self.scroll_area)
        layout.addWidget(self.btn_calculate)
        layout.addWidget(self.result_label)
        layout.addWidget(self.detail_label)

        self.tab_convert.setLayout(layout)

    def add_currency_row(self):
        row = CurrencyRow(self.exchange_data)
        row.remove_button.clicked.connect(lambda: self.remove_currency_row(row))
        self.currency_rows.append(row)
        self.scroll_layout.addWidget(row)

    def remove_currency_row(self, row):
        self.currency_rows.remove(row)
        row.setParent(None)
        row.deleteLater()

    def calculate_total(self):
        total = 0.0
        details = []
        for row in self.currency_rows:
            detail, rmb = row.get_data()
            if detail:
                details.append(detail)
                total += rmb
        self.result_label.setText(f"💰 总人民币：{total:.2f} 元")

        dynamic_desc = generate_dynamic_goods_description(total)
        full_text = "\n".join(details) + f"\n\n{dynamic_desc}"
        self.detail_label.setText(full_text)
        self.detail_label.setAlignment(Qt.AlignHCenter)

        # ====== 新增动态调整窗口高度的逻辑 ======
        text_lines = full_text.count('\n') + 1
        additional_height = text_lines * 25  # 每行约25像素，按需调整
        base_height = 750
        new_height = base_height + additional_height
        max_height = 1200  # 可设置一个最大窗口高度限制
        self.setFixedHeight(min(new_height, max_height))

    # ===== 添加/更新汇率 TAB =====
    def init_tab_add(self):
        layout = QFormLayout()

        self.new_country = QLineEdit()
        self.new_country.editingFinished.connect(self.refresh_parent_currency_options)
        self.new_currency = QLineEdit()

        self.parent_currency_box = QComboBox()
        self.refresh_parent_currency_options()

        self.rate_to_parent = QLineEdit()
        self.rate_to_parent.setPlaceholderText("与基础单位的换算数量")

        self.rmb_preview = QLabel("≈ 人民币：? 元")

        btn_calculate_rmb = QPushButton("预览人民币汇率")
        btn_calculate_rmb.clicked.connect(self.preview_rmb_rate)

        btn_add = QPushButton("添加 / 更新汇率")
        btn_add.clicked.connect(self.add_or_update_rate)

        layout.addRow("国家名称：", self.new_country)
        layout.addRow("币种名称：", self.new_currency)
        layout.addRow("基础单位币种：", self.parent_currency_box)
        layout.addRow("与基础单位的换算数量：", self.rate_to_parent)
        layout.addRow(self.rmb_preview)
        layout.addRow(btn_calculate_rmb)
        layout.addRow(btn_add)

        self.tab_add.setLayout(layout)

    def refresh_parent_currency_options(self):
        country = self.new_country.text().strip()
        self.parent_currency_box.clear()

        if country in self.exchange_data:
            self.parent_currency_box.addItem("人民币")
            for currency in self.exchange_data[country]:
                self.parent_currency_box.addItem(currency)
        else:
            self.parent_currency_box.addItem("人民币")

    def calculate_rate_to_rmb(self, parent_currency, rate_to_parent):
        if parent_currency == "人民币":
            return float(rate_to_parent)
        for country, currencies in self.exchange_data.items():
            if parent_currency in currencies:
                parent_info = currencies[parent_currency]
                parent_rate = parent_info['rate_to_rmb'] if isinstance(parent_info, dict) else parent_info
                return float(rate_to_parent) * parent_rate
        raise ValueError(f"父币种 {parent_currency} 不存在人民币汇率")

    def preview_rmb_rate(self):
        try:
            parent_currency = self.parent_currency_box.currentText()
            rate_to_parent = float(self.rate_to_parent.text())
            rate_to_rmb = self.calculate_rate_to_rmb(parent_currency, rate_to_parent)
            self.rmb_preview.setText(f"≈ 人民币：{rate_to_rmb:.4f} 元")
        except Exception as e:
            QMessageBox.warning(self, "错误", str(e))

    def add_or_update_rate(self):
        country = self.new_country.text().strip()
        currency = self.new_currency.text().strip()
        parent_currency = self.parent_currency_box.currentText()
        try:
            rate_to_parent = float(self.rate_to_parent.text())
            rate_to_rmb = self.calculate_rate_to_rmb(parent_currency, rate_to_parent)

            if not country or not currency:
                QMessageBox.warning(self, "错误", "国家或币种不能为空。")
                return

            if country not in self.exchange_data:
                self.exchange_data[country] = {}

            currency_info = {"rate_to_rmb": rate_to_rmb}
            if parent_currency != "人民币":
                currency_info["parent_currency"] = parent_currency
                currency_info["rate_to_parent"] = rate_to_parent

            self.exchange_data[country][currency] = currency_info
            save_exchange_data(self.exchange_data)

            QMessageBox.information(self, "成功", f"{currency} 已添加/更新，汇率：{rate_to_rmb:.4f} 人民币")

            self.new_country.clear()
            self.new_currency.clear()
            self.rate_to_parent.clear()
            self.rmb_preview.setText("≈ 人民币：? 元")
            self.refresh_parent_currency_options()
            self.load_manage_table()

        except Exception as e:
            QMessageBox.warning(self, "错误", str(e))

    # ===== 管理 TAB =====
    def init_tab_manage(self):
        layout = QVBoxLayout()

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["国家", "币种", "人民币汇率", "换算路径", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # 默认可拖动
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)  # 默认可拖动

        # 自适应宽度
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 国家
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 币种
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 币种
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)  # 币种
        # 设置列宽
        #self.table.setColumnWidth(0, 80)  # 国家
        #self.table.setColumnWidth(1, 80)  # 币种
        #self.table.setColumnWidth(2, 120)  # 人民币汇率
        self.table.setColumnWidth(3, 470)  # 换算路径，固定宽度
        #self.table.setColumnWidth(4, 60)  # 操作


        layout.addWidget(self.table)
        self.tab_manage.setLayout(layout)
        self.load_manage_table()

    def load_manage_table(self):
        rows = sum(len(currencies) for currencies in self.exchange_data.values())
        self.table.setRowCount(rows)

        row_idx = 0
        for country, currencies in self.exchange_data.items():
            for currency, info in currencies.items():
                rate_to_rmb = info['rate_to_rmb'] if isinstance(info, dict) else info

                # 国家
                country_item = QTableWidgetItem(country)
                country_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_idx, 0, country_item)

                # 币种
                currency_item = QTableWidgetItem(currency)
                currency_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_idx, 1, currency_item)

                # 人民币汇率
                rate_item = QTableWidgetItem(f"{rate_to_rmb:.4f}")
                rate_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_idx, 2, rate_item)

                # 换算路径
                _, formula = self.build_conversion_chain(currency)
                formula_item = QTableWidgetItem(formula)
                formula_item.setToolTip(formula)
                formula_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_idx, 3, formula_item)

                # 删除按钮
                btn_del = QPushButton("删除")
                btn_del.setFixedWidth(60)
                btn_del.clicked.connect(lambda _, c=country, cur=currency: self.delete_currency(c, cur))
                self.table.setCellWidget(row_idx, 4, btn_del)

                self.table.setRowHeight(row_idx, 40)

                row_idx += 1

        #self.table.resizeRowsToContents()

    def build_conversion_chain(self, currency):
        for country, currencies in self.exchange_data.items():
            if currency in currencies:
                chain = []
                current_currency = currency
                formula = f"1 {currency}"
                rate = 1.0
                while True:
                    info = currencies.get(current_currency)
                    if not info:
                        break
                    if isinstance(info, dict) and 'parent_currency' in info:
                        rate *= info['rate_to_parent']
                        formula += f" = {info['rate_to_parent']} {info['parent_currency']}"
                        current_currency = info['parent_currency']
                    else:
                        final_rate = info['rate_to_rmb'] if isinstance(info, dict) else info
                        rate *= final_rate
                        formula += f" = {rate:.4f} 人民币"
                        break
                return chain, formula
        return [], "路径不明"

    def delete_currency(self, country, currency):
        for ctry, currencies in self.exchange_data.items():
            for cur, info in currencies.items():
                if isinstance(info, dict) and info.get('parent_currency') == currency:
                    QMessageBox.warning(self, "错误", f"{currency} 被其他币种（{cur}）引用，无法删除。")
                    return

        del self.exchange_data[country][currency]
        if not self.exchange_data[country]:
            del self.exchange_data[country]
        save_exchange_data(self.exchange_data)
        self.refresh_parent_currency_options()
        self.load_manage_table()
        QMessageBox.information(self, "成功", f"{currency} 已删除。")

    # ===== 设置 TAB =====
    def init_tab_config(self):
        layout = QFormLayout()

        self.qwen_api_key_input = QLineEdit()
        self.qwen_api_key_input.setText(config.get("qwen_api_key", ""))

        self.qwen_model_input = QLineEdit()
        self.qwen_model_input.setText(config.get("qwen_model", "qwen-plus"))

        btn_save_config = QPushButton("保存配置")
        btn_save_config.clicked.connect(self.save_config)

        layout.addRow("通义 API Key：", self.qwen_api_key_input)
        layout.addRow("通义模型名称：", self.qwen_model_input)
        layout.addRow(btn_save_config)

        self.tab_config.setLayout(layout)

    def save_config(self):
        api_key = self.qwen_api_key_input.text().strip()
        model = self.qwen_model_input.text().strip()

        config["qwen_api_key"] = api_key
        config["qwen_model"] = model

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        global QWEN_API_KEY
        QWEN_API_KEY = api_key  # 更新全局变量
        QMessageBox.information(self, "成功", "配置已保存！")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CurrencyConverter()
    window.show()
    sys.exit(app.exec_())
