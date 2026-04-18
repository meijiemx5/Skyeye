import { useState, useEffect } from 'react';
import { Modal, message } from 'antd';
import FileUpload, { FileInfo } from './FileUpload';

interface FileManagerProps {
  open: boolean;
  title: string;
  entityType: string;
  entityId: string;
  files: FileInfo[];
  onSave: (files: FileInfo[]) => Promise<void>;
  onClose: () => void;
  canEdit?: boolean;
}

export default function FileManager({ open, title, entityType, entityId, files: initialFiles, onSave, onClose, canEdit = true }: FileManagerProps) {
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) setFiles(initialFiles || []);
  }, [open, initialFiles]);

  const handleOk = async () => {
    setSaving(true);
    try {
      await onSave(files);
      message.success('附件保存成功');
      onClose();
    } catch (e: any) {
      message.error(e.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title={`📎 ${title} - 附件管理`}
      open={open}
      onOk={canEdit ? handleOk : undefined}
      onCancel={onClose}
      okText="保存"
      cancelText={canEdit ? '取消' : '关闭'}
      confirmLoading={saving}
      footer={canEdit ? undefined : null}
      width={600}
    >
      <FileUpload
        entityType={entityType}
        entityId={entityId}
        files={files}
        onChange={setFiles}
        disabled={!canEdit}
      />
    </Modal>
  );
}
