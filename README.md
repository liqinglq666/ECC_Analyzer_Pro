# 🏗️ ECC Analyzer Pro - Scientific Edition

<div align="center">

![Language](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python)
![Framework](https://img.shields.io/badge/GUI-PySide6%20%7C%20Matplotlib-green?logo=qt)
![Method](https://img.shields.io/badge/Algorithm-Dual--Criterion%20Strategy-purple)
![Physics](https://img.shields.io/badge/Physics-Informed-orange)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

An automated, physics-informed scientific tool for characterizing tensile & compressive properties of Engineered Cementitious Composites (ECC/SHCC).

专为 ECC/SHCC 材料研发的自动化科研分析工具——拒绝暴力拟合，回归物理本真。

[Installation](#-installation) • [Scientific Core](#-scientific-core) • [Data Protocol](#-data-protocol) • [Citation](#-citation)

</div>

---

## 💡 设计哲学 (Design Philosophy)

> ECC Analyzer Pro 不试图讨好所有材料，也不假装 ECC 是“近似线弹性”的乖孩子。相反，它非常直接地承认一个事实：ECC 从第一步加载开始，就是非线性的。

既然如此，就不该用一个“唯一模量”去强行解释它，也不该用肉眼去猜测“哪一点是开裂点”。本软件的核心使命，是将 “经验判断” 转化为 “可复现的数学判据”。

---

## 🖥️ 界面概览 (Interface Overview)

软件界面采用 "Data-Vis Split" (左数据-右视觉) 的现代布局，专为高效率科研工作流设计。

![img.png](assets/screenshots/img.png)

![img_1.png](assets/screenshots/img_1.png)

### 1️⃣ 全局控制 (Global Control)
* Mode Selector: `Tensile` / `Compressive` 双模式一键切换。
* View Switcher: `Basic` (工程指标) / `Advanced` (科研指标) 视图切换。

### 2️⃣ 智能数据面板 (Smart Data Panel)
* Drag & Drop: 支持批量拖拽 `.xlsx` / `.csv` 文件。
* Smart Selection: 交互式勾选，支持 Shift 连选，实时显示选中样本统计值。

### 3️⃣ 可视化引擎 (Visualization Engine)
* Dual Canvas: 左侧 `Statistics` (带误差棒的柱状图)，右侧 `Curves` (高质量曲线叠加)。
* Interaction: 鼠标悬停显示精确坐标，支持右键一键复制图表到论文。

### 4️⃣ 绘图调优 (Visual Tuning)
* 即时渲染: 实时调节配色 (Scientific Theme) 与线宽 (Line Width)。
* 导出: 一键保存 300 DPI 高清图片 (`.png`, `.pdf`, `.svg`)。

---

## 🔬 核心算法：物理定义的重构 (Scientific Core)

超越传统唯象拟合的局限，本工具搭载了 **物理驱动的本构解析引擎 (Physics-Informed Constitutive Engine)**。

### 1. 双模量策略 (Dual-Modulus Strategy)
* **初始弹性模量 ($E_{init}$)**：对平滑后的应力-应变曲线进行数值微分，选取加载初期最大的 10% 切线模量进行统计平均。真实反映未损伤基体刚度。
* **有效弹性模量 ($E_{eff}$)**：在用户可配的应力区间（默认 10%–40% 峰值）内，采用线性回归计算割线响应。作为工程设计的刚度输入。

### 2. 首裂判据：主辅耦合机制 (Dual-Criterion Strategy)
* **主判据 (Master) - 线性偏离**：当实验应力显著偏离 $E_{eff}$ 预测轨迹时触发预警：
  
  $$\sigma_{theory} - \sigma_{exp} > \delta_{tol}$$

* **辅判据 (Slave) - 刚度衰减**：仅当实时切线模量发生实质性退化时确认开裂：
  
  $$E_{tan} < 0.85 \cdot E_{init}$$

### 3. 多缝机制与能量量化 (Ductility & Energy)
* **多缝发展区间 ($\Delta \varepsilon_{SH}$)**：$\Delta \varepsilon_{SH} = \varepsilon_u - \varepsilon_{cr}$，直接量化材料“能稳定开多少裂缝”。
* **平台稳定性系数 ($CV_{\sigma}$)**：计算硬化段应力的变异系数。$CV$ 越小，表明多缝开展过程越平稳。
* **断裂能 ($G_F$)**：基于 Simpson 积分和标距转换：
  
  $$G_F = \int \sigma d\varepsilon \times L_0$$

---

## 📖 数据格式规范 (Data Protocol)

⚠️ 程序核心逻辑：基于“列对 (Column Pairs)”或“行式 (Row-Based)”读取数据。

### 1. 抗拉模式 (Tensile Mode)
每两个列为一组（Strain + Stress），程序会自动忽略空列。

| A (Sample 1) | B | C (Sample 2) | D | ... |
| :--- | :--- | :--- | :--- | :--- |
| FSC-AIR-1 | *(Empty)* | FSC-AIR-2 | *(Empty)* | ... |
| *Strain (%)* | *Stress (MPa)* | *Strain (%)* | *Stress (MPa)* | ... |
| 0.001 | 0.05 | 0.002 | 0.04 | ... |
| 0.005 | 0.12 | 0.006 | 0.11 | ... |

* Row 1: 样品名称。
* **Row 3+**: 数据。应变支持小数(0.01)或百分数(1.0)，程序会自动归一化。

### 2. 抗压模式 (Compressive Mode)
支持两种数据格式，程序会自动识别：

#### A. 全曲线格式 (Full Curve Data)
同抗拉模式，每两列为一组，用于绘制应力-应变曲线。

#### B. 行式汇总格式 (Row-Based Summary List)
适用于批量录入抗压强度峰值。每一行代表一组样品。

| A (Group Name) | B (Val 1) | C (Val 2) | D (Val 3) | ... |
| :--- | :--- | :--- | :--- | :--- |
| ECC-M45 | 45.2 | 46.8 | 44.9 | ... |
| ECC-PVA | 38.5 | 39.1 | *(Empty)* | ... |

* Column A: 样品组名称。
* **Columns B+**: 该组样品对应的抗压强度值。支持每组样本数量不一致。

---
## 🚀 下载与安装 (Download)

### 1. 下载运行 (Windows - 推荐)
您可以直接从 **[Latest Release (v1.0)](https://github.com/liqinglq666/ECC_Analyzer_Pro/releases/tag/v1.0)** 页面下载编译好的 `ECC_Analyzer_Pro.exe`。
* **开箱即用**：无需安装 Python 环境，双击即可运行。
* **注意**：由于未进行数字签名，Windows Defender 可能会弹出安全提醒，请点击“更多信息”并选择“仍要运行”。

### 2. 数据准备 (Data Preparation)

本程序支持 **单轴拉伸 (Tensile)** 与 **抗压(Compression)** 两种试验数据的自动解析。为了确保导入成功，推荐采用“模板替换”法：

1. **选择并下载模板**：
   前往 [raw_data 示例目录](https://github.com/liqinglq666/ECC_Analyzer_Pro/tree/main/raw_data) 下载对应的 Demo 文件：
   * **拉伸试验**：使用 `demo_tensile.xlsx`
   * **抗压试验**：使用 `demo_compression.xlsx`

2. **排版数据**：
   将您实验所得的原始数据（应力、应变、荷载等）直接粘贴到对应模板的列中。
   * **注意**：请务必保持模板首行的**列名关键词**（如 `Stress`, `Strain`）不变。

3. **一键分析**：
   运行 [ECC_Analyzer_Pro.exe](https://github.com/liqinglq666/liqinglq666/ECC_Analyzer_Pro/releases/tag/v1.0)，在软件界面选择对应的试验类型并导入您修改后的文件即可。

> **💡 小建议**：
> 如果您的原始数据列名与模板不一致，只需在 Excel 中将表头修改为与 Demo 文件一致，程序即可自动识别，无需手动调整数据顺序。
---

## 📊 指标解读 (Metrics Explained)

### 🧶 Tensile Metrics (抗拉指标)

| Column Name | Symbol | Definition & Significance |
| :--- | :---: | :--- |
| Effective Modulus | $E_{eff}$ | 工程刚度。区间回归得到的割线模量，用于结构设计。 |
| First Crack Strength | $\sigma_{cr}$ | **初裂强度**。线性段结束点，标志多缝开展起始。 |
| Ultimate Strength | $\sigma_{u}$ | 极限强度。材料能承受的最大拉应力。 |
| Ultimate Strain | $\varepsilon_{tu}$ | **极限应变**。峰值应力对应的应变值。 |
| Hardening Capacity | $\Delta\varepsilon_{sh}$ | 应变硬化容量 ($\varepsilon_{u} - \varepsilon_{cr}$)。评价 ECC 性能的核心指标。 |
| Fracture Energy | $G_F$ | **断裂能**。单位裂缝面积消耗的能量，用于数值模拟标定。 |
| Plateau Stability | $CV_{\sigma}$ | 平台稳定性。数值越低，裂缝宽度控制越均匀。 |

### 🧱 Compressive Metrics (抗压指标)

| Column Name | Symbol | Definition & Significance |
| :--- | :---: | :--- |
| Mean Strength | $\sigma_{mean}$ | **平均强度**。材料抗压承载力的核心指标。 |
| Standard Deviation | $SD$ | **标准差**。量化强度的绝对离散程度。 |
| COV (%) | $CV$ | **变异系数**。表征相对稳定性。通常要求水泥基材料 $CV < 15\%$。 |

> 💡 **Tips**:
> * High Strength, Low COV: 理想结果，表明纤维分散均匀。
> * **High Strength, High COV**: 可能存在离群值或振捣不均，建议检查原始数据。

---
## 🚀 快速开始 (Quick Start)

###  下载运行 (Windows)
您可以直接从 [Releases](https://github.com/liqinglq666/ECC_Analyzer_Pro/releases) 页面下载编译好的 `ECC_Analyzer_Pro.exe`。
* **无需安装 Python 环境**，双击即可运行。
* *注意：如遇系统拦截，请选择“仍要运行”。*

---

## 🛠️ 安装与使用 (Installation)

### 环境要求
* Python 3.8+
* 依赖库：`PySide6`, `matplotlib`, `pandas`, `numpy`, `scipy`, `openpyxl`, `mplcursors`

### 快速开始

1.  **克隆仓库**
    ```bash
    git clone [https://github.com/liqinglq666/ECC_Analyzer_Pro.git](https://github.com/liqinglq666/ECC_Analyzer_Pro.git)
    cd ECC_Analyzer_Pro
    ```

2.  **安装依赖**
    ```bash
    pip install -r requirements.txt
    ```

3.  **启动程序**
    ```bash
    python main.py
    ```

---

## ⚙️ 参数配置 (Configuration)

点击界面上的 `⚙️ Settings` 可调整核心物理参数：

| 参数 | 默认值 | 物理意义与建议 |
| :--- | :--- | :--- |
| **Gauge Length** | 80.0 mm | 至关重要。直接影响断裂能 ($G_F$) 计算，请按实测填写。 |
| Crack Tolerance | 0.05 MPa | 首裂主判据。数值越小越敏感；若数据噪点多，建议调大。 |
| Ultimate Ratio | 0.85 | 极限状态。当峰后应力降至峰值的 85% 时，视为破坏。 |
| Smooth Window | 11 | 平滑窗口。必须为奇数。数值越大曲线越平滑，但可能削峰。 |

---

## 🖊️ 引用 (Citation)

本项目由 Sun Yat-sen University (SYSU) 的 Li Qing 开发。

如果您在学术研究中使用了本软件或其“双判据主从制算法”，请引用：

> Li, Q. (2026). *ECC Analyzer Pro: An automated scientific tool for characterizing tensile properties of Engineered Cementitious Composites based on dual-criterion strategy*. [Software]. Sun Yat-sen University. Available at: https://github.com/liqinglq666/ECC_Analyzer_Pro

```bibtex
@software{ECC_Analyzer_Pro,
  author = {Li, Qing},
  title = {ECC Analyzer Pro: An automated scientific tool for characterizing tensile properties of Engineered Cementitious Composites},
  year = {2026},
  publisher = {GitHub},
  journal = {GitHub repository},
  url = {[https://github.com/liqinglq666/ECC_Analyzer_Pro](https://github.com/liqinglq666/ECC_Analyzer_Pro)}
}