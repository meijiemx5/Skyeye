import { useState } from 'react';
import { Upload, Button, message, List, Space, Popconfirm } from 'antd';
import { UploadOutlined, FileOutlined, DeleteOutlined, DownloadOutlined, EyeOutlined } from '@ant-design/icons';
import { uploadApi } from '../api/client';
import axios from 'axios';

export interface FileInfo {
  file_id: string;
  file_name: string;
  file_type: string;
  file_size: number;
  s3_key: string;
  upload_time: string;
  uploaded_by?: string;
}

interface FileUploadProps {
  entityType: string;  // contract, reimbursement, acceptance, inventory
  entityId: string;
  files: FileInfo[];
  onChange: (files: FileInfo[]) => void;
  maxCount?: number;
  disabled?: boolean;
}

export default function FileUpload({ entityType, entityId, files, onChange, maxCount = 10, disabled = false }: FileUploadProps) {
  const [uploading, setUploading] = useState(false);

  const handleUpload = async (options: any) => {
    const { file, onSuccess, onError } = options;
    if (!entityId) {
      message.warning('请先保存记录后再上传附件');
      onError(new Error('no entity id'));
      return;
    }
    setUploading(true);
    try {
      // Step 1: Get presigned URL
      const res = await uploadApi.getUploadUrl({
        file_name: file.name,
        file_type: file.type || 'application/octet-stream',
        entity_type: entityType,
        entity_id: entityId,
      });
      const { upload_url, file_id, s3_key } = res.data.data;

      // Step 2: Upload to S3 (use clean axios, no JWT header)
      await axios.put(upload_url, file, {
        headers: { 'Content-Type': file.type || 'application/octet-stream' },
        transformRequest: [(data: any) => data],  // prevent axios from transforming
      });

      // Step 3: Add to file list
      const newFile: FileInfo = {
        file_id,
        file_name: file.name,
        file_type: file.type || '',
        file_size: file.size,
        s3_key,
        upload_time: new Date().toISOString(),
      };
      onChange([...files, newFile]);
      message.success(`${file.name} 上传成功`);
      onSuccess(null, file);
    } catch (e: any) {
      message.error(`上传失败: ${e.message}`);
      onError(e);
    } finally {
      setUploading(false);
    }
  };

  const viewableExts = ['pdf', 'jpg', 'jpeg', 'png', 'gif', 'svg', 'txt', 'html'];

  const isViewable = (fileName: string) => {
    const ext = fileName.split('.').pop()?.toLowerCase() || '';
    return viewableExts.includes(ext);
  };

  const handleView = async (file: FileInfo) => {
    try {
      const res = await uploadApi.getDownloadUrl(file.s3_key);
      const url = res.data.data.download_url;
      // Use location.href as fallback for mobile
      window.location.href = url;
    } catch (e: any) {
      message.error('获取查看链接失败: ' + (e.message || ''));
    }
  };

  const handleDownload = async (file: FileInfo) => {
    try {
      const res = await uploadApi.getDownloadUrl(file.s3_key, true);
      const url = res.data.data.download_url;
      window.location.href = url;
    } catch (e: any) {
      message.error('获取下载链接失败: ' + (e.message || ''));
    }
  };

  const handleDelete = (fileId: string) => {
    onChange(files.filter(f => f.file_id !== fileId));
  };

  return (
    <div>
      <Upload
        customRequest={handleUpload}
        showUploadList={false}
        multiple
        disabled={disabled || uploading || files.length >= maxCount}
      >
        <Button icon={<UploadOutlined />} loading={uploading} disabled={disabled || files.length >= maxCount}>
          {uploading ? '上传中...' : '上传附件'}
        </Button>
      </Upload>
      {files.length > 0 && (
        <List
          size="small"
          style={{ marginTop: 8 }}
          dataSource={files}
          renderItem={(file) => (
            <List.Item style={{ padding: '4px 0' }}>
              <Space>
                <FileOutlined />
                <span style={{ fontSize: 13 }}>{file.file_name}</span>
                <span style={{ fontSize: 12, color: '#999' }}>({(file.file_size / 1024).toFixed(1)} KB)</span>
              </Space>
              <Space>
                {isViewable(file.file_name) && <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => handleView(file)}>查看</Button>}
                <Button type="link" size="small" icon={<DownloadOutlined />} onClick={() => handleDownload(file)}>下载</Button>
                {!disabled && (
                  <Popconfirm title="确定删除?" onConfirm={() => handleDelete(file.file_id)}>
                    <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
                  </Popconfirm>
                )}
              </Space>
            </List.Item>
          )}
        />
      )}
      <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>
        {files.length}/{maxCount} 个文件
      </div>
    </div>
  );
}
