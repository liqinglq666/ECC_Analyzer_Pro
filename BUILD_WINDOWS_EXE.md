# Windows EXE 打包与发布说明

这个项目是 PySide6 + Matplotlib 桌面程序，推荐发布为 **Windows x64 portable package**，也就是一个 zip 包。用户解压后双击里面的 `ECC Analyzer Pro.exe` 即可运行，不需要自己安装 Python。

> 说明：所谓“别人下载后任何电脑都能打开”，更准确地说是 **Windows 10/11 64 位电脑大概率可以直接运行**。如果是 macOS、Linux、32 位 Windows，或者被杀毒软件拦截，就需要对应系统单独打包或加入信任。

---

## 一、GitHub 自动打包

仓库已经加入 GitHub Actions 工作流：

```text
.github/workflows/build-windows-exe.yml
```

它会做这些事：

1. 在 GitHub 的 Windows 云端环境启动；
2. 安装 Python 3.10；
3. 安装项目依赖和 PyInstaller；
4. 运行 `python scripts/smoke_test.py`；
5. 运行 `python scripts/build_exe.py`；
6. 生成 `ECC_Analyzer_Pro_Windows_x64.zip`；
7. 把 zip 上传为 GitHub Actions artifact。

---

## 二、下载 Actions 生成的 zip

每次 push 到 `main` 或手动运行 workflow 后，GitHub 都会生成一个临时下载包。

操作步骤：

1. 打开 GitHub 仓库；
2. 点击顶部 **Actions**；
3. 选择左侧 **Build Windows EXE**；
4. 点进最新一次成功的绿色运行记录；
5. 页面底部找到 **Artifacts**；
6. 下载 `ECC_Analyzer_Pro_Windows_x64`；
7. 解压后进入文件夹，双击：

```text
ECC Analyzer Pro.exe
```

Artifacts 默认保留 30 天，适合自己测试，不适合长期对外发布。

---

## 三、正式发布到 GitHub Releases

如果希望别人长期下载，建议用 GitHub Releases。

在本地项目目录执行：

```bash
git pull origin main
git tag v0.1.0
git push origin v0.1.0
```

推送 `v0.1.0` 这种 tag 后，GitHub Actions 会自动：

1. 打包 Windows zip；
2. 创建 GitHub Release；
3. 把 `ECC_Analyzer_Pro_Windows_x64.zip` 挂到 Release Assets 里。

之后别人就可以在仓库首页右侧或顶部的 **Releases** 中下载。

---

## 四、本地打包方式

如果要在自己的 Windows 电脑本地打包：

```bash
cd /d E:\MTS\ECC_Analyzer_Pro
conda activate ecc_sim
python -m pip install -r requirements.txt pyinstaller
python scripts\build_exe.py
```

打包完成后会生成：

```text
dist/ECC_Analyzer_Pro/
├── ECC Analyzer Pro.exe
└── _internal/
```

分享时不要只发 exe，要把整个 `ECC_Analyzer_Pro` 文件夹压缩成 zip 再发。

---

## 五、为什么不默认做单文件 onefile

PyInstaller 支持单文件：

```bash
pyinstaller --onefile main.py
```

但这个项目包含 PySide6、Matplotlib、SciPy、Pandas 等依赖。单文件模式通常会有几个问题：

- 首次启动慢；
- Qt 插件更容易找不到；
- Matplotlib 字体和 backend 数据更容易丢；
- 杀毒软件更容易误报；
- 出错时更难定位。

所以当前推荐 `onedir` 方案。虽然 zip 大一些，但对科研工具来说更稳。

---

## 六、常见问题

### 1. 双击 exe 没反应

可能是程序启动时报错但窗口没有弹出来。建议先在命令行中运行：

```cmd
cd 解压后的文件夹
"ECC Analyzer Pro.exe"
```

如果有报错，把完整报错复制出来再排查。

### 2. Windows 提示未知发布者

这是因为 exe 没有代码签名。个人开源项目常见。点击“更多信息 → 仍要运行”即可。

如果后期要给很多人用，可以考虑购买代码签名证书，但这个成本比较高。

### 3. 杀毒软件误报

PyInstaller 打包的程序偶尔会被误报，尤其是单文件 onefile 更常见。当前使用 onedir 已经能降低风险。

### 4. 下载后提示缺少 DLL

请确认用户解压的是整个 zip 包，而不是只把 exe 单独拿出来运行。`_internal` 文件夹必须和 exe 放在一起。

---

## 七、推荐发布口径

可以在 Release 说明里这样写：

```text
Windows 版为 portable package。
下载 ECC_Analyzer_Pro_Windows_x64.zip 后解压，双击 ECC Analyzer Pro.exe 即可运行。
无需安装 Python。
如 Windows Defender 提示未知发布者，请选择“更多信息 → 仍要运行”。
```
