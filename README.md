# 个性化文档助手 MCP 服务器

一个基于 fastMCP 的个性化文档助手服务器，可以查询指定电脑路径的文档内容。

## 功能特点

- 支持多种文档格式：PDF、TXT、CSV、Excel、Word、Markdown 等
- 使用向量数据库进行语义检索
- 符合 MCP 协议标准
- 提供标准 MCP 服务接口

## 依赖安装

```bash
# 安装基础依赖
pip install langchain langchain-community faiss-cpu pypdf transformers unstructured docx2txt pandas openpyxl

# 安装 MCP 依赖
pip install mcp-fastmcp
```

## 使用方法

### 启动服务器

```bash
python test_mcp_server.py --paths /path/to/documents /another/path --embedding-model moka-ai/m3e-base
```

参数说明：
- `--paths`: 文档路径列表，可以是文件或目录
- `--embedding-model`: 嵌入模型名称，默认为 moka-ai/m3e-base

### 与服务器交互

该服务器支持标准的 MCP 交互协议，可以通过 MCP 客户端与其交互。

服务器提供的功能：

1. 资源列表（list_resources）：列出所有可用的文档资源
2. 读取资源（read_resource）：读取指定文档的内容
3. 工具列表（list_tools）：列出可用的工具
4. 调用工具（call_tool）：调用查询文档内容的工具

### 示例：查询文档

可以使用 MCP 客户端调用 `query_document` 工具来查询文档内容：

```python
from mcp.client import Client

async with Client() as client:
    # 连接到文档助手服务器
    await client.connect("document_assistant_mcp")
    
    # 调用查询工具
    result = await client.call_tool(
        "query_document", 
        {"question": "我想了解关于某个主题的信息"}
    )
    
    # 打印结果
    print(result[0].text)
```

## 注意事项

1. 首次加载文档时会构建向量索引，可能需要一定时间
2. 查询性能取决于文档数量和嵌入模型的性能
3. 服务器使用标准输入输出作为传输方式，适合与其他 MCP 组件集成使用

## 客户端配置
```json
{
  "mcpServers": {
    "document-assistant": {
        "command": "python",
        "args": [
          "你的 python 文件地址 如./mcp_server.py",
          "--paths",
          "你的文档路径 如/Users/Downloads",
          "--embedding-model",
          "moka-ai/m3e-base"
        ],
        "env": {}
      }

  }
}

```