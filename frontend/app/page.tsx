'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Layout,
  Menu,
  Button,
  Input,
  Card,
  Upload,
  Modal,
  Form,
  Select,
  List,
  Tag,
  Space,
  message,
  Popconfirm,
  Spin,
  Empty,
  Collapse,
  Tabs,
} from 'antd';
import {
  DatabaseOutlined,
  UploadOutlined,
  MessageOutlined,
  FileTextOutlined,
  DeleteOutlined,
  EditOutlined,
  EyeOutlined,
  SendOutlined,
  PlusOutlined,
  FilePdfOutlined,
  FileWordOutlined,
  FileExcelOutlined,
  FileMarkdownOutlined,
  FileTextOutlined as FileTxtOutlined,
  ClearOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const { Sider, Content, Header } = Layout;
const { TextArea } = Input;
const { Dragger } = Upload;

// ============================================================
//  类型定义
// ============================================================

interface Collection {
  name: string;
  total_chunks: number;
  file_count: number;
}

interface FileItem {
  file_name: string;
  chunks: number;
  size_bytes?: number;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  sources?: Array<{ content: string; file_name: string; similarity: number }>;
}

// ============================================================
//  API 调用辅助函数
// ============================================================

const API_BASE = '/api';

async function apiGet(path: string) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || '请求失败');
  }
  return res.json();
}

async function apiPost(path: string, body: any) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: body instanceof FormData ? {} : { 'Content-Type': 'application/json' },
    body: body instanceof FormData ? body : JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || '请求失败');
  }
  return res.json();
}

async function apiDelete(path: string) {
  const res = await fetch(`${API_BASE}${path}`, { method: 'DELETE' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || '请求失败');
  }
  return res.json();
}

// ============================================================
//  主页面组件
// ============================================================

export default function HomePage() {
  const [currentMenu, setCurrentMenu] = useState('qa');
  const [collections, setCollections] = useState<Collection[]>([]);
  const [selectedCollection, setSelectedCollection] = useState<string>('');

  // 刷新知识库列表
  const refreshCollections = useCallback(async () => {
    try {
      const data = await apiGet('/collections');
      setCollections(data.collections || []);
      if (!selectedCollection && data.collections?.length > 0) {
        setSelectedCollection(data.collections[0].name);
      }
    } catch {
      // 忽略错误
    }
  }, [selectedCollection]);

  useEffect(() => {
    refreshCollections();
  }, []);

  const menuItems = [
    { key: 'qa', icon: <MessageOutlined />, label: '知识问答' },
    { key: 'upload', icon: <UploadOutlined />, label: '上传文件' },
    { key: 'collections', icon: <DatabaseOutlined />, label: '知识库管理' },
    { key: 'files', icon: <FileTextOutlined />, label: '文件管理' },
  ];

  const renderContent = () => {
    switch (currentMenu) {
      case 'qa':
        return <QAPanel collection={selectedCollection} collections={collections} onCollectionChange={setSelectedCollection} />;
      case 'upload':
        return <UploadPanel collection={selectedCollection} collections={collections} onCollectionChange={setSelectedCollection} onSuccess={refreshCollections} />;
      case 'collections':
        return <CollectionsPanel collections={collections} onRefresh={refreshCollections} onSelect={setSelectedCollection} />;
      case 'files':
        return <FilesPanel collection={selectedCollection} collections={collections} onCollectionChange={setSelectedCollection} onRefresh={refreshCollections} />;
      default:
        return null;
    }
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider breakpoint="lg" collapsedWidth="0" style={{ background: '#001529' }}>
        <div className="sidebar-logo">
          <h2>DX-RAG</h2>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[currentMenu]}
          onClick={({ key }) => setCurrentMenu(key)}
          items={menuItems}
        />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', padding: '0 24px', borderBottom: '1px solid #f0f0f0' }}>
          <h1 style={{ margin: 0, fontSize: 18, lineHeight: '64px' }}>
            {menuItems.find((m) => m.key === currentMenu)?.label}
          </h1>
        </Header>
        <Content className="site-content">
          <Card className="content-card">{renderContent()}</Card>
        </Content>
      </Layout>
    </Layout>
  );
}

// ============================================================
//  知识问答面板
// ============================================================

function QAPanel({
  collection,
  collections,
  onCollectionChange,
}: {
  collection: string;
  collections: Collection[];
  onCollectionChange: (v: string) => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [topK, setTopK] = useState(5);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    const question = inputValue.trim();
    if (!question || loading) return;

    setInputValue('');
    const userMsg: ChatMessage = { role: 'user', content: question };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const history = messages.map((m) => ({ role: m.role, content: m.content }));
      const data = await apiPost('/query', {
        question,
        top_k: topK,
        collection_name: collection || undefined,
        history,
      });

      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: data.answer,
        sources: data.sources,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      message.error(err.message || '问答请求失败');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.ctrlKey && e.key === 'Enter') {
      handleSend();
    }
  };

  const handleClear = () => {
    setMessages([]);
  };

  const getFileIcon = (fileName: string) => {
    const ext = fileName.split('.').pop()?.toLowerCase();
    switch (ext) {
      case 'pdf': return <FilePdfOutlined style={{ color: '#ff4d4f' }} />;
      case 'docx': return <FileWordOutlined style={{ color: '#1890ff' }} />;
      case 'xlsx': case 'xlsm': return <FileExcelOutlined style={{ color: '#52c41a' }} />;
      case 'md': return <FileMarkdownOutlined style={{ color: '#722ed1' }} />;
      default: return <FileTxtOutlined />;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 200px)' }}>
      {/* 工具栏 */}
      <div style={{ marginBottom: 16, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <Select
          style={{ width: 200 }}
          placeholder="选择知识库"
          value={collection || undefined}
          onChange={onCollectionChange}
          options={collections.map((c) => ({ label: `${c.name} (${c.file_count}文件)`, value: c.name }))}
        />
        <Select
          style={{ width: 100 }}
          value={topK}
          onChange={setTopK}
          options={[3, 5, 10, 15, 20].map((k) => ({ label: `Top-${k}`, value: k }))}
        />
        <Button icon={<ClearOutlined />} onClick={handleClear} disabled={messages.length === 0}>
          清空对话
        </Button>
        <Tag color="blue">Ctrl+Enter 发送</Tag>
      </div>

      {/* 消息区域 */}
      <div className="chat-messages">
        {messages.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>
            <MessageOutlined style={{ fontSize: 48, marginBottom: 16 }} />
            <p>选择知识库后，输入问题开始对话</p>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div key={idx} className={`chat-message ${msg.role}`}>
              <div className="chat-message-header">
                {msg.role === 'user' ? '你' : 'DX-RAG 助手'}
              </div>
              {msg.role === 'assistant' ? (
                <div className="markdown-content">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                  {msg.sources && msg.sources.length > 0 && (
                    <Collapse
                      style={{ marginTop: 12 }}
                      size="small"
                      items={[
                        {
                          key: 'sources',
                          label: `参考来源 (${msg.sources.length})`,
                          children: (
                            <List
                              size="small"
                              dataSource={msg.sources}
                              renderItem={(src, i) => (
                                <List.Item>
                                  <div style={{ width: '100%' }}>
                                    <div style={{ marginBottom: 4 }}>
                                      {getFileIcon(src.file_name)}
                                      <span style={{ marginLeft: 6, fontWeight: 500 }}>{src.file_name}</span>
                                      <Tag style={{ marginLeft: 8 }} color="blue">
                                        相似度: {(src.similarity * 100).toFixed(1)}%
                                      </Tag>
                                    </div>
                                    <div style={{ fontSize: 12, color: '#666', whiteSpace: 'pre-wrap' }}>
                                      {src.content}
                                    </div>
                                  </div>
                                </List.Item>
                              )}
                            />
                          ),
                        },
                      ]}
                    />
                  )}
                </div>
              ) : (
                <div>{msg.content}</div>
              )}
            </div>
          ))
        )}
        {loading && (
          <div className="chat-message assistant">
            <Spin size="small" /> 正在检索和生成答案...
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 输入区域 */}
      <div className="chat-input-area" style={{ marginTop: 12 }}>
        <TextArea
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入问题，Ctrl+Enter 发送"
          autoSize={{ minRows: 2, maxRows: 6 }}
          disabled={loading}
          style={{ flex: 1 }}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSend}
          loading={loading}
          disabled={!inputValue.trim()}
          size="large"
        >
          发送
        </Button>
      </div>
    </div>
  );
}

// ============================================================
//  文件上传面板
// ============================================================

function UploadPanel({
  collection,
  collections,
  onCollectionChange,
  onSuccess,
}: {
  collection: string;
  collections: Collection[];
  onCollectionChange: (v: string) => void;
  onSuccess: () => void;
}) {
  const [uploading, setUploading] = useState(false);

  const handleUpload = async (file: File) => {
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      if (collection) {
        formData.append('collection_name', collection);
      }
      const data = await apiPost('/upload', formData);
      message.success(`上传成功！已切分为 ${data.chunks} 个文本块`);
      onSuccess();
    } catch (err: any) {
      message.error(err.message || '上传失败');
    } finally {
      setUploading(false);
    }
    return false; // 阻止默认上传
  };

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <Select
          style={{ width: 300 }}
          placeholder="选择目标知识库"
          value={collection || undefined}
          onChange={onCollectionChange}
          options={collections.map((c) => ({ label: `${c.name} (${c.file_count} 文件)`, value: c.name }))}
          allowClear
        />
      </div>

      <Dragger
        name="file"
        multiple={false}
        showUploadList={false}
        beforeUpload={handleUpload}
        disabled={uploading}
        accept=".pdf,.docx,.xlsx,.xlsm,.xltx,.xltm,.txt,.md,.csv,.json,.log"
      >
        <p className="ant-upload-drag-icon">
          <UploadOutlined style={{ fontSize: 48, color: '#1890ff' }} />
        </p>
        <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
        <p className="ant-upload-hint">
          支持 PDF（含图片型）、Word、Excel、Markdown、TXT、CSV、JSON 等格式
        </p>
        <p className="ant-upload-hint">单个文件最大 50MB</p>
      </Dragger>

      {uploading && (
        <div style={{ textAlign: 'center', marginTop: 24 }}>
          <Spin tip="正在处理文件（提取文本 → 清洗 → 切片 → 向量化）..." />
        </div>
      )}

      <Card title="支持的文件格式" size="small" style={{ marginTop: 24 }}>
        <Space wrap>
          <Tag icon={<FilePdfOutlined />} color="red">PDF（含图片型）</Tag>
          <Tag icon={<FileWordOutlined />} color="blue">Word (.docx)</Tag>
          <Tag icon={<FileExcelOutlined />} color="green">Excel (.xlsx/.xlsm)</Tag>
          <Tag icon={<FileMarkdownOutlined />} color="purple">Markdown (.md)</Tag>
          <Tag icon={<FileTxtOutlined />}>TXT / CSV / JSON / LOG</Tag>
        </Space>
      </Card>
    </div>
  );
}

// ============================================================
//  知识库管理面板
// ============================================================

function CollectionsPanel({
  collections,
  onRefresh,
  onSelect,
}: {
  collections: Collection[];
  onRefresh: () => void;
  onSelect: (v: string) => void;
}) {
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [renameModalOpen, setRenameModalOpen] = useState(false);
  const [targetCol, setTargetCol] = useState('');
  const [form] = Form.useForm();
  const [renameForm] = Form.useForm();
  const [loading, setLoading] = useState(false);

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);
      const formData = new FormData();
      formData.append('name', values.name);
      await apiPost('/collections', formData);
      message.success('知识库创建成功');
      setCreateModalOpen(false);
      form.resetFields();
      onRefresh();
    } catch (err: any) {
      if (err.message) message.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRename = async () => {
    try {
      const values = await renameForm.validateFields();
      setLoading(true);
      const formData = new FormData();
      formData.append('new_name', values.new_name);
      await fetch(`${API_BASE}/collections/${encodeURIComponent(targetCol)}`, {
        method: 'PUT',
        body: formData,
      }).then(async (res) => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: '重命名失败' }));
          throw new Error(err.detail || '重命名失败');
        }
        return res.json();
      });
      message.success('重命名成功');
      setRenameModalOpen(false);
      renameForm.resetFields();
      onRefresh();
    } catch (err: any) {
      if (err.message) message.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (name: string) => {
    try {
      await apiDelete(`/collections/${encodeURIComponent(name)}`);
      message.success('知识库已删除');
      onRefresh();
    } catch (err: any) {
      message.error(err.message || '删除失败');
    }
  };

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalOpen(true)}>
          创建知识库
        </Button>
        <Button icon={<ReloadOutlined />} onClick={onRefresh} style={{ marginLeft: 8 }}>
          刷新
        </Button>
      </div>

      {collections.length === 0 ? (
        <Empty description="暂无知识库，请创建一个" />
      ) : (
        <List
          dataSource={collections}
          renderItem={(item) => (
            <List.Item
              actions={[
                <Button
                  key="edit"
                  size="small"
                  icon={<EditOutlined />}
                  onClick={() => {
                    setTargetCol(item.name);
                    renameForm.setFieldsValue({ new_name: item.name });
                    setRenameModalOpen(true);
                  }}
                >
                  重命名
                </Button>,
                <Popconfirm
                  key="delete"
                  title="确定删除此知识库？"
                  description="删除后数据不可恢复"
                  onConfirm={() => handleDelete(item.name)}
                  okText="确定"
                  cancelText="取消"
                >
                  <Button size="small" danger icon={<DeleteOutlined />}>
                    删除
                  </Button>
                </Popconfirm>,
              ]}
            >
              <List.Item.Meta
                avatar={<DatabaseOutlined style={{ fontSize: 24, color: '#1890ff' }} />}
                title={
                  <span style={{ fontSize: 16, fontWeight: 500, cursor: 'pointer' }} onClick={() => onSelect(item.name)}>
                    {item.name}
                  </span>
                }
                description={
                  <Space>
                    <Tag>{item.file_count} 个文件</Tag>
                    <Tag>{item.total_chunks} 个文本块</Tag>
                  </Space>
                }
              />
            </List.Item>
          )}
        />
      )}

      {/* 创建知识库 Modal */}
      <Modal
        title="创建知识库"
        open={createModalOpen}
        onOk={handleCreate}
        onCancel={() => { setCreateModalOpen(false); form.resetFields(); }}
        confirmLoading={loading}
        okText="创建"
        cancelText="取消"
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="知识库名称"
            rules={[
              { required: true, message: '请输入知识库名称' },
              { min: 3, message: '名称至少 3 个字符' },
              { max: 50, message: '名称最多 50 个字符' },
              {
                pattern: /^[a-zA-Z0-9一-龥].*[a-zA-Z0-9一-龥]$/,
                message: '名称应以字母、数字或中文开头和结尾',
              },
            ]}
          >
            <Input placeholder="请输入知识库名称（3-50字符）" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 重命名 Modal */}
      <Modal
        title="重命名知识库"
        open={renameModalOpen}
        onOk={handleRename}
        onCancel={() => { setRenameModalOpen(false); renameForm.resetFields(); }}
        confirmLoading={loading}
        okText="确定"
        cancelText="取消"
      >
        <Form form={renameForm} layout="vertical">
          <Form.Item label="当前名称">
            <Input value={targetCol} disabled />
          </Form.Item>
          <Form.Item
            name="new_name"
            label="新名称"
            rules={[
              { required: true, message: '请输入新名称' },
              { min: 3, message: '名称至少 3 个字符' },
              { max: 50, message: '名称最多 50 个字符' },
            ]}
          >
            <Input placeholder="请输入新名称" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

// ============================================================
//  文件管理面板
// ============================================================

function FilesPanel({
  collection,
  collections,
  onCollectionChange,
  onRefresh,
}: {
  collection: string;
  collections: Collection[];
  onCollectionChange: (v: string) => void;
  onRefresh: () => void;
}) {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewFile, setPreviewFile] = useState('');
  const [previewContent, setPreviewContent] = useState('');
  const [previewChunks, setPreviewChunks] = useState<string[]>([]);

  const loadFiles = useCallback(async () => {
    if (!collection) return;
    setLoading(true);
    try {
      const data = await apiGet(`/files?collection_name=${encodeURIComponent(collection)}`);
      setFiles(data.files || []);
    } catch {
      setFiles([]);
    } finally {
      setLoading(false);
    }
  }, [collection]);

  useEffect(() => {
    loadFiles();
  }, [loadFiles]);

  const handlePreview = async (fileName: string) => {
    try {
      const data = await apiGet(
        `/files/${encodeURIComponent(fileName)}/preview?collection_name=${encodeURIComponent(collection)}`
      );
      setPreviewFile(fileName);
      setPreviewContent(data.content || '');
      setPreviewChunks(data.chunks || []);
      setPreviewOpen(true);
    } catch (err: any) {
      message.error(err.message || '预览失败');
    }
  };

  const handleDelete = async (fileName: string) => {
    try {
      await apiDelete(
        `/files/${encodeURIComponent(fileName)}?collection_name=${encodeURIComponent(collection)}`
      );
      message.success('文件已删除');
      loadFiles();
      onRefresh();
    } catch (err: any) {
      message.error(err.message || '删除失败');
    }
  };

  const formatSize = (bytes?: number) => {
    if (!bytes) return '未知';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getFileIcon = (fileName: string) => {
    const ext = fileName.split('.').pop()?.toLowerCase();
    switch (ext) {
      case 'pdf': return <FilePdfOutlined style={{ fontSize: 24, color: '#ff4d4f' }} />;
      case 'docx': return <FileWordOutlined style={{ fontSize: 24, color: '#1890ff' }} />;
      case 'xlsx': case 'xlsm': return <FileExcelOutlined style={{ fontSize: 24, color: '#52c41a' }} />;
      case 'md': return <FileMarkdownOutlined style={{ fontSize: 24, color: '#722ed1' }} />;
      default: return <FileTxtOutlined style={{ fontSize: 24 }} />;
    }
  };

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', gap: 12, alignItems: 'center' }}>
        <Select
          style={{ width: 250 }}
          placeholder="选择知识库"
          value={collection || undefined}
          onChange={onCollectionChange}
          options={collections.map((c) => ({ label: `${c.name} (${c.file_count}文件)`, value: c.name }))}
        />
        <Button icon={<ReloadOutlined />} onClick={loadFiles}>
          刷新
        </Button>
      </div>

      {!collection ? (
        <Empty description="请先选择知识库" />
      ) : loading ? (
        <Spin tip="加载中..." />
      ) : files.length === 0 ? (
        <Empty description="该知识库暂无文件" />
      ) : (
        <List
          dataSource={files}
          renderItem={(item) => (
            <List.Item
              actions={[
                <Button key="preview" size="small" icon={<EyeOutlined />} onClick={() => handlePreview(item.file_name)}>
                  预览
                </Button>,
                <Popconfirm
                  key="delete"
                  title="确定删除此文件？"
                  onConfirm={() => handleDelete(item.file_name)}
                  okText="确定"
                  cancelText="取消"
                >
                  <Button size="small" danger icon={<DeleteOutlined />}>
                    删除
                  </Button>
                </Popconfirm>,
              ]}
            >
              <List.Item.Meta
                avatar={getFileIcon(item.file_name)}
                title={item.file_name}
                description={
                  <Space>
                    <Tag>{item.chunks} 个文本块</Tag>
                    <Tag>{formatSize(item.size_bytes)}</Tag>
                  </Space>
                }
              />
            </List.Item>
          )}
        />
      )}

      {/* 文件预览 Modal */}
      <Modal
        title={`预览: ${previewFile}`}
        open={previewOpen}
        onCancel={() => setPreviewOpen(false)}
        width={800}
        footer={null}
      >
        <Tabs
          items={[
            {
              key: 'chunks',
              label: `文本块 (${previewChunks.length})`,
              children: (
                <div style={{ maxHeight: 400, overflow: 'auto' }}>
                  {previewChunks.length === 0 ? (
                    <Empty description="无切片数据" />
                  ) : (
                    previewChunks.map((chunk, i) => (
                      <Card key={i} size="small" style={{ marginBottom: 8 }} title={`Chunk ${i + 1}`}>
                        <div style={{ whiteSpace: 'pre-wrap', fontSize: 13 }}>{chunk}</div>
                      </Card>
                    ))
                  )}
                </div>
              ),
            },
            {
              key: 'raw',
              label: '原始内容',
              children: (
                <div style={{ maxHeight: 400, overflow: 'auto', whiteSpace: 'pre-wrap', fontSize: 13 }}>
                  {previewContent || '无原始内容'}
                </div>
              ),
            },
          ]}
        />
      </Modal>
    </div>
  );
}
