# macOS 使用说明

这个文件夹已经排除了 Windows 虚拟环境和真实 API Key，可直接压缩后发送给 Mac 用户。

## 第一次使用

1. 安装 Python 3.11 或 Python 3.12：<https://www.python.org/downloads/macos/>
2. 解压本文件夹。
3. 打开“终端”，输入 `cd `（注意末尾空格），把解压后的文件夹拖进终端窗口，然后按回车。
4. 执行：

   ```bash
   chmod +x setup.sh run.sh "Start Mac.command"
   ./setup.sh
   ```

5. 打开新生成的 `.env` 文件，将内容改为：

   ```env
   ZHIPU_API_KEY=你的智谱API密钥
   ```

6. 执行 `./run.sh`，或以后直接双击 `Start Mac.command`。

浏览器地址为：<http://localhost:8650>

## 注意事项

- 第一次安装必须联网。
- 不要从 Windows 电脑复制 `venv` 文件夹；Mac 会自行创建兼容环境。
- `.env` 包含 API Key，不要公开转发。
- Apple Silicon 和 Intel Mac 使用相同的安装步骤。
