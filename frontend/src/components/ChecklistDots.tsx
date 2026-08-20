import { Tooltip } from 'antd';
import { CHECKLIST_STATUS } from '../utils/constants';

export interface ChecklistItem {
  key: string;
  label: string;
  status: 'ok' | 'missing' | 'overdue' | 'warning';
  message: string;
  severity: string;
  due_date?: string | null;
  days_overdue?: number;
  applicable: boolean;
  owner_name?: string | null;
  owner_role?: string;
}

/** 项目完整度红黄绿灯：预算/报价/合同/验收/发票/报销/工费一眼看完。 */
export default function ChecklistDots({ items, size = 12 }: { items: ChecklistItem[]; size?: number }) {
  return (
    <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
      {items.map((item) => {
        const color = item.applicable ? CHECKLIST_STATUS[item.status]?.color : '#d9dde3';
        return (
          <Tooltip
            key={item.key}
            title={
              <span>
                <b>{item.label}</b>：{item.applicable ? CHECKLIST_STATUS[item.status]?.label : '不适用'}
                <br />{item.message}
              </span>
            }
          >
            <span
              style={{
                width: size, height: size, borderRadius: '50%', background: color,
                display: 'inline-block', cursor: 'help',
              }}
            />
          </Tooltip>
        );
      })}
    </span>
  );
}
