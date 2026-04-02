# -*- coding: utf-8 -*-
"""
能量反应路径图绘制软件 - GUI版本 (v1.0)
基于 plot_combined.py 核心功能

作者: 刘璋
单位: 华中科技大学 | 微纳材料设计与制造研究中心
版本: 1.0
日期: 2023-12-01

功能更新：
- 内置数据模板，支持直接使用示例数据绘图
- 图形界面内展示图片，支持放大查看
- 手动输出按钮控制图片保存
"""

import sys
import os
import csv
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import List, Tuple, Union, Optional
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

# 将父目录加入路径以导入核心模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ==================== 内置数据模板 ====================
# data-template.csv 的内容作为内置模板
BUILT_IN_TEMPLATE = """index,Model A,Model B,Model C
color,"0.5, 0.6, 0.7","0.8, 0.4, 0.3","0.5, 0.6, 0.3"
gas,0,0,0
ads.,-0.5,-1,-1.5
TS1,0.2,-0.1,-0.4
state,-0.4,-0.8,-1.2
TS2,0.1,-0.1,-0.3
prod.,-0.6,-1.1,-1.6"""

BUILT_IN_TEMPLATE_FILENAME = "data-template.csv"


# ==================== 提示框工具类 ====================
class Tooltip:
    """鼠标悬停提示框"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.show)
        self.widget.bind("<Leave>", self.hide)
    
    def show(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(
            self.tooltip,
            text=self.text,
            background="#ffffcc",
            relief="solid",
            borderwidth=1,
            font=("微软雅黑", 9),
            wraplength=300,
            justify="left",
            padx=5,
            pady=3
        )
        label.pack()
    
    def hide(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None


# ==================== 配置类 ====================
class PlotConfig:
    """绘图配置类（可变版本，用于GUI）"""
    def __init__(self):
        # 图像基础配置
        self.figure_size = (20, 15)
        self.dpi = 300
        
        # 字体配置
        self.font_size_title = 40
        self.font_size_axis_title = 36
        self.font_size_axis_tick = 30
        self.font_size_energy_label = 30
        self.font_size_legend = 24
        
        # 图片主标题配置
        self.show_title = True
        self.title_text = "Relative Energy Profile"
        self.title_fontweight = 'bold'
        self.title_pad = 20
        
        # 坐标轴标题配置
        self.show_x_title = True
        self.x_title_text = "Reaction Coordinate"
        self.x_title_fontweight = 'bold'
        self.show_y_title = True
        self.y_title_text = "Relative Energy (eV)"
        self.y_title_fontweight = 'bold'
        
        # 能量值标签配置
        self.show_energy_labels = True              # curve图 是否显示能量标签
        self.show_energy_labels_state = True        # state图 是否显示能量标签（v2新增）
        
        # 能量数值标签位置配置
        # curve 图
        self.label_offset_x_curve = -0.2            # X轴偏移量
        self.label_offset_y_curve = 0.06            # Y轴偏移量
        self.label_ha_curve = 'left'                # 水平对齐方式
        
        # state 图
        self.label_offset_x_state = 0.5             # X轴偏移量
        self.label_offset_y_state = 0.1             # Y轴偏移量
        self.label_ha_state = 'right'               # 水平对齐方式
        
        # 图例配置
        self.show_legend = True                     # curve图 是否显示图例
        self.show_legend_state = True               # state图 是否显示图例（v2新增）
        self.legend_loc = 'upper right'             # 图例位置（curve图）
        self.legend_loc_state = 'upper right'       # 图例位置（state图，v2新增，可独立设置）
        self.legend_frameon = True
        self.legend_bbox_to_anchor = None  # 默认不使用，如需精细调整可设置为 (x, y)
        
        # state图 专用配置（v2新增）
        self.connect_steps = True                   # 是否用虚线连接台阶
        self.line_style_connector = '--'            # 连接线型（'--'虚线, ':'点线, '-.'点划线）
        self.line_width_connector = 3.0             # 连接线宽
        
        # 线宽配置
        self.line_width_curve = 4
        self.line_width_segment = 8
        self.line_width_frame = 3
        
        # 坐标轴范围配置（将根据数据自动计算）
        self.y_axis_limits = (-2.0, 1.0)  # 默认Y轴范围（自动计算关闭时使用）
        self.auto_y_range = True  # 是否自动计算Y轴范围（默认开启）
        
        # 插值配置
        self.interpolation_points = 50
        
        # 输出配置
        self.output_curve = "curve.png"
        self.output_state = "state.png"


# ==================== 数据类 ====================
class ReactionData:
    """反应数据容器类"""
    def __init__(self, path_labels, x_labels, colors, x_coords, y_values, row_minimums):
        self.path_labels = path_labels
        self.x_labels = x_labels
        self.colors = colors
        self.x_coords = x_coords
        self.y_values = y_values
        self.row_minimums = row_minimums
    
    def validate(self):
        if not self.y_values:
            raise ValueError("能量数据为空")
        if not self.x_labels:
            raise ValueError("状态标签为空")


# ==================== 核心绘图函数 ====================
def generate_cosine_points(y_small, y_large, direction, num_points=50):
    """生成余弦曲线插值点"""
    if direction not in ("up", "down"):
        raise ValueError(f"无效的方向参数: {direction}")
    
    if direction == "up":
        x_vals = np.linspace(np.pi, 2 * np.pi, num_points)
    else:
        x_vals = np.linspace(0, np.pi, num_points)
    
    cos_vals = np.cos(x_vals)
    y_curve = [y_small + (y_large - y_small) * (j + 1) / 2 for j in cos_vals.tolist()]
    return y_curve


def parse_color(color_string):
    """解析颜色字符串"""
    try:
        parts = color_string.split(',')
        if len(parts) != 3:
            raise ValueError(f"颜色格式应为 'R,G,B'，得到: {color_string}")
        return [float(p.strip()) for p in parts]
    except Exception as e:
        raise ValueError(f"无法解析颜色 '{color_string}': {e}")


def get_row_minimums(y_data):
    """获取每行的最小值"""
    y_transposed = np.array(y_data).T.tolist()
    row_mins = []
    for row in y_transposed:
        valid_values = [float(val) for val in row if val != ""]
        if valid_values:
            row_mins.append(min(valid_values))
    return row_mins


def load_csv_data_from_file(filename):
    """从CSV文件加载数据"""
    with open(filename, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        rows = list(reader)
    return _parse_csv_rows(rows)


def load_csv_data_from_string(csv_string):
    """从CSV字符串加载数据（用于内置模板）"""
    lines = csv_string.strip().split('\n')
    reader = csv.reader(lines)
    rows = list(reader)
    return _parse_csv_rows(rows)


def _parse_csv_rows(rows):
    """解析CSV行数据"""
    if len(rows) < 3:
        raise ValueError(f"CSV文件行数不足(需要至少3行，实际{len(rows)}行)")
    
    path_labels = rows[0][1:]
    color_strings = rows[1][1:]
    
    x_labels = []
    y_values_rows = []
    for row in rows[2:]:
        if row and row[0]:
            x_labels.append(row[0])
            y_values_rows.append(row[1:])
    
    colors = [parse_color(cs) for cs in color_strings]
    x_coords = list(range(1, len(x_labels) + 1))
    
    num_paths = len(path_labels)
    y_values = []
    
    for i in range(num_paths):
        col_idx = i
        path_data = []
        for row in y_values_rows:
            if col_idx < len(row):
                val = row[col_idx].strip()
                if val == '':
                    path_data.append('')
                else:
                    try:
                        path_data.append(float(val))
                    except ValueError:
                        path_data.append('')
            else:
                path_data.append('')
        y_values.append(path_data)
    
    row_minimums = get_row_minimums(y_values)
    
    data = ReactionData(
        path_labels=path_labels,
        x_labels=x_labels,
        colors=colors,
        x_coords=x_coords,
        y_values=y_values,
        row_minimums=row_minimums
    )
    data.validate()
    return data, y_values


def get_y_range(y_values):
    """根据数据计算Y轴范围"""
    flat_list = [float(val) for sublist in y_values for val in sublist if val != ""]
    if not flat_list:
        return (-1.25, 1.25)
    
    y_min = min(flat_list)
    y_max = max(flat_list)
    
    # 添加一些边距
    margin = (y_max - y_min) * 0.15 if y_max != y_min else 0.5
    return (y_min - margin, y_max + margin)


# ==================== 图片查看窗口 ====================
class ImageViewerWindow:
    """独立窗口用于放大查看图片"""
    def __init__(self, parent, fig_curve, fig_state):
        self.window = tk.Toplevel(parent)
        self.window.title("图片查看器 - 点击标签切换")
        self.window.geometry("1200x900")
        self.window.minsize(800, 600)
        
        # 创建Notebook标签页
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # curve图页面
        curve_frame = ttk.Frame(notebook)
        notebook.add(curve_frame, text="curve图")
        
        canvas_curve = FigureCanvasTkAgg(fig_curve, master=curve_frame)
        canvas_curve.draw()
        canvas_curve.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        toolbar_curve = NavigationToolbar2Tk(canvas_curve, curve_frame)
        toolbar_curve.update()
        
        # state图页面
        state_frame = ttk.Frame(notebook)
        notebook.add(state_frame, text="state图")
        
        canvas_state = FigureCanvasTkAgg(fig_state, master=state_frame)
        canvas_state.draw()
        canvas_state.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        toolbar_state = NavigationToolbar2Tk(canvas_state, state_frame)
        toolbar_state.update()
        
        # 关闭按钮
        ttk.Button(self.window, text="关闭", command=self.window.destroy).pack(pady=5)


# ==================== GUI主类 ====================
class PlotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("能量反应路径图绘制软件 v1.0")
        self.root.geometry("1200x900")
        self.root.minsize(1000, 800)
        
        # 数据文件路径
        self.data_file = tk.StringVar()
        self.output_dir = tk.StringVar()
        
        # 当前数据和图表
        self.current_data = None
        self.current_y_values = None
        self.current_config = None
        self.fig_curve = None
        self.fig_state = None
        self.canvas_curve = None
        self.canvas_state = None
        
        # 创建配置对象
        self.config = PlotConfig()
        
        # 创建界面
        self.create_widgets()
        
        # 存储所有tooltip
        self.tooltips = []
        
        # 状态栏提示
        self.status_var.set("就绪 - 可选择导入数据文件，或直接使用内置模板绘图")
    
    def create_widgets(self):
        """创建界面组件"""
        # 主框架 - 使用PanedWindow分割左右
        self.main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左侧：控制面板
        left_frame = ttk.Frame(self.main_paned, padding="5")
        self.main_paned.add(left_frame, weight=1)
        
        # 右侧：图片显示区域
        right_frame = ttk.Frame(self.main_paned, padding="5")
        self.main_paned.add(right_frame, weight=3)
        
        # ===== 左侧控制面板 =====
        left_frame.columnconfigure(0, weight=1)
        
        row = 0
        
        # ========== 文件选择区域 ==========
        file_frame = ttk.LabelFrame(left_frame, text="文件选择", padding="5")
        file_frame.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=3)
        file_frame.columnconfigure(0, weight=1)
        
        # 数据文件选择
        file_row = 0
        ttk.Label(file_frame, text="数据文件:").grid(row=file_row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(file_frame, textvariable=self.data_file).grid(row=file_row+1, column=0, sticky=(tk.W, tk.E), pady=2)
        btn_frame = ttk.Frame(file_frame)
        btn_frame.grid(row=file_row+1, column=1, padx=5)
        ttk.Button(btn_frame, text="浏览...", command=self.browse_data_file, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="清除", command=self.clear_data_file, width=6).pack(side=tk.LEFT, padx=2)
        
        # 模板操作按钮
        file_row += 2
        template_btn_frame = ttk.Frame(file_frame)
        template_btn_frame.grid(row=file_row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        ttk.Button(template_btn_frame, text="📥 导出内置模板", command=self.export_template, width=16).pack(side=tk.LEFT, padx=2)
        tooltip_text = "将内置示例数据模板导出到指定位置，可作为数据格式参考"
        self.add_tooltip(template_btn_frame.winfo_children()[-1], tooltip_text)
        
        ttk.Label(template_btn_frame, text="(未选择文件时将使用内置模板)", foreground="gray", font=("微软雅黑", 8)).pack(side=tk.LEFT, padx=5)
        
        row += 1
        
        # ========== 创建Notebook（标签页）==========
        notebook = ttk.Notebook(left_frame)
        notebook.grid(row=row, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # 标题配置页
        title_frame = self.create_title_frame(notebook)
        notebook.add(title_frame, text="标题")
        
        # 字体配置页
        font_frame = self.create_font_frame(notebook)
        notebook.add(font_frame, text="字体")
        
        # 显示配置页
        display_frame = self.create_display_frame(notebook)
        notebook.add(display_frame, text="显示")
        
        # 图例配置页
        legend_frame = self.create_legend_frame(notebook)
        notebook.add(legend_frame, text="图例")
        
        # 高级配置页
        advanced_frame = self.create_advanced_frame(notebook)
        notebook.add(advanced_frame, text="高级")
        
        row += 1
        
        # ========== 输出配置区域 ==========
        output_frame = ttk.LabelFrame(left_frame, text="输出配置", padding="5")
        output_frame.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=3)
        output_frame.columnconfigure(0, weight=1)
        
        out_row = 0
        ttk.Label(output_frame, text="输出目录:").grid(row=out_row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(output_frame, textvariable=self.output_dir).grid(row=out_row+1, column=0, sticky=(tk.W, tk.E), pady=2)
        ttk.Button(output_frame, text="浏览...", command=self.browse_output_dir, width=8).grid(row=out_row+1, column=1, padx=5)
        
        out_row += 2
        ttk.Label(output_frame, text="curve文件名:").grid(row=out_row, column=0, sticky=tk.W, pady=2)
        self.curve_name = tk.StringVar(value="curve图")
        ttk.Entry(output_frame, textvariable=self.curve_name, width=25).grid(row=out_row+1, column=0, sticky=tk.W, pady=2)
        
        out_row += 2
        ttk.Label(output_frame, text="state文件名:").grid(row=out_row, column=0, sticky=tk.W, pady=2)
        self.state_name = tk.StringVar(value="state图")
        ttk.Entry(output_frame, textvariable=self.state_name, width=25).grid(row=out_row+1, column=0, sticky=tk.W, pady=2)
        
        row += 1
        
        # ========== 按钮区域 ==========
        btn_frame = ttk.Frame(left_frame)
        btn_frame.grid(row=row, column=0, pady=10)
        
        ttk.Button(btn_frame, text="🎨 开始绘图", command=self.plot, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="💾 输出图片", command=self.save_images, width=15).pack(side=tk.LEFT, padx=5)
        
        # 恢复默认和关于按钮
        btn_frame2 = ttk.Frame(left_frame)
        btn_frame2.grid(row=row+1, column=0, pady=5)
        
        ttk.Button(btn_frame2, text="恢复默认", command=self.reset_defaults, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame2, text="关于", command=self.show_about, width=10).pack(side=tk.LEFT, padx=5)
        
        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(left_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=row+2, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # 作者信息
        author_label = ttk.Label(
            left_frame, 
            text="华中科技大学 | 微纳材料设计与制造研究中心 | 刘璋",
            font=("微软雅黑", 8),
            foreground="gray",
            anchor=tk.CENTER
        )
        author_label.grid(row=row+3, column=0, sticky=(tk.W, tk.E), pady=2)
        
        # ===== 右侧图片显示区域 =====
        right_frame.rowconfigure(0, weight=1)
        right_frame.columnconfigure(0, weight=1)
        
        # 创建Notebook用于显示两张图
        self.plot_notebook = ttk.Notebook(right_frame)
        self.plot_notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # curve图显示页面
        self.curve_display_frame = ttk.Frame(self.plot_notebook)
        self.plot_notebook.add(self.curve_display_frame, text="curve图预览")
        
        # state图显示页面
        self.state_display_frame = ttk.Frame(self.plot_notebook)
        self.plot_notebook.add(self.state_display_frame, text="state图预览")
        
        # 放大查看按钮
        zoom_btn = ttk.Button(right_frame, text="🔍 放大查看", command=self.open_image_viewer, width=15)
        zoom_btn.grid(row=1, column=0, pady=5)
        self.add_tooltip(zoom_btn, "在新窗口中放大查看图片，支持缩放和平移")
        
        # 初始提示
        self.show_initial_message()
    
    def show_initial_message(self):
        """显示初始提示信息"""
        for frame in [self.curve_display_frame, self.state_display_frame]:
            label = ttk.Label(
                frame, 
                text="点击「开始绘图」按钮生成图片\n\n"
                     "提示：\n"
                     "• 未选择数据文件时将使用内置示例模板\n"
                     "• 绘图后图片会显示在此处\n"
                     "• 点击「放大查看」可查看高清大图\n"
                     "• 点击「输出图片」可保存到指定目录",
                font=("微软雅黑", 12),
                foreground="gray",
                justify=tk.CENTER
            )
            label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
    
    def create_title_frame(self, parent):
        """创建标题配置页"""
        frame = ttk.Frame(parent, padding="10")
        frame.columnconfigure(1, weight=1)
        
        row = 0
        
        # 图片主标题
        self.show_title_var = tk.BooleanVar(value=self.config.show_title)
        cb = ttk.Checkbutton(frame, text="显示图片主标题", variable=self.show_title_var)
        cb.grid(row=row, column=0, sticky=tk.W, columnspan=2, pady=5)
        self.add_tooltip(cb, "是否在图片顶部显示主标题")
        
        row += 1
        ttk.Label(frame, text="主标题内容:").grid(row=row, column=0, sticky=tk.W, padx=20)
        self.title_text_var = tk.StringVar(value=self.config.title_text)
        entry = ttk.Entry(frame, textvariable=self.title_text_var, width=30)
        entry.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.add_tooltip(entry, "图片顶部的主标题文字，默认为Relative Energy Profile")
        
        row += 1
        ttk.Label(frame, text="标题字体粗细:").grid(row=row, column=0, sticky=tk.W, padx=20)
        self.title_fontweight_var = tk.StringVar(value=self.config.title_fontweight)
        combo = ttk.Combobox(frame, textvariable=self.title_fontweight_var, 
                            values=['normal', 'bold', 'light', 'heavy'], width=15, state="readonly")
        combo.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.add_tooltip(combo, "标题字体的粗细程度")
        
        row += 1
        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        row += 1
        # X轴标题
        self.show_x_title_var = tk.BooleanVar(value=self.config.show_x_title)
        cb = ttk.Checkbutton(frame, text="显示X轴标题", variable=self.show_x_title_var)
        cb.grid(row=row, column=0, sticky=tk.W, columnspan=2, pady=5)
        self.add_tooltip(cb, "是否在X轴下方显示标题")
        
        row += 1
        ttk.Label(frame, text="X轴标题内容:").grid(row=row, column=0, sticky=tk.W, padx=20)
        self.x_title_var = tk.StringVar(value=self.config.x_title_text)
        entry = ttk.Entry(frame, textvariable=self.x_title_var, width=30)
        entry.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.add_tooltip(entry, "X轴下方的标题文字，默认为Reaction Coordinate")
        
        row += 1
        ttk.Label(frame, text="X轴字体粗细:").grid(row=row, column=0, sticky=tk.W, padx=20)
        self.x_fontweight_var = tk.StringVar(value=self.config.x_title_fontweight)
        combo = ttk.Combobox(frame, textvariable=self.x_fontweight_var,
                            values=['normal', 'bold', 'light', 'heavy'], width=15, state="readonly")
        combo.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.add_tooltip(combo, "X轴标题字体的粗细程度")
        
        row += 1
        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        row += 1
        # Y轴标题
        self.show_y_title_var = tk.BooleanVar(value=self.config.show_y_title)
        cb = ttk.Checkbutton(frame, text="显示Y轴标题", variable=self.show_y_title_var)
        cb.grid(row=row, column=0, sticky=tk.W, columnspan=2, pady=5)
        self.add_tooltip(cb, "是否在Y轴左侧显示标题")
        
        row += 1
        ttk.Label(frame, text="Y轴标题内容:").grid(row=row, column=0, sticky=tk.W, padx=20)
        self.y_title_var = tk.StringVar(value=self.config.y_title_text)
        entry = ttk.Entry(frame, textvariable=self.y_title_var, width=30)
        entry.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.add_tooltip(entry, "Y轴左侧的标题文字，默认为Relative Energy (eV)")
        
        row += 1
        ttk.Label(frame, text="Y轴字体粗细:").grid(row=row, column=0, sticky=tk.W, padx=20)
        self.y_fontweight_var = tk.StringVar(value=self.config.y_title_fontweight)
        combo = ttk.Combobox(frame, textvariable=self.y_fontweight_var,
                            values=['normal', 'bold', 'light', 'heavy'], width=15, state="readonly")
        combo.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.add_tooltip(combo, "Y轴标题字体的粗细程度")
        
        return frame
    
    def create_font_frame(self, parent):
        """创建字体配置页"""
        frame = ttk.Frame(parent, padding="10")
        frame.columnconfigure(1, weight=1)
        
        fonts = [
            ("图片主标题字体大小", "font_size_title", 40, "图片顶部主标题的字体大小"),
            ("坐标轴标题字体大小", "font_size_axis_title", 36, "X轴和Y轴标题的字体大小"),
            ("坐标轴刻度字体大小", "font_size_axis_tick", 30, "坐标轴刻度标签的字体大小"),
            ("能量值标签字体大小", "font_size_energy_label", 30, "曲线上能量数值标签的字体大小"),
            ("图例字体大小", "font_size_legend", 24, "图例文字的字体大小"),
        ]
        
        self.font_vars = {}
        for i, (label, key, default, tooltip) in enumerate(fonts):
            ttk.Label(frame, text=f"{label}:").grid(row=i, column=0, sticky=tk.W, pady=5)
            var = tk.IntVar(value=default)
            self.font_vars[key] = var
            spin = ttk.Spinbox(frame, from_=8, to=72, textvariable=var, width=10)
            spin.grid(row=i, column=1, sticky=tk.W, padx=5)
            self.add_tooltip(spin, tooltip)
        
        return frame
    
    def create_display_frame(self, parent):
        """创建显示配置页（v2版本 - 整合能量标签选项）"""
        frame = ttk.Frame(parent, padding="10")
        frame.columnconfigure(1, weight=1)
        
        row = 0
        
        # 能量值标签显示配置（整合curve图和state图）
        ttk.Label(frame, text="能量值数值标签显示:", font=("微软雅黑", 9, "bold")).grid(row=row, column=0, sticky=tk.W, columnspan=2, pady=(0, 5))
        
        row += 1
        self.show_energy_labels_var = tk.BooleanVar(value=self.config.show_energy_labels)
        cb = ttk.Checkbutton(frame, text="在curve图上显示", variable=self.show_energy_labels_var)
        cb.grid(row=row, column=0, sticky=tk.W, padx=20)
        self.add_tooltip(cb, "是否在curve图的数据点旁显示具体的能量数值")
        
        row += 1
        self.show_energy_labels_state_var = tk.BooleanVar(value=self.config.show_energy_labels_state)
        cb = ttk.Checkbutton(frame, text="在state图上显示", variable=self.show_energy_labels_state_var)
        cb.grid(row=row, column=0, sticky=tk.W, padx=20)
        self.add_tooltip(cb, "是否在state图的数据点旁显示具体的能量数值（v2新增）")
        
        row += 1
        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        row += 1
        # 能量数值标签位置配置
        ttk.Label(frame, text="能量数值标签位置:", font=("微软雅黑", 9, "bold")).grid(row=row, column=0, sticky=tk.W, columnspan=2, pady=(0, 5))
        
        row += 1
        ttk.Label(frame, text="curve图 X偏移:").grid(row=row, column=0, sticky=tk.W, padx=20)
        self.label_offset_x_curve_var = tk.DoubleVar(value=self.config.label_offset_x_curve)
        spin = ttk.Spinbox(frame, from_=-2.0, to=2.0, textvariable=self.label_offset_x_curve_var, width=10, increment=0.1)
        spin.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.add_tooltip(spin, "curve图标签水平偏移量（负值向左，正值向右）")
        
        row += 1
        ttk.Label(frame, text="curve图 Y偏移:").grid(row=row, column=0, sticky=tk.W, padx=20)
        self.label_offset_y_curve_var = tk.DoubleVar(value=self.config.label_offset_y_curve)
        spin = ttk.Spinbox(frame, from_=-2.0, to=2.0, textvariable=self.label_offset_y_curve_var, width=10, increment=0.05)
        spin.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.add_tooltip(spin, "curve图标签垂直偏移量（正值向上，负值向下）")
        
        row += 1
        ttk.Label(frame, text="curve图 对齐:").grid(row=row, column=0, sticky=tk.W, padx=20)
        self.label_ha_curve_var = tk.StringVar(value=self.config.label_ha_curve)
        combo = ttk.Combobox(frame, textvariable=self.label_ha_curve_var, 
                            values=['left', 'center', 'right'], width=10, state="readonly")
        combo.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.add_tooltip(combo, "curve图标签水平对齐方式")
        
        row += 1
        ttk.Label(frame, text="state图 X偏移:").grid(row=row, column=0, sticky=tk.W, padx=20)
        self.label_offset_x_state_var = tk.DoubleVar(value=self.config.label_offset_x_state)
        spin = ttk.Spinbox(frame, from_=-2.0, to=2.0, textvariable=self.label_offset_x_state_var, width=10, increment=0.1)
        spin.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.add_tooltip(spin, "state图标签水平偏移量（相对于台阶中点）")
        
        row += 1
        ttk.Label(frame, text="state图 Y偏移:").grid(row=row, column=0, sticky=tk.W, padx=20)
        self.label_offset_y_state_var = tk.DoubleVar(value=self.config.label_offset_y_state)
        spin = ttk.Spinbox(frame, from_=-2.0, to=2.0, textvariable=self.label_offset_y_state_var, width=10, increment=0.05)
        spin.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.add_tooltip(spin, "state图标签垂直偏移量")
        
        row += 1
        ttk.Label(frame, text="state图 对齐:").grid(row=row, column=0, sticky=tk.W, padx=20)
        self.label_ha_state_var = tk.StringVar(value=self.config.label_ha_state)
        combo = ttk.Combobox(frame, textvariable=self.label_ha_state_var, 
                            values=['left', 'center', 'right'], width=10, state="readonly")
        combo.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.add_tooltip(combo, "state图标签水平对齐方式")
        
        row += 1
        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        row += 1
        # Y轴范围设置
        self.auto_y_range_var = tk.BooleanVar(value=self.config.auto_y_range)
        cb = ttk.Checkbutton(frame, text="自动计算Y轴范围", variable=self.auto_y_range_var, 
                            command=self.toggle_y_range)
        cb.grid(row=row, column=0, sticky=tk.W, columnspan=2, pady=5)
        self.add_tooltip(cb, "根据数据自动计算Y轴范围（推荐勾选），取消勾选可手动设置")
        
        row += 1
        ttk.Label(frame, text="Y轴最小值:").grid(row=row, column=0, sticky=tk.W, padx=20)
        self.y_min_var = tk.DoubleVar(value=self.config.y_axis_limits[0])
        self.y_min_spin = ttk.Spinbox(frame, from_=-10, to=10, textvariable=self.y_min_var, width=10, increment=0.1)
        self.y_min_spin.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.add_tooltip(self.y_min_spin, "Y轴显示范围的最小值（自动计算关闭时使用）")
        
        row += 1
        ttk.Label(frame, text="Y轴最大值:").grid(row=row, column=0, sticky=tk.W, padx=20)
        self.y_max_var = tk.DoubleVar(value=self.config.y_axis_limits[1])
        self.y_max_spin = ttk.Spinbox(frame, from_=-10, to=10, textvariable=self.y_max_var, width=10, increment=0.1)
        self.y_max_spin.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.add_tooltip(self.y_max_spin, "Y轴显示范围的最大值（自动计算关闭时使用）")
        
        self.toggle_y_range()
        
        return frame
    
    def create_legend_frame(self, parent):
        """创建图例配置页（v2版本）"""
        frame = ttk.Frame(parent, padding="10")
        frame.columnconfigure(1, weight=1)
        
        row = 0
        
        # ========== 第一层：是否显示图例 ==========
        ttk.Label(frame, text="显示图例:", font=("微软雅黑", 9, "bold")).grid(row=row, column=0, sticky=tk.W, columnspan=2, pady=(0, 5))
        
        row += 1
        self.show_legend_var = tk.BooleanVar(value=self.config.show_legend)
        cb = ttk.Checkbutton(frame, text="在curve图上显示图例", variable=self.show_legend_var)
        cb.grid(row=row, column=0, sticky=tk.W, padx=20)
        self.add_tooltip(cb, "是否在curve图上显示图例")
        
        row += 1
        self.show_legend_state_var = tk.BooleanVar(value=self.config.show_legend_state)
        cb = ttk.Checkbutton(frame, text="在state图上显示图例", variable=self.show_legend_state_var)
        cb.grid(row=row, column=0, sticky=tk.W, padx=20)
        self.add_tooltip(cb, "是否在state图上显示图例（v2新增）")
        
        row += 1
        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        # ========== 第二层：图例位置 ==========
        row += 1
        ttk.Label(frame, text="图例位置:", font=("微软雅黑", 9, "bold")).grid(row=row, column=0, sticky=tk.W, columnspan=2, pady=(0, 5))
        
        row += 1
        ttk.Label(frame, text="curve图位置:").grid(row=row, column=0, sticky=tk.W, padx=20)
        self.legend_loc_var = tk.StringVar(value=self.config.legend_loc)
        combo = ttk.Combobox(frame, textvariable=self.legend_loc_var, state="readonly", width=20)
        combo['values'] = [
            'upper right', 'upper left', 'upper center',
            'lower right', 'lower left', 'lower center',
            'center right', 'center left', 'center',
            'best'
        ]
        combo.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.add_tooltip(combo, "curve图图例在图中的位置")
        
        row += 1
        ttk.Label(frame, text="state图位置:").grid(row=row, column=0, sticky=tk.W, padx=20)
        self.legend_loc_state_var = tk.StringVar(value=self.config.legend_loc_state)
        combo = ttk.Combobox(frame, textvariable=self.legend_loc_state_var, state="readonly", width=20)
        combo['values'] = [
            'upper right', 'upper left', 'upper center',
            'lower right', 'lower left', 'lower center',
            'center right', 'center left', 'center',
            'best'
        ]
        combo.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.add_tooltip(combo, "state图图例在图中的位置（v2新增，可独立设置）")
        
        row += 1
        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        # ========== 第三层：图例边框 ==========
        row += 1
        ttk.Label(frame, text="图例边框:", font=("微软雅黑", 9, "bold")).grid(row=row, column=0, sticky=tk.W, columnspan=2, pady=(0, 5))
        
        row += 1
        self.legend_frameon_var = tk.BooleanVar(value=self.config.legend_frameon)
        cb = ttk.Checkbutton(frame, text="curve图图例带边框", variable=self.legend_frameon_var)
        cb.grid(row=row, column=0, sticky=tk.W, padx=20)
        self.add_tooltip(cb, "curve图图例是否显示边框")
        
        row += 1
        # state图图例边框（可以与curve图分开设置）
        self.legend_frameon_state_var = tk.BooleanVar(value=self.config.legend_frameon)
        cb = ttk.Checkbutton(frame, text="state图图例带边框", variable=self.legend_frameon_state_var)
        cb.grid(row=row, column=0, sticky=tk.W, padx=20)
        self.add_tooltip(cb, "state图图例是否显示边框（v2新增，可与curve图分开设置）")
        
        return frame
    
    def create_advanced_frame(self, parent):
        """创建高级配置页"""
        frame = ttk.Frame(parent, padding="10")
        frame.columnconfigure(1, weight=1)
        
        row = 0
        
        # 图像尺寸
        ttk.Label(frame, text="图像宽度:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.fig_width_var = tk.IntVar(value=20)
        spin = ttk.Spinbox(frame, from_=10, to=50, textvariable=self.fig_width_var, width=10)
        spin.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.add_tooltip(spin, "输出图像的宽度（英寸）")
        
        row += 1
        ttk.Label(frame, text="图像高度:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.fig_height_var = tk.IntVar(value=15)
        spin = ttk.Spinbox(frame, from_=5, to=30, textvariable=self.fig_height_var, width=10)
        spin.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.add_tooltip(spin, "输出图像的高度（英寸）")
        
        row += 1
        ttk.Label(frame, text="图像分辨率(DPI):").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.dpi_var = tk.IntVar(value=300)
        combo = ttk.Combobox(frame, textvariable=self.dpi_var, values=[150, 300, 600], width=10, state="readonly")
        combo.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.add_tooltip(combo, "输出图像的分辨率，越高越清晰但文件越大")
        
        row += 1
        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        row += 1
        # 线宽
        ttk.Label(frame, text="曲线线宽:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.line_width_curve_var = tk.IntVar(value=4)
        spin = ttk.Spinbox(frame, from_=1, to=10, textvariable=self.line_width_curve_var, width=10)
        spin.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.add_tooltip(spin, "曲线的线条宽度")
        
        row += 1
        ttk.Label(frame, text="分段线宽:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.line_width_segment_var = tk.IntVar(value=8)
        spin = ttk.Spinbox(frame, from_=1, to=15, textvariable=self.line_width_segment_var, width=10)
        spin.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.add_tooltip(spin, "state图中分段线的宽度")
        
        row += 1
        ttk.Label(frame, text="坐标轴线宽:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.line_width_frame_var = tk.DoubleVar(value=3)
        spin = ttk.Spinbox(frame, from_=0.5, to=5.0, textvariable=self.line_width_frame_var, width=10, increment=0.1)
        spin.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.add_tooltip(spin, "图片四周边框的线宽")
        
        row += 1
        ttk.Label(frame, text="插值点数:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.interp_var = tk.IntVar(value=50)
        spin = ttk.Spinbox(frame, from_=10, to=200, textvariable=self.interp_var, width=10)
        spin.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.add_tooltip(spin, "曲线平滑度，数值越大曲线越平滑但计算越慢")
        
        row += 1
        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        row += 1
        # state图 连接线配置（v2新增）
        ttk.Label(frame, text="state图 连接线配置:", font=("微软雅黑", 9, "bold")).grid(row=row, column=0, sticky=tk.W, pady=5)
        
        row += 1
        self.connect_steps_var = tk.BooleanVar(value=self.config.connect_steps)
        cb = ttk.Checkbutton(frame, text="用虚线连接台阶", variable=self.connect_steps_var)
        cb.grid(row=row, column=0, sticky=tk.W, columnspan=2, pady=5)
        self.add_tooltip(cb, "是否用虚线将state图中相邻的台阶连接起来（v2新增功能，默认开启）")
        
        row += 1
        ttk.Label(frame, text="连接线型:").grid(row=row, column=0, sticky=tk.W, padx=20, pady=5)
        self.line_style_connector_var = tk.StringVar(value=self.config.line_style_connector)
        combo = ttk.Combobox(frame, textvariable=self.line_style_connector_var, 
                            values=['--', ':', '-.', '-'], width=10, state="readonly")
        combo.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.add_tooltip(combo, "连接台阶的线型：'--'虚线(推荐), ':'点线, '-.'点划线, '-'实线")
        
        row += 1
        ttk.Label(frame, text="连接线宽:").grid(row=row, column=0, sticky=tk.W, padx=20, pady=5)
        self.line_width_connector_var = tk.DoubleVar(value=self.config.line_width_connector)
        spin = ttk.Spinbox(frame, from_=0.5, to=5.0, textvariable=self.line_width_connector_var, 
                          width=10, increment=0.1)
        spin.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.add_tooltip(spin, "连接虚线的线宽")
        
        return frame
    
    def add_tooltip(self, widget, text):
        """为组件添加提示"""
        Tooltip(widget, text)
    
    def toggle_y_range(self):
        """切换Y轴范围输入框的启用状态"""
        state = "disabled" if self.auto_y_range_var.get() else "normal"
        self.y_min_spin.config(state=state)
        self.y_max_spin.config(state=state)
    
    def browse_data_file(self):
        """浏览数据文件"""
        filename = filedialog.askopenfilename(
            title="选择数据文件",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        if filename:
            self.data_file.set(filename)
            # 自动设置输出目录
            if not self.output_dir.get():
                self.output_dir.set(os.path.dirname(filename))
            self.status_var.set(f"已选择数据文件: {os.path.basename(filename)}")
    
    def clear_data_file(self):
        """清除数据文件选择"""
        self.data_file.set("")
        self.status_var.set("已清除数据文件选择，将使用内置模板")
    
    def browse_output_dir(self):
        """浏览输出目录"""
        dirname = filedialog.askdirectory(title="选择输出目录")
        if dirname:
            self.output_dir.set(dirname)
    
    def export_template(self):
        """导出内置模板到指定位置"""
        filename = filedialog.asksaveasfilename(
            title="导出内置模板",
            defaultextension=".csv",
            initialfile=BUILT_IN_TEMPLATE_FILENAME,
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
                    f.write(BUILT_IN_TEMPLATE)
                self.status_var.set(f"模板已导出到: {filename}")
                messagebox.showinfo("成功", f"内置模板已导出到:\n{filename}\n\n您可以使用此模板作为数据格式参考。")
            except Exception as e:
                messagebox.showerror("错误", f"导出模板失败:\n{str(e)}")
    
    def reset_defaults(self):
        """恢复默认设置"""
        if messagebox.askyesno("确认", "确定要恢复所有默认设置吗？"):
            self.config = PlotConfig()
            # 这里可以添加重置所有界面控件到默认值的逻辑
            messagebox.showinfo("提示", "已恢复默认设置，请重新打开软件生效")
    
    def collect_config(self):
        """从界面收集配置"""
        config = PlotConfig()
        
        # 标题配置
        config.show_title = self.show_title_var.get()
        config.title_text = self.title_text_var.get() or config.title_text
        config.title_fontweight = self.title_fontweight_var.get()
        config.show_x_title = self.show_x_title_var.get()
        config.x_title_text = self.x_title_var.get() or config.x_title_text
        config.x_title_fontweight = self.x_fontweight_var.get()
        config.show_y_title = self.show_y_title_var.get()
        config.y_title_text = self.y_title_var.get() or config.y_title_text
        config.y_title_fontweight = self.y_fontweight_var.get()
        
        # 字体配置
        config.font_size_title = self.font_vars["font_size_title"].get()
        config.font_size_axis_title = self.font_vars["font_size_axis_title"].get()
        config.font_size_axis_tick = self.font_vars["font_size_axis_tick"].get()
        config.font_size_energy_label = self.font_vars["font_size_energy_label"].get()
        config.font_size_legend = self.font_vars["font_size_legend"].get()
        
        # 显示配置
        config.show_energy_labels = self.show_energy_labels_var.get()
        config.show_energy_labels_state = self.show_energy_labels_state_var.get()  # v2新增
        
        # 能量数值标签位置配置
        config.label_offset_x_curve = self.label_offset_x_curve_var.get()
        config.label_offset_y_curve = self.label_offset_y_curve_var.get()
        config.label_ha_curve = self.label_ha_curve_var.get()
        config.label_offset_x_state = self.label_offset_x_state_var.get()
        config.label_offset_y_state = self.label_offset_y_state_var.get()
        config.label_ha_state = self.label_ha_state_var.get()
        
        config.auto_y_range = self.auto_y_range_var.get()
        if not config.auto_y_range:
            y_min = self.y_min_var.get()
            y_max = self.y_max_var.get()
            config.y_axis_limits = (y_min, y_max)
        
        # 图例配置
        config.show_legend = self.show_legend_var.get()
        config.show_legend_state = self.show_legend_state_var.get()  # v2新增
        config.legend_loc = self.legend_loc_var.get()
        config.legend_loc_state = self.legend_loc_state_var.get()  # v2新增：state图独立图例位置
        config.legend_frameon = self.legend_frameon_var.get()
        # state图图例边框目前与curve图共用同一设置，如需分开可取消下面注释
        # config.legend_frameon_state = self.legend_frameon_state_var.get()  # v2新增（可选）
        
        # 高级配置
        config.figure_size = (self.fig_width_var.get(), self.fig_height_var.get())
        config.dpi = self.dpi_var.get()
        config.line_width_curve = self.line_width_curve_var.get()
        config.line_width_segment = self.line_width_segment_var.get()
        config.line_width_frame = self.line_width_frame_var.get()
        config.interpolation_points = self.interp_var.get()
        
        # state图 专用配置（v2新增）
        config.connect_steps = self.connect_steps_var.get()
        config.line_style_connector = self.line_style_connector_var.get()
        config.line_width_connector = self.line_width_connector_var.get()
        
        return config
    
    def show_about(self):
        """显示关于对话框"""
        about_text = """
能量反应路径图绘制软件 v1.0

作者: 刘璋
单位: 华中科技大学 | 微纳材料设计与制造研究中心

版本: 1.0
日期: 2023-12-01

功能更新：
- 内置数据模板，支持直接使用示例数据绘图
- 图形界面内展示图片，支持放大查看
- 手动输出按钮控制图片保存

本软件用于绘制化学反应路径的能量剖面图，
支持生成两种风格的能垒图：
  - curve图: 横线+平滑曲线风格
  - state图: 分段实线+散点风格

Copyright (c) 2023 华中科技大学
微纳材料设计与制造研究中心
        """
        messagebox.showinfo("关于", about_text.strip())
    
    def plot(self):
        """执行绘图（在GUI中显示）"""
        # 确定数据来源
        data_file = self.data_file.get()
        use_builtin = not data_file
        
        try:
            self.status_var.set("正在加载数据..." if not use_builtin else "正在加载内置模板...")
            self.root.update()
            
            # 加载数据
            if use_builtin:
                data, y_values = load_csv_data_from_string(BUILT_IN_TEMPLATE)
                source_name = "内置模板"
            else:
                if not os.path.exists(data_file):
                    messagebox.showerror("错误", f"数据文件不存在：{data_file}")
                    return
                data, y_values = load_csv_data_from_file(data_file)
                source_name = os.path.basename(data_file)
            
            # 保存当前数据
            self.current_data = data
            self.current_y_values = y_values
            
            # 收集配置
            config = self.collect_config()
            self.current_config = config
            
            # 自动计算Y轴范围
            if config.auto_y_range:
                config.y_axis_limits = get_y_range(y_values)
            
            self.status_var.set("正在生成 curve图...")
            self.root.update()
            
            # 生成curve图（返回Figure对象）
            self.fig_curve = self.create_curve_figure(data, config)
            self.display_curve_plot()
            
            self.status_var.set("正在生成 state图...")
            self.root.update()
            
            # 生成state图（返回Figure对象）
            self.fig_state = self.create_state_figure(data, config)
            self.display_state_plot()
            
            self.status_var.set(f"绘图完成！数据来源: {source_name}")
            
        except Exception as e:
            self.status_var.set(f"错误: {str(e)}")
            messagebox.showerror("错误", f"绘图过程中发生错误：\n{str(e)}")
            import traceback
            traceback.print_exc()
    
    def create_curve_figure(self, data, config, preview_mode=True):
        """创建curve图Figure对象
        
        参数:
            data: 反应数据
            config: 配置对象
            preview_mode: 是否为预览模式（True时使用较低的DPI和较小的尺寸以适应屏幕显示）
        """
        import re
        
        if preview_mode:
            # 预览模式：使用较小的尺寸和较低的DPI，以适应GUI显示
            preview_figsize = (10, 7.5)  # 屏幕预览尺寸
            preview_dpi = 100
            scale_factor = 0.5  # 字体缩放因子
            
            fig = Figure(figsize=preview_figsize, dpi=preview_dpi)
            ax = fig.add_subplot(111)
            
            # 预览模式下缩小字体大小
            font_size_title = int(config.font_size_title * scale_factor)
            font_size_axis_title = int(config.font_size_axis_title * scale_factor)
            font_size_axis_tick = int(config.font_size_axis_tick * scale_factor)
            font_size_energy_label = int(config.font_size_energy_label * scale_factor)
            font_size_legend = int(config.font_size_legend * scale_factor)
            line_width_curve = max(1, config.line_width_curve * scale_factor)
        else:
            # 导出模式：使用用户配置的高DPI和大尺寸
            fig = Figure(figsize=config.figure_size, dpi=config.dpi)
            ax = fig.add_subplot(111)
            
            font_size_title = config.font_size_title
            font_size_axis_title = config.font_size_axis_title
            font_size_axis_tick = config.font_size_axis_tick
            font_size_energy_label = config.font_size_energy_label
            font_size_legend = config.font_size_legend
            line_width_curve = config.line_width_curve
        
        x_positions = None
        for y_path, color, label in zip(data.y_values, data.colors, data.path_labels):
            # 绘制曲线逻辑
            x_processed = []
            y_processed = []
            x_pos_list = [i * 2 + 2 for i in range(len(y_path))]
            
            for i, (y_val, x_label) in enumerate(zip(y_path, data.x_labels)):
                if y_val == "":
                    continue
                is_ts = re.match(r"^TS", x_label) is not None
                if is_ts:
                    y_processed.append(float(y_val))
                    x_processed.append(x_pos_list[i])
                else:
                    y_processed.extend([float(y_val), float(y_val)])
                    x_processed.extend([x_pos_list[i] - 0.5, x_pos_list[i] + 0.5])
            
            # 绘制平滑曲线
            if len(x_processed) >= 2:
                x_smooth = []
                y_smooth = []
                for i in range(len(x_processed) - 1):
                    x_segment = np.linspace(x_processed[i], x_processed[i + 1], 
                                           config.interpolation_points).tolist()
                    if y_processed[i] < y_processed[i + 1]:
                        y_segment = generate_cosine_points(
                            y_processed[i], y_processed[i + 1], "up", config.interpolation_points
                        )
                    elif y_processed[i] > y_processed[i + 1]:
                        y_segment = generate_cosine_points(
                            y_processed[i + 1], y_processed[i], "down", config.interpolation_points
                        )
                    else:
                        y_segment = np.linspace(y_processed[i], y_processed[i + 1], 
                                               config.interpolation_points).tolist()
                    x_smooth.extend(x_segment)
                    y_smooth.extend(y_segment)
                
                ax.plot(x_smooth, y_smooth, linestyle='-', 
                        linewidth=line_width_curve, color=color, label=label)
            
            # 添加能量值标签
            if config.show_energy_labels:
                for i, y_val in enumerate(y_path):
                    if y_val != "":
                        x_pos = x_pos_list[i] + config.label_offset_x_curve
                        y_pos = float(y_val) + config.label_offset_y_curve
                        ax.text(x_pos, y_pos,
                               f"{float(y_val):.2f}", 
                               fontsize=font_size_energy_label, 
                               color=color,
                               ha=config.label_ha_curve)
            
            x_positions = x_pos_list
        
        # 应用样式（使用调整后的字体大小）
        self.apply_common_style_to_ax(ax, data, x_positions, config, 
                                      font_size_title, font_size_axis_title, 
                                      font_size_axis_tick, preview_mode)
        
        # 添加图例
        if config.show_legend:
            legend_kwargs = {
                'loc': config.legend_loc,
                'fontsize': font_size_legend,
                'frameon': config.legend_frameon,
            }
            if config.legend_bbox_to_anchor is not None:
                legend_kwargs['bbox_to_anchor'] = config.legend_bbox_to_anchor
            ax.legend(**legend_kwargs)
        
        fig.tight_layout()
        return fig
    
    def create_state_figure(self, data, config, preview_mode=True):
        """创建state图Figure对象
        
        参数:
            data: 反应数据
            config: 配置对象
            preview_mode: 是否为预览模式（True时使用较低的DPI和较小的尺寸以适应屏幕显示）
        """
        if preview_mode:
            # 预览模式：使用较小的尺寸和较低的DPI，以适应GUI显示
            preview_figsize = (10, 7.5)  # 屏幕预览尺寸
            preview_dpi = 100
            scale_factor = 0.5  # 字体缩放因子
            
            fig = Figure(figsize=preview_figsize, dpi=preview_dpi)
            ax = fig.add_subplot(111)
            
            # 预览模式下缩小字体大小
            font_size_title = int(config.font_size_title * scale_factor)
            font_size_axis_title = int(config.font_size_axis_title * scale_factor)
            font_size_axis_tick = int(config.font_size_axis_tick * scale_factor)
            font_size_energy_label = int(config.font_size_energy_label * scale_factor)
            font_size_legend = int(config.font_size_legend * scale_factor)
            line_width_segment = max(1, config.line_width_segment * scale_factor)
            line_width_connector = max(0.5, config.line_width_connector * scale_factor)
        else:
            # 导出模式：使用用户配置的高DPI和大尺寸
            fig = Figure(figsize=config.figure_size, dpi=config.dpi)
            ax = fig.add_subplot(111)
            
            font_size_title = config.font_size_title
            font_size_axis_title = config.font_size_axis_title
            font_size_axis_tick = config.font_size_axis_tick
            font_size_energy_label = config.font_size_energy_label
            font_size_legend = config.font_size_legend
            line_width_segment = config.line_width_segment
            line_width_connector = config.line_width_connector
        
        # 计算散点图的x轴位置
        x_scatter_positions = [x * 2 - 0.5 for x in data.x_coords]
        
        # 绘制分段实线和散点
        for y_path, color, label in zip(data.y_values, data.colors, data.path_labels):
            # 绘制分段实线（台阶）
            x_doubled = []
            y_doubled = []
            for i, yi in enumerate(y_path):
                if yi != "":
                    x_doubled.extend([2 * i + 1, 2 * i + 2])
                    y_doubled.extend([yi, yi])
            
            for i in range(0, len(y_doubled), 2):
                ax.plot(
                    [x_doubled[i], x_doubled[i+1]], 
                    [y_doubled[i], y_doubled[i+1]], 
                    linestyle='-', 
                    linewidth=line_width_segment, 
                    color=color
                )
            
            # 收集有效数据点用于散点和连接
            step_positions = []  # (头部x, 中部x, 尾部x, y值)
            for i, (x_pos, y_val) in enumerate(zip(x_scatter_positions, y_path)):
                if y_val != "":
                    head_x = 2 * i + 1      # 台阶左端（头部）
                    tail_x = 2 * i + 2      # 台阶右端（尾部）
                    mid_x = x_pos           # 台阶中部（散点位置）
                    step_positions.append((head_x, mid_x, tail_x, float(y_val)))
                    
                    # 显示能量值标签
                    if config.show_energy_labels_state:
                        x_label_pos = mid_x + config.label_offset_x_state
                        y_label_pos = float(y_val) + config.label_offset_y_state
                        ax.text(x_label_pos, y_label_pos,
                               f"{float(y_val):.2f}", 
                               fontsize=font_size_energy_label, 
                               color=color, 
                               ha=config.label_ha_state)
            
            # 用虚线连接台阶
            if config.connect_steps and len(step_positions) >= 2:
                for i in range(len(step_positions) - 1):
                    prev_tail_x = step_positions[i][2]
                    prev_y = step_positions[i][3]
                    curr_head_x = step_positions[i+1][0]
                    curr_y = step_positions[i+1][3]
                    
                    ax.plot(
                        [prev_tail_x, curr_head_x], 
                        [prev_y, curr_y], 
                        linestyle=config.line_style_connector, 
                        linewidth=line_width_connector, 
                        color=color,
                        alpha=0.6
                    )
            
            # 绘制散点（用于图例）
            x_scatter = [pos[1] for pos in step_positions]
            y_scatter = [pos[3] for pos in step_positions]
            # 预览模式下调整散点大小和线宽
            if preview_mode:
                scatter_s = 400  # 预览模式使用更小的散点
                scatter_linewidth = 3  # 预览模式使用更细的线条
            else:
                scatter_s = 1200  # 导出模式使用原始大小
                scatter_linewidth = 6  # 导出模式使用原始线宽
            ax.scatter(x_scatter, y_scatter, linewidth=scatter_linewidth, color=color,
                       label=label if config.show_legend_state else None, 
                       marker='_', s=scatter_s)
        
        # 设置X轴刻度位置
        x_tick_positions = [x * 2 - 0.5 for x in data.x_coords]
        
        # 应用样式（使用调整后的字体大小）
        self.apply_common_style_to_ax(ax, data, x_tick_positions, config,
                                      font_size_title, font_size_axis_title,
                                      font_size_axis_tick, preview_mode)
        
        # 添加图例
        if config.show_legend_state:
            legend_kwargs = {
                'loc': config.legend_loc_state,  # 使用独立的state图图例位置
                'fontsize': font_size_legend,
                'frameon': config.legend_frameon,
            }
            if config.legend_bbox_to_anchor is not None:
                legend_kwargs['bbox_to_anchor'] = config.legend_bbox_to_anchor
            ax.legend(**legend_kwargs)
        
        fig.tight_layout()
        return fig
    
    def apply_common_style_to_ax(self, ax, data, x_positions, config, 
                                  font_size_title=None, font_size_axis_title=None, 
                                  font_size_axis_tick=None, preview_mode=True):
        """应用通用样式到Axes对象
        
        参数:
            ax: matplotlib Axes对象
            data: 反应数据
            x_positions: X轴位置
            config: 配置对象
            font_size_title: 标题字体大小（预览模式下使用缩放后的值）
            font_size_axis_title: 坐标轴标题字体大小（预览模式下使用缩放后的值）
            font_size_axis_tick: 坐标轴刻度字体大小（预览模式下使用缩放后的值）
            preview_mode: 是否为预览模式
        """
        # 使用传入的字体大小或配置中的默认值
        fs_title = font_size_title if font_size_title is not None else config.font_size_title
        fs_axis_title = font_size_axis_title if font_size_axis_title is not None else config.font_size_axis_title
        fs_axis_tick = font_size_axis_tick if font_size_axis_tick is not None else config.font_size_axis_tick
        
        # 预览模式下调整边框线宽
        if preview_mode:
            line_width_frame = max(1, config.line_width_frame * 0.5)
        else:
            line_width_frame = config.line_width_frame
        
        # 图片标题
        if config.show_title and config.title_text:
            ax.set_title(config.title_text, 
                      fontsize=fs_title, 
                      fontweight=config.title_fontweight, 
                      pad=config.title_pad)
        
        # 刻度方向
        ax.tick_params(axis='both', direction='in')
        ax.tick_params(axis='x', top=True, bottom=True, labeltop=False, labelbottom=True)
        
        # Y轴格式
        ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%.1f'))
        
        # Y轴范围
        ax.set_ylim(config.y_axis_limits)
        ax.tick_params(axis='y', labelsize=fs_axis_tick)
        
        # X/Y轴标题
        if config.show_x_title and config.x_title_text:
            ax.set_xlabel(config.x_title_text, fontsize=fs_axis_title, 
                         fontweight=config.x_title_fontweight)
        if config.show_y_title and config.y_title_text:
            ax.set_ylabel(config.y_title_text, fontsize=fs_axis_title, 
                         fontweight=config.y_title_fontweight)
        
        # X轴刻度
        if x_positions:
            ax.set_xticks(x_positions)
            ax.set_xticklabels(data.x_labels, fontsize=fs_axis_tick)
        
        # 边框线宽
        for spine in ['bottom', 'top', 'right', 'left']:
            ax.spines[spine].set_linewidth(line_width_frame)
        ax.tick_params(axis='both', width=1, length=6, colors='black')
    
    def display_curve_plot(self):
        """在GUI中显示curve图"""
        # 清除旧的内容
        for widget in self.curve_display_frame.winfo_children():
            widget.destroy()
        
        # 创建Canvas
        self.canvas_curve = FigureCanvasTkAgg(self.fig_curve, master=self.curve_display_frame)
        self.canvas_curve.draw()
        self.canvas_curve.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # 添加工具栏
        toolbar = NavigationToolbar2Tk(self.canvas_curve, self.curve_display_frame)
        toolbar.update()
    
    def display_state_plot(self):
        """在GUI中显示state图"""
        # 清除旧的内容
        for widget in self.state_display_frame.winfo_children():
            widget.destroy()
        
        # 创建Canvas
        self.canvas_state = FigureCanvasTkAgg(self.fig_state, master=self.state_display_frame)
        self.canvas_state.draw()
        self.canvas_state.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # 添加工具栏
        toolbar = NavigationToolbar2Tk(self.canvas_state, self.state_display_frame)
        toolbar.update()
    
    def open_image_viewer(self):
        """打开图片查看器窗口"""
        if self.fig_curve is None or self.fig_state is None:
            messagebox.showinfo("提示", "请先点击「开始绘图」生成图片")
            return
        
        # 创建独立窗口显示放大的图片
        ImageViewerWindow(self.root, self.fig_curve, self.fig_state)
    
    def save_images(self):
        """保存图片到文件"""
        if self.fig_curve is None or self.fig_state is None:
            messagebox.showinfo("提示", "请先点击「开始绘图」生成图片")
            return
        
        # 确定输出路径
        if self.data_file.get():
            default_dir = os.path.dirname(self.data_file.get())
        else:
            default_dir = os.getcwd()
        
        output_dir = self.output_dir.get() or default_dir
        
        # 确保输出目录存在
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                messagebox.showerror("错误", f"无法创建输出目录：{e}")
                return
        
        curve_path = os.path.join(output_dir, (self.curve_name.get() or "curve图") + ".png")
        state_path = os.path.join(output_dir, (self.state_name.get() or "state图") + ".png")
        
        try:
            self.status_var.set("正在生成高清图片...")
            self.root.update()
            
            # 使用导出模式重新生成高DPI图片
            if self.current_data is not None and self.current_config is not None:
                export_fig_curve = self.create_curve_figure(self.current_data, self.current_config, preview_mode=False)
                export_fig_state = self.create_state_figure(self.current_data, self.current_config, preview_mode=False)
                
                export_fig_curve.savefig(curve_path, dpi=self.current_config.dpi)
                export_fig_state.savefig(state_path, dpi=self.current_config.dpi)
                
                # 清理导出的Figure对象
                from matplotlib.pyplot import close
                close(export_fig_curve)
                close(export_fig_state)
            else:
                # 如果没有当前数据，直接保存预览图
                self.fig_curve.savefig(curve_path, dpi=self.current_config.dpi if self.current_config else 300)
                self.fig_state.savefig(state_path, dpi=self.current_config.dpi if self.current_config else 300)
            
            self.status_var.set(f"图片已保存至: {output_dir}")
            messagebox.showinfo("成功", f"图片已成功保存！\n\ncurve图: {curve_path}\nstate图: {state_path}")
            
        except Exception as e:
            messagebox.showerror("错误", f"保存图片失败：{str(e)}")


def main():
    root = tk.Tk()
    app = PlotGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
