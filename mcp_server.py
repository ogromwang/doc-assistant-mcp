#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
个性化文档助手 MCP 服务器
可以查询指定电脑路径的文档内容
"""

import os
import sys
import logging
import argparse
import asyncio
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import mimetypes
import re

try:
    from langchain_community.document_loaders import (
        TextLoader, 
        PyPDFLoader, 
        CSVLoader, 
        UnstructuredExcelLoader,
        Docx2txtLoader,
        UnstructuredMarkdownLoader
    )
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_community.vectorstores import FAISS
    from langchain_community.embeddings import HuggingFaceEmbeddings
except ImportError:
    print("请安装所需依赖: pip install langchain langchain-community faiss-cpu pypdf transformers unstructured docx2txt pandas openpyxl mcp")
    sys.exit(1)

try:
    from mcp.server import Server
    from mcp.types import Resource, Tool, TextContent
    from pydantic import AnyUrl
except ImportError as e:
    print(e)
    sys.exit(1)

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("文档助手")

class DocumentAssistant:
    """个性化文档助手，用于查询本地文档"""
    
    def __init__(self, document_paths: List[str], embedding_model_name: str = "moka-ai/m3e-base"):
        """
        初始化文档助手
        
        Args:
            document_paths: 文档路径列表
            embedding_model_name: 嵌入模型名称
        """
        self.document_paths = document_paths
        self.embedding_model_name = embedding_model_name
        self.documents = []
        self.vector_store = None
        self.retriever = None
        
        # 加载文档
        self._load_documents()
        
        # 初始化向量数据库
        self._initialize_vector_store()
    
    def _load_documents(self):
        """加载指定路径的所有文档"""
        logger.info(f"开始加载文档，路径: {self.document_paths}")
        
        for doc_path in self.document_paths:
            path = Path(doc_path)
            
            if not path.exists():
                logger.warning(f"路径不存在: {doc_path}")
                continue
            
            if path.is_file():
                docs = self._load_single_file(path)
                if docs:
                    self.documents.extend(docs)
            elif path.is_dir():
                for file_path in path.glob("**/*"):
                    if file_path.is_file():
                        docs = self._load_single_file(file_path)
                        if docs:
                            self.documents.extend(docs)
        
        # 切分文档
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
            length_function=len,
        )
        
        self.documents = text_splitter.split_documents(self.documents)
        logger.info(f"文档加载完成，总共加载了 {len(self.documents)} 个文档片段")
    
    def _load_single_file(self, file_path: Path):
        """根据文件类型加载单个文件"""
        try:
            file_type = mimetypes.guess_type(file_path)[0]
            
            if file_path.suffix.lower() == '.pdf':
                loader = PyPDFLoader(str(file_path))
                return loader.load()
            
            elif file_path.suffix.lower() in ['.txt', '.log', '.py', '.java', '.js', '.html', '.css', '.json']:
                loader = TextLoader(str(file_path), encoding='utf-8')
                return loader.load()
            
            elif file_path.suffix.lower() == '.csv':
                loader = CSVLoader(str(file_path))
                return loader.load()
            
            elif file_path.suffix.lower() in ['.xlsx', '.xls']:
                loader = UnstructuredExcelLoader(str(file_path))
                return loader.load()
            
            elif file_path.suffix.lower() in ['.docx', '.doc']:
                loader = Docx2txtLoader(str(file_path))
                return loader.load()
            
            elif file_path.suffix.lower() in ['.md', '.markdown']:
                loader = UnstructuredMarkdownLoader(str(file_path))
                return loader.load()
            
            logger.warning(f"不支持的文件类型: {file_path}")
            return []
        except Exception as e:
            logger.error(f"加载文件 {file_path} 时出错: {str(e)}")
            return []
    
    def _initialize_vector_store(self):
        """初始化向量数据库"""
        logger.info("初始化向量数据库...")
        
        # 使用HuggingFace模型进行嵌入
        embeddings = HuggingFaceEmbeddings(model_name=self.embedding_model_name)
        
        # 创建FAISS向量数据库
        self.vector_store = FAISS.from_documents(self.documents, embeddings)
        
        logger.info("向量数据库初始化完成")
        
        # 设置检索器
        self.retriever = self.vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 5}
        )
    
    def query(self, question: str) -> str:
        """
        查询文档
        
        Args:
            question: 问题
            
        Returns:
            str: 回答
        """
        if not self.retriever:
            return "检索器尚未初始化，无法回答问题"
        
        try:
            # 检索相关文档
            docs = self.retriever.get_relevant_documents(question)
            
            # 构建回答
            if not docs:
                return "未找到相关信息，请尝试其他问题"
            
            result = f"根据您的问题 '{question}'，找到以下相关内容：\n\n"
            
            for i, doc in enumerate(docs):
                result += f"文档 {i+1}:\n"
                result += f"来源: {doc.metadata.get('source', '未知来源')}\n"
                result += f"内容: {doc.page_content[:500]}...(内容可能被截断)\n\n"
            
            return result
        except Exception as e:
            logger.error(f"查询时出错: {str(e)}")
            return f"查询时出错: {str(e)}"
    
    def vectorize_directory(self, directory_path: str) -> str:
        """
        向量化指定目录中的所有文档
        
        Args:
            directory_path: 目录路径
            
        Returns:
            str: 处理结果
        """
        try:
            path = Path(directory_path)
            
            if not path.exists():
                return f"路径不存在: {directory_path}"
            
            if not path.is_dir():
                return f"指定路径不是目录: {directory_path}"
            
            # 如果该目录已经在文档路径列表中，则不重复添加
            if str(path.absolute()) in [str(Path(p).absolute()) for p in self.document_paths]:
                logger.info(f"目录 {directory_path} 已经在文档路径列表中")
            else:
                self.document_paths.append(str(path.absolute()))
            
            # 重新加载文档
            logger.info(f"开始加载目录 {directory_path} 中的文档")
            self.documents = []
            self._load_documents()
            
            # 重新初始化向量数据库
            self._initialize_vector_store()
            
            return f"成功向量化目录 {directory_path} 中的文档，总共加载了 {len(self.documents)} 个文档片段"
        except Exception as e:
            logger.error(f"向量化目录 {directory_path} 时出错: {str(e)}")
            return f"向量化目录时出错: {str(e)}"

# 全局文档助手实例
document_assistant = None

# 初始化 MCP 服务器
app = Server("document_assistant_mcp")

def get_document_paths():
    """获取命令行参数中的文档路径"""
    parser = argparse.ArgumentParser(description="个性化文档助手 MCP 服务器")
    parser.add_argument('--paths', type=str, nargs='+', default=[], help="文档路径列表")
    parser.add_argument('--embedding-model', type=str, default="moka-ai/m3e-base", help="嵌入模型名称")
    
    # 解析参数，但不退出程序（仅使用已知参数）
    args, _ = parser.parse_known_args()
    
    return args.paths, args.embedding_model

@app.list_resources()
async def list_resources() -> list[Resource]:
    """列出可用文档资源"""
    global document_assistant
    
    paths, embedding_model = get_document_paths()
    if not paths:
        logger.warning("未指定文档路径，请使用 --paths 参数指定")
        return []
    
    # 延迟初始化文档助手
    if document_assistant is None:
        document_assistant = DocumentAssistant(paths, embedding_model)
    
    resources = []
    
    # 为每个文档路径创建资源
    for doc_path in document_assistant.document_paths:
        path = Path(doc_path)
        if path.exists():
            if path.is_file():
                mime_type = mimetypes.guess_type(path)[0] or "text/plain"
                resources.append(
                    Resource(
                        uri=f"file://{path.absolute()}",
                        name=f"文件: {path.name}",
                        mimeType=mime_type,
                        description=f"文档内容: {path.name}"
                    )
                )
            elif path.is_dir():
                # 对于目录，列出所有文件作为资源
                for file_path in path.glob("**/*"):
                    if file_path.is_file():
                        mime_type = mimetypes.guess_type(file_path)[0] or "text/plain"
                        resources.append(
                            Resource(
                                uri=f"file://{file_path.absolute()}",
                                name=f"文件: {file_path.relative_to(path)}",
                                mimeType=mime_type,
                                description=f"文档内容: {file_path.relative_to(path)}"
                            )
                        )
    
    logger.info(f"列出 {len(resources)} 个资源")
    return resources

@app.read_resource()
async def read_resource(uri: AnyUrl) -> str:
    """读取文档资源内容"""
    uri_str = str(uri)
    logger.info(f"读取资源: {uri_str}")
    
    if not uri_str.startswith("file://"):
        raise ValueError(f"不支持的 URI 方案: {uri_str}")
    
    file_path = uri_str[7:]  # 移除 'file://' 前缀
    path = Path(file_path)
    
    if not path.exists() or not path.is_file():
        raise ValueError(f"文件不存在: {file_path}")
    
    try:
        # 根据文件类型读取内容
        if path.suffix.lower() == '.pdf':
            # 使用 PyPDF 读取
            from pypdf import PdfReader
            reader = PdfReader(path)
            return "\n\n".join([page.extract_text() or "" for page in reader.pages])
        else:
            # 尝试作为文本文件读取
            return path.read_text(encoding='utf-8', errors='replace')
    except Exception as e:
        logger.error(f"读取文件 {file_path} 时出错: {str(e)}")
        raise RuntimeError(f"读取文件出错: {str(e)}")

@app.list_tools()
async def list_tools() -> list[Tool]:
    """列出可用工具"""
    logger.info("列出工具...")
    return [
        Tool(
            name="query_document",
            description="查询文档内容",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "要查询的问题"
                    }
                },
                "required": ["question"]
            }
        ),
        Tool(
            name="vectorize_directory",
            description="向量化指定目录中的所有文档",
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "要向量化的目录路径"
                    }
                },
                "required": ["directory"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """执行工具调用"""
    global document_assistant
    
    logger.info(f"调用工具: {name}, 参数: {arguments}")
    
    # 延迟初始化文档助手
    if document_assistant is None:
        paths, embedding_model = get_document_paths()
        if not paths:
            return [TextContent(type="text", text="未指定文档路径，请使用 --paths 参数指定")]
        document_assistant = DocumentAssistant(paths, embedding_model)
    
    try:
        if name == "query_document":
            question = arguments.get("question")
            if not question:
                raise ValueError("必须提供问题参数")
            
            answer = document_assistant.query(question)
            return [TextContent(type="text", text=answer)]
        
        elif name == "vectorize_directory":
            directory = arguments.get("directory")
            if not directory:
                raise ValueError("必须提供目录参数")
            
            result = document_assistant.vectorize_directory(directory)
            return [TextContent(type="text", text=result)]
        
        else:
            raise ValueError(f"未知工具: {name}")
    except Exception as e:
        logger.error(f"执行工具 {name} 时出错: {str(e)}")
        return [TextContent(type="text", text=f"执行工具时出错: {str(e)}")]

async def main():
    """主函数"""
    from mcp.server.stdio import stdio_server
    
    logger.info("启动文档助手 MCP 服务器...")
    
    paths, embedding_model = get_document_paths()
    if paths:
        logger.info(f"文档路径: {paths}")
        logger.info(f"嵌入模型: {embedding_model}")
    else:
        logger.warning("未指定文档路径，请使用 --paths 参数指定")
    
    # 使用标准输入输出作为传输方式
    logger.info("文档助手 MCP 服务器启动成功")
    async with stdio_server() as (read_stream, write_stream):
        try:
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )
        except Exception as e:
            logger.error(f"服务器错误: {str(e)}", exc_info=True)
            raise

if __name__ == "__main__":
    asyncio.run(main())
