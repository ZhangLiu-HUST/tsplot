# -*- coding: utf-8 -*-
"""
能量反应路径图绘制脚本

作者: 刘璋
单位: 华中科技大学 | 微纳材料设计与制造研究中心
版本: 1.0
日期: 2023-12-01
功能：根据CSV数据同时生成两种风格的能垒图：
  1. curve.png - 横线+平滑曲线风格
  2. state.png - 分段实线+散点风格

用法：
  python plot_combined.py <data_file.csv>
  
示例：
  python plot_combined.py data.csv

CSV文件格式：
  - 第1行: 路径名称/图例标签（第1列是'index'，后续是路径名）
  - 第2行: 颜色配置（第1列是'color'，后续是R,G,B值）
  - 第3行起: 数据（第1列是状态名称，后续是各路径能量值）
  
注：图片标题、Y轴标题在 PlotConfig 类中配置

Copyright (c) 2023 华中科技大学微纳材料设计与制造研究中心
"""

import sys
import re
import logging
import csv
from typing import List, Tuple, Dict, Optional, Union, Any, NamedTuple
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ==================== 日志配置 ====================

def setup_logging() -> logging.Logger:
    """配置日志记录器"""
    logger = logging.getLogger("plot_combined")
    logger.setLevel(logging.INFO)
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(levelname)s] %(message)s')
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    return logger

logger = setup_logging()

# ==================== 配置类 ====================

class PlotConfig(NamedTuple):
    """
    绘图配置类（不可变）
    
    使用 NamedTuple 提供类型安全且不可变的配置对象
    所有配置按功能模块分组，字体大小统一在"字体配置"部分设置
    """
    
    # ========== 1. 图像基础配置 ==========
    figure_size: Tuple[int, int] = (20, 15)      # 图像尺寸 (宽, 高)
    dpi: int = 300                               # 图像分辨率
    
    # ========== 2. 字体配置（统一设置各类文字大小） ==========
    # 标题字体
    font_size_title: int = 40                    # 图片主标题字体大小
    font_size_axis_title: int = 36               # X/Y轴标题字体大小
    
    # 刻度与标签字体
    font_size_axis_tick: int = 30                # 坐标轴刻度标签字体大小
    font_size_energy_label: int = 30             # 能量值数值标签字体大小
    font_size_legend: int = 24                   # 图例字体大小
    
    # ========== 3. 图片主标题配置 ==========
    show_title: bool = True                      # 是否显示图片主标题
    title_text: str = "Relative Energy Profile"  # 图片主标题内容
    title_fontweight: str = 'bold'               # 标题字体粗细
    title_pad: int = 20                          # 标题与图形的间距
    
    # ========== 4. 坐标轴标题配置 ==========
    # X轴
    show_x_title: bool = True                    # 是否显示X轴标题
    x_title_text: str = "Reaction Coordinate"    # X轴标题内容
    x_title_fontweight: str = 'bold'             # X轴标题字体粗细
    
    # Y轴
    show_y_title: bool = True                    # 是否显示Y轴标题
    y_title_text: str = "Relative Energy (eV)"   # Y轴标题内容
    y_title_fontweight: str = 'bold'             # Y轴标题字体粗细
    
    # ========== 5. 能量值标签配置 ==========
    show_energy_labels: bool = True              # 是否显示能量值数值标签（curve.png）
    show_energy_labels_state: bool = True        # 是否显示能量值数值标签（state.png）
    
    # 能量数值标签位置配置（相对于数据点的偏移量）
    # curve 图标签位置
    label_offset_x_curve: float = -0.2            # X轴偏移量（负值向左，正值向右）
    label_offset_y_curve: float = 0.06            # Y轴偏移量（正值向上，负值向下）
    label_ha_curve: str = 'left'                  # 水平对齐方式：'left', 'center', 'right'
    
    # state 图标签位置
    label_offset_x_state: float = 0.5             # X轴偏移量（相对于台阶中点）
    label_offset_y_state: float = 0.1             # Y轴偏移量
    label_ha_state: str = 'right'                 # 水平对齐方式
  
    # ========== 6. 图例配置 ==========
    show_legend: bool = True                     # 是否显示图例（curve.png）
    show_legend_state: bool = True               # 是否显示图例（state.png）
    legend_loc: str = 'upper right'              # 图例位置（curve.png和state.png共用）
    legend_frameon: bool = True                  # 图例是否带边框
    legend_bbox_to_anchor: Optional[Tuple[float, float]] = None  # 图例锚点位置（None表示使用默认位置）
    
    # ========== 6.5 state.png 专用配置 ==========
    connect_steps: bool = True                   # 是否用虚线连接台阶
    line_style_connector: str = '--'             # 连接线型（'--'虚线, ':'点线, '-.'点划线等）
    line_width_connector: float = 3.0            # 连接线宽
    
    # ========== 7. 线宽配置 ==========
    line_width_curve: int = 4                    # 曲线线宽
    line_width_segment: int = 8                  # 分段实线线宽
    line_width_frame: float = 3                # 坐标轴线宽
    
    # ========== 8. 坐标轴范围配置 ==========
    auto_y_range: bool = True                    # 是否根据数据自动计算Y轴范围
    y_axis_limits: Tuple[float, float] = (-2.0, 1.0)    # Y轴显示范围（自动计算为False时使用）
    
    # ========== 9. 插值配置 ==========
    interpolation_points: int = 50               # 曲线插值点数（越大越平滑）
    
    # ========== 10. 输出配置 ==========
    output_curve: str = "./curve.png"            # curve.png输出路径
    output_state: str = "./state.png"            # state.png输出路径


class ReactionData:
    """
    反应数据容器类
    
    封装所有从Excel加载的数据，提供结构化访问
    """
    def __init__(
        self,
        path_labels: List[str],
        x_labels: List[str],
        colors: List[List[float]],
        x_coords: List[int],
        y_values: List[List[Union[float, str]]],
        row_minimums: List[float]
    ):
        self.path_labels = path_labels
        self.x_labels = x_labels
        self.colors = colors
        self.x_coords = x_coords
        self.y_values = y_values
        self.row_minimums = row_minimums
    
    def validate(self) -> None:
        """
        验证数据完整性
        
        抛出:
            ValueError: 当数据不符合预期格式时
        """
        if not self.y_values:
            raise ValueError("能量数据为空")
        
        if not self.x_labels:
            raise ValueError("状态标签为空")
        
        num_paths = len(self.y_values)
        if num_paths != len(self.colors):
            raise ValueError(f"路径数量({num_paths})与颜色配置({len(self.colors)})不匹配")
        
        if num_paths != len(self.path_labels):
            raise ValueError(f"路径数量({num_paths})与路径标签({len(self.path_labels)})不匹配")
        
        # 检查每条路径的数据点数量
        expected_points = len(self.x_labels)
        for i, y_path in enumerate(self.y_values):
            if len(y_path) != expected_points:
                raise ValueError(f"路径{i+1}的数据点数量({len(y_path)})与状态数量({expected_points})不匹配")
        
        logger.info(f"数据验证通过: {num_paths}条路径, {expected_points}个状态")


# ==================== 数学工具函数 ====================

def generate_cosine_points(
    y_small: float, 
    y_large: float, 
    direction: str,
    num_points: int = 50
) -> List[float]:
    """
    生成余弦曲线插值点
    
    参数:
        y_small: 较小的y值（起点或终点）
        y_large: 较大的y值
        direction: 'up' 表示上升曲线，'down' 表示下降曲线
        num_points: 插值点数量
    
    返回:
        包含插值点的列表
    
    抛出:
        ValueError: 当direction参数无效时
    """
    if direction not in ("up", "down"):
        raise ValueError(f"无效的方向参数: {direction}，必须是 'up' 或 'down'")
    
    if direction == "up":
        x_vals = np.linspace(np.pi, 2 * np.pi, num_points)
    else:
        x_vals = np.linspace(0, np.pi, num_points)
    
    cos_vals = np.cos(x_vals)
    y_curve = [y_small + (y_large - y_small) * (j + 1) / 2 for j in cos_vals.tolist()]
    return y_curve


def interpolate_cosine(
    x: List[Union[int, float]], 
    y: List[Union[float, str]],
    num_points: int = 50
) -> Tuple[List[float], List[float]]:
    """
    在反应路径驻点间生成余弦曲线插值点
    
    包含三个部分：起始点延伸、中间点插值、末端点延伸
    
    参数:
        x: 原始x坐标列表
        y: 原始y坐标列表（可能包含空字符串）
        num_points: 每个段的插值点数
    
    返回:
        (x_new, y_smooth): 插值后的坐标序列
    
    抛出:
        ValueError: 当输入数据不足时
    """
    # 过滤有效数据
    valid_pairs = [(xi, yi) for xi, yi in zip(x, y) if yi != ""]
    if len(valid_pairs) < 2:
        raise ValueError("至少需要两个有效数据点进行插值")
    
    x_valid = [p[0] for p in valid_pairs]
    y_valid = [float(p[1]) for p in valid_pairs]
    
    x_new = []
    y_smooth = []
    
    # 1. 延伸起始点
    x_pre = np.linspace(x_valid[0] - 1, x_valid[0], num_points).tolist()
    y_pre = generate_cosine_points(y_valid[0], y_valid[1], "down", num_points)
    x_new.extend(x_pre)
    y_smooth.extend(y_pre)
    
    # 2. 中间点插值
    for i in range(len(x_valid) - 1):
        x_segment = np.linspace(x_valid[i], x_valid[i + 1], num_points).tolist()
        
        if y_valid[i] < y_valid[i + 1]:
            y_segment = generate_cosine_points(y_valid[i], y_valid[i + 1], "up", num_points)
        else:
            y_segment = generate_cosine_points(y_valid[i + 1], y_valid[i], "down", num_points)
        
        x_new.extend(x_segment)
        y_smooth.extend(y_segment)
    
    # 3. 延伸末端点
    x_post = np.linspace(x_valid[-1], x_valid[-1] + 1, num_points).tolist()
    y_post = generate_cosine_points(y_valid[-1], y_valid[-2], "up", num_points)
    x_new.extend(x_post)
    y_smooth.extend(y_post)
    
    return x_new, y_smooth


# ==================== 数据工具函数 ====================

def get_y_extremes(y_data: List[List[Union[float, str]]]) -> Tuple[float, float]:
    """
    获取y数据的最大值和最小值
    
    参数:
        y_data: 能量值数据，嵌套列表，可能包含空字符串
    
    返回:
        (y_max, y_min): 最大值和最小值
    
    抛出:
        ValueError: 当没有有效数据时
    """
    flat_list = [float(val) for sublist in y_data for val in sublist if val != ""]
    
    if not flat_list:
        raise ValueError("没有有效的能量数据")
    
    return max(flat_list), min(flat_list)


def calculate_y_axis_limits(y_data: List[List[Union[float, str]]], 
                           margin: float = 0.15) -> Tuple[float, float]:
    """
    根据数据计算Y轴显示范围
    
    参数:
        y_data: 能量值数据，嵌套列表，可能包含空字符串
        margin: 边距比例（默认15%）
    
    返回:
        (y_min, y_max): Y轴显示范围
    """
    try:
        y_max, y_min = get_y_extremes(y_data)
        
        # 添加边距
        if y_max != y_min:
            range_val = y_max - y_min
            y_min_display = y_min - range_val * margin
            y_max_display = y_max + range_val * margin
        else:
            # 如果所有数据相同，给一个默认范围
            y_min_display = y_min - 0.5
            y_max_display = y_max + 0.5
        
        return (y_min_display, y_max_display)
    except ValueError:
        # 没有有效数据时返回默认值
        return (-2.0, 1.0)


def get_row_minimums(y_data: List[List[Union[float, str]]]) -> List[float]:
    """
    获取每行的最小值（用于多自旋态数据）
    
    对转置后的数据，找出每个状态在所有路径中的最小值
    
    参数:
        y_data: 能量值数据，嵌套列表格式
    
    返回:
        每行最小值的列表
    """
    y_transposed = np.array(y_data).T.tolist()
    row_mins = []
    
    for row in y_transposed:
        valid_values = [float(val) for val in row if val != ""]
        if valid_values:
            row_mins.append(min(valid_values))
    
    return row_mins


# ==================== 数据加载函数 ====================

def parse_color(color_string: str) -> List[float]:
    """
    解析颜色字符串
    
    参数:
        color_string: RGB格式字符串，如 "0.8,0.2,0.2"
    
    返回:
        RGB颜色值列表
    
    抛出:
        ValueError: 当格式无效时
    """
    try:
        parts = color_string.split(',')
        if len(parts) != 3:
            raise ValueError(f"颜色格式应为 'R,G,B'，得到: {color_string}")
        return [float(p.strip()) for p in parts]
    except Exception as e:
        raise ValueError(f"无法解析颜色 '{color_string}': {e}")


def load_csv_data(filename: str) -> ReactionData:
    """
    从CSV文件加载反应路径数据
    
    CSV文件结构约定：
    - 第1行: 路径名称/图例标签（第1列是'index'，后续是路径名）
    - 第2行: 颜色配置（第1列是'color'，后续是R,G,B值，如'0.8,0.2,0.2'）
    - 第3行起: 数据（第1列为状态名称，后续列为各路径的能量值，空值用空字符串表示）
    
    注：图片标题、Y轴标题等在 PlotConfig 类中配置，不再从数据文件读取
    
    参数:
        filename: CSV文件路径
    
    返回:
        ReactionData对象
    
    抛出:
        FileNotFoundError: 文件不存在
        ValueError: 数据格式错误
    """
    logger.info(f"正在加载数据文件: {filename}...")
    
    try:
        with open(filename, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            rows = list(reader)
    except FileNotFoundError:
        raise FileNotFoundError(f"找不到文件: {filename}")
    except Exception as e:
        raise ValueError(f"无法读取CSV文件: {e}")
    
    # 检查基本结构（至少需要3行：路径名、颜色、至少1行数据）
    if len(rows) < 3:
        raise ValueError(f"CSV文件行数不足(需要至少3行，实际{len(rows)}行)")
    
    # 读取元数据
    try:
        path_labels = rows[0][1:]  # 第1行，从第2列开始
        color_strings = rows[1][1:]  # 第2行，从第2列开始
        
        # 读取状态名称和数据
        x_labels = []
        y_values_rows = []
        for row in rows[2:]:
            if row and row[0]:  # 确保行不为空且第1列有值
                x_labels.append(row[0])
                y_values_rows.append(row[1:])
    except IndexError as e:
        raise ValueError(f"CSV文件结构错误: {e}")
    
    # 解析颜色
    colors = [parse_color(cs) for cs in color_strings]
    
    # 生成x轴坐标
    x_coords = list(range(1, len(x_labels) + 1))
    
    # 处理能量值数据（将空字符串保留，其他转换为float）
    num_paths = len(path_labels)
    y_values = []
    
    for i in range(num_paths):
        col_idx = i
        if col_idx >= len(color_strings):
            raise ValueError(f"路径{i+1}的数据列不存在")
        
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
    
    # 计算每行最小值
    row_minimums = get_row_minimums(y_values)
    
    # 创建数据对象
    data = ReactionData(
        path_labels=path_labels,
        x_labels=x_labels,
        colors=colors,
        x_coords=x_coords,
        y_values=y_values,
        row_minimums=row_minimums
    )
    
    # 验证数据
    data.validate()
    
    logger.info(f"  成功加载 {num_paths} 条路径，{len(x_labels)} 个状态")
    return data


def load_csv_data_from_string(csv_string: str) -> Tuple[ReactionData, List[List[Union[float, str]]]]:
    """
    从CSV字符串加载反应路径数据（用于内置模板）
    
    参数:
        csv_string: CSV格式的字符串
    
    返回:
        (ReactionData对象, y_values原始数据)
    """
    lines = csv_string.strip().split('\n')
    reader = csv.reader(lines)
    rows = list(reader)
    
    # 检查基本结构
    if len(rows) < 3:
        raise ValueError(f"CSV数据行数不足(需要至少3行，实际{len(rows)}行)")
    
    # 读取元数据
    path_labels = rows[0][1:]
    color_strings = rows[1][1:]
    
    # 读取状态标签和能量数据
    x_labels = []
    y_values_rows = []
    for row in rows[2:]:
        if row and row[0]:
            x_labels.append(row[0])
            y_values_rows.append(row[1:])
    
    # 解析颜色
    colors = [parse_color(cs) for cs in color_strings]
    
    # 生成x坐标（1, 2, 3, ...）
    x_coords = list(range(1, len(x_labels) + 1))
    
    # 构建y_values（按路径组织）
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
    
    # 计算每行最小值
    row_minimums = get_row_minimums(y_values)
    
    # 创建数据对象
    data = ReactionData(
        path_labels=path_labels,
        x_labels=x_labels,
        colors=colors,
        x_coords=x_coords,
        y_values=y_values,
        row_minimums=row_minimums
    )
    
    # 验证数据
    data.validate()
    
    logger.info(f"数据验证通过: {num_paths}条路径, {len(x_labels)}个状态")
    logger.info(f"  成功加载 {num_paths} 条路径，{len(x_labels)} 个状态")
    return data, y_values


# ==================== 绘图组件函数 ====================

def draw_segment_lines(
    y: List[Union[float, str]], 
    color: List[float], 
    config: PlotConfig
) -> None:
    """
    绘制分段实线
    
    参数:
        y: y坐标列表（可能包含空字符串）
        color: RGB颜色值
        config: 绘图配置
    """
    x_doubled = []
    y_doubled = []
    
    for i, yi in enumerate(y):
        if yi != "":
            x_doubled.extend([2 * i + 1, 2 * i + 2])
            y_doubled.extend([yi, yi])
    
    for i in range(0, len(y_doubled), 2):
        plt.plot(
            [x_doubled[i], x_doubled[i+1]], 
            [y_doubled[i], y_doubled[i+1]], 
            linestyle='-', 
            linewidth=config.line_width_segment, 
            color=color
        )


def draw_line_curve(
    y_values: List[Union[float, str]], 
    x_labels: List[str], 
    color: List[float],
    path_label: Optional[str], 
    show_text: bool, 
    config: PlotConfig
) -> List[int]:
    """
    绘制带平滑曲线的能垒图
    
    参数:
        y_values: 该路径的能量值列表
        x_labels: 状态名称列表
        color: RGB颜色值
        path_label: 路径标签（用于图例，None则不显示）
        show_text: 是否显示能量值文本
        config: 绘图配置
    
    返回:
        x_tick_positions: x轴刻度位置
    """
    x_positions = [i * 2 + 2 for i in range(len(y_values))]
    
    # 数据预处理
    x_processed = []
    y_processed = []
    
    for i, (y_val, label) in enumerate(zip(y_values, x_labels)):
        if y_val == "":
            continue
        
        is_ts = re.match(r"^TS", label) is not None
        
        if is_ts:
            y_processed.append(float(y_val))
            x_processed.append(x_positions[i])
        else:
            y_processed.extend([float(y_val), float(y_val)])
            x_processed.extend([x_positions[i] - 0.5, x_positions[i] + 0.5])
    
    if len(x_processed) < 2:
        logger.warning(f"路径 '{path_label}' 的有效数据点不足，跳过曲线绘制")
        return x_positions
    
    # 生成平滑曲线
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
    
    # 绘制曲线
    label = path_label if path_label else None
    plt.plot(x_smooth, y_smooth, linestyle='-', 
             linewidth=config.line_width_curve, color=color, label=label)
    
    # 添加能量值文本标签
    if show_text:
        for i, y_val in enumerate(y_values):
            if y_val != "":
                x_pos = x_positions[i] + config.label_offset_x_curve
                y_pos = float(y_val) + config.label_offset_y_curve
                plt.text(x_pos, y_pos,
                        f"{float(y_val):.2f}", 
                        fontsize=config.font_size_energy_label, 
                        color=color,
                        ha=config.label_ha_curve)
    
    return x_positions


def draw_scatter_points(
    x_positions: List[float], 
    y_data: List[List[Union[float, str]]], 
    colors: List[List[float]], 
    path_labels: List[str], 
    show_text: bool, 
    config: PlotConfig,
    style: str = 'state'
) -> None:
    """
    绘制散点图
    
    参数:
        x_positions: x轴位置列表
        y_data: 能量值数据（嵌套列表）
        colors: 颜色列表
        path_labels: 路径标签列表
        show_text: 是否显示能量值
        config: 绘图配置
        style: 'curve' 或 'state'，控制文本标签位置
    """
    for i, (y_path, color, label) in enumerate(zip(y_data, colors, path_labels)):
        x_valid = []
        y_valid = []
        
        for j, (x_pos, y_val) in enumerate(zip(x_positions, y_path)):
            if y_val != "":
                x_valid.append(x_pos)
                y_valid.append(y_val)
                
                if show_text:
                    if style == 'curve':
                        plt.text(x_pos - 0.3, float(y_val) + 0.06,
                                f"{float(y_val):.2f}", 
                                fontsize=config.font_size_energy_label, color=color)
                    else:
                        plt.text(x_pos + 0.5, float(y_val) + 0.1,
                                f"{float(y_val):.2f}", 
                                fontsize=config.font_size_energy_label, 
                                color=color, ha='right')
        
        plt.scatter(x_valid, y_valid, linewidth=6, color=color,
                   label=label, marker='_', s=1200)


# ==================== 样式应用函数 ====================

def apply_common_style(
    data: ReactionData, 
    x_positions: List[float], 
    config: PlotConfig,
    show_title: bool = True
) -> None:
    """
    应用通用的图形样式设置
    
    参数:
        data: 反应数据
        x_positions: X轴刻度位置
        config: 绘图配置
        show_title: 是否显示图片标题
    """
    # 设置图片标题
    if show_title and config.show_title and config.title_text:
        plt.title(config.title_text, 
                  fontsize=config.font_size_title, 
                  fontweight=config.title_fontweight, 
                  pad=config.title_pad)
    
    # 设置刻度方向
    plt.gca().tick_params(axis='both', direction='in')
    plt.tick_params(axis='x', top=True, bottom=True,
                   labeltop=False, labelbottom=True)
    
    # 设置Y轴刻度格式
    plt.gca().yaxis.set_major_formatter(ticker.FormatStrFormatter('%.1f'))
    
    # 设置Y轴范围
    plt.ylim(config.y_axis_limits)
    plt.yticks(fontsize=config.font_size_axis_tick)
    
    # 设置X轴标题
    if config.show_x_title and config.x_title_text:
        plt.xlabel(config.x_title_text, fontsize=config.font_size_axis_title, fontweight=config.x_title_fontweight)
    
    # 设置Y轴标题
    if config.show_y_title and config.y_title_text:
        plt.ylabel(config.y_title_text, fontsize=config.font_size_axis_title, fontweight=config.y_title_fontweight)
    
    # 设置X轴刻度
    plt.xticks(x_positions, data.x_labels, fontsize=config.font_size_axis_tick)
    
    # 调整布局
    plt.tight_layout()
    
    # 设置边框线宽
    ax = plt.gca()
    for spine in ['bottom', 'top', 'right', 'left']:
        ax.spines[spine].set_linewidth(config.line_width_frame)
    
    ax.tick_params(axis='both', width=1, length=6, colors='black')


# ==================== 主绘图函数 ====================

def plot_curve_style(
    data: ReactionData, 
    show_text: bool, 
    config: PlotConfig
) -> str:
    """
    生成横线+平滑曲线风格的能垒图
    
    参数:
        data: 反应数据
        show_text: 是否显示能量值文本
        config: 绘图配置
    
    返回:
        输出文件路径
    """
    plt.figure(figsize=config.figure_size, dpi=config.dpi)
    
    x_positions = None
    for y_path, color, label in zip(data.y_values, data.colors, data.path_labels):
        x_positions = draw_line_curve(y_path, data.x_labels, color,
                                      label, show_text, config)
    
    if x_positions:
        apply_common_style(data, x_positions, config, show_title=True)
    
    # 添加图例（仅在curve.png中显示）
    if config.show_legend:
        legend_kwargs = {
            'loc': config.legend_loc,
            'fontsize': config.font_size_legend,
            'frameon': config.legend_frameon,
        }
        if config.legend_bbox_to_anchor is not None:
            legend_kwargs['bbox_to_anchor'] = config.legend_bbox_to_anchor
        plt.legend(**legend_kwargs)
    
    plt.savefig(config.output_curve)
    plt.close()
    
    return config.output_curve


def plot_state_style(
    data: ReactionData, 
    show_text: bool, 
    config: PlotConfig
) -> str:
    """
    生成分段实线+散点风格的能垒图（v2版本）
    
    新增功能：
    - 可选择显示图例
    - 可选择显示能量值标签
    - 可选择用虚线连接台阶
    - 使用adjustText优化标签位置（防止重叠）
    
    参数:
        data: 反应数据
        show_text: 是否显示能量值文本（传入的参数，实际使用config.show_energy_labels_state）
        config: 绘图配置
    
    返回:
        输出文件路径
    """
    plt.figure(figsize=config.figure_size, dpi=config.dpi)
    
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
            plt.plot(
                [x_doubled[i], x_doubled[i+1]], 
                [y_doubled[i], y_doubled[i+1]], 
                linestyle='-', 
                linewidth=config.line_width_segment, 
                color=color
            )
        
        # 收集有效数据点用于散点和连接
        # 记录每个台阶的头部(左端)、中部(散点位置)、尾部(右端)坐标
        step_positions = []  # (头部x, 中部x, 尾部x, y值)
        for i, (x_pos, y_val) in enumerate(zip(x_scatter_positions, y_path)):
            if y_val != "":
                head_x = 2 * i + 1      # 台阶左端（头部）
                tail_x = 2 * i + 2      # 台阶右端（尾部）
                mid_x = x_pos           # 台阶中部（散点位置）
                step_positions.append((head_x, mid_x, tail_x, float(y_val)))
                
                # 显示能量值标签（在中部位置显示）
                if config.show_energy_labels_state:
                    x_label_pos = mid_x + config.label_offset_x_state
                    y_label_pos = float(y_val) + config.label_offset_y_state
                    plt.text(x_label_pos, y_label_pos,
                            f"{float(y_val):.2f}", 
                            fontsize=config.font_size_energy_label, 
                            color=color, 
                            ha=config.label_ha_state)
        
        # 用虚线连接台阶：前一个台阶的尾部连接当前台阶的头部
        if config.connect_steps and len(step_positions) >= 2:
            for i in range(len(step_positions) - 1):
                # 前一个台阶的尾部
                prev_tail_x = step_positions[i][2]
                prev_y = step_positions[i][3]
                # 当前台阶的头部
                curr_head_x = step_positions[i+1][0]
                curr_y = step_positions[i+1][3]
                
                plt.plot(
                    [prev_tail_x, curr_head_x], 
                    [prev_y, curr_y], 
                    linestyle=config.line_style_connector, 
                    linewidth=config.line_width_connector, 
                    color=color,
                    alpha=0.6  # 虚线稍微透明
                )
        
        # 绘制散点（在中部位置，用于图例）
        x_scatter = [pos[1] for pos in step_positions]
        y_scatter = [pos[3] for pos in step_positions]
        plt.scatter(x_scatter, y_scatter, linewidth=6, color=color,
                   label=label if config.show_legend_state else None, 
                   marker='_', s=1200)
    
    # 设置X轴刻度位置
    x_tick_positions = [x * 2 - 0.5 for x in data.x_coords]
    
    apply_common_style(data, x_tick_positions, config, show_title=True)
    
    # 添加图例
    if config.show_legend_state:
        legend_kwargs = {
            'loc': config.legend_loc,
            'fontsize': config.font_size_legend,
            'frameon': config.legend_frameon,
        }
        if config.legend_bbox_to_anchor is not None:
            legend_kwargs['bbox_to_anchor'] = config.legend_bbox_to_anchor
        plt.legend(**legend_kwargs)
    
    plt.savefig(config.output_state)
    plt.close()
    
    return config.output_state


# ==================== 主入口 ====================

# ==================== 内置数据模板 ====================
BUILT_IN_TEMPLATE = """index,Model A,Model B,Model C
color,"0.5, 0.6, 0.7","0.8, 0.4, 0.3","0.5, 0.6, 0.3"
gas,0,0,0
ads.,-0.5,-1,-1.5
TS1,0.2,-0.1,-0.4
state,-0.4,-0.8,-1.2
TS2,0.1,-0.1,-0.3
prod.,-0.6,-1.1,-1.6"""


def parse_arguments(args: List[str]) -> Optional[str]:
    """
    解析命令行参数
    
    参数:
        args: 命令行参数列表
    
    返回:
        数据文件路径，如果未提供则返回None（将使用内置模板）
    """
    if len(args) < 2:
        # 无参数时使用内置模板
        return None
    
    data_file = args[1]
    return data_file


def main() -> int:
    """
    脚本入口函数
    
    返回:
        退出码 (0表示成功，1表示失败)
    """
    try:
        # 解析参数
        data_file = parse_arguments(sys.argv)
        
        # 加载数据（使用内置模板或文件）
        if data_file is None:
            logger.info("未提供数据文件，使用内置示例模板...")
            data, _ = load_csv_data_from_string(BUILT_IN_TEMPLATE)
        else:
            logger.info(f"正在加载数据文件: {data_file}...")
            data = load_csv_data(data_file)
        
        # 创建配置（可在 PlotConfig() 中修改 show_text 默认值）
        config = PlotConfig()  # show_text 默认为 True
        show_text = config.show_energy_labels
        
        # 根据数据自动计算Y轴范围（如果启用）
        if config.auto_y_range:
            config = config._replace(
                y_axis_limits=calculate_y_axis_limits(data.y_values)
            )
            logger.info(f"自动计算Y轴范围: {config.y_axis_limits}")
        
        # 生成曲线风格图
        logger.info("正在生成 curve.png (横线+平滑曲线风格)...")
        output1 = plot_curve_style(data, show_text, config)
        logger.info(f"  [OK] {output1} 已保存")
        
        # 生成状态风格图（state.png 始终不显示数值标签）
        logger.info("正在生成 state.png (分段实线+散点风格)...")
        output2 = plot_state_style(data, False, config)
        logger.info(f"  [OK] {output2} 已保存")
        
        logger.info("\n两张图都已成功生成!")
        return 0
        
    except FileNotFoundError as e:
        logger.error(f"文件错误: {e}")
        return 1
    except ValueError as e:
        logger.error(f"数据错误: {e}")
        return 1
    except Exception as e:
        logger.error(f"未知错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
