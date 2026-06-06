import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'DX-RAG 知识库问答系统',
  description: '企业级知识库问答系统 - 基于检索增强生成技术',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
