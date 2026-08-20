import { List, Tag, Button, Empty, Typography } from 'antd';
import { ClockCircleOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { SEVERITY, TODO_TYPE_LABELS } from '../utils/constants';

const { Text } = Typography;

export interface TodoItem {
  todo_id: string;
  type: string;
  title: string;
  detail: string;
  severity: 'high' | 'medium' | 'low';
  link: string;
  project_id?: string | null;
  project_name?: string | null;
  due_date?: string | null;
  days_pending?: number;
}

const BORDER_COLORS: Record<string, string> = {
  high: '#e5484d', medium: '#f59e0b', low: '#2563eb',
};

export default function TodoList({ todos, emptyText = '没有待办，今天是清爽的一天 🎉' }: {
  todos: TodoItem[];
  emptyText?: string;
}) {
  const navigate = useNavigate();

  if (!todos.length) return <Empty description={emptyText} />;

  return (
    <List
      size="small"
      dataSource={todos}
      renderItem={(todo) => (
        <List.Item
          style={{ borderLeft: `3px solid ${BORDER_COLORS[todo.severity] || '#d9dde3'}`, paddingLeft: 12 }}
          actions={[<Button type="link" size="small" onClick={() => navigate(todo.link)}>去处理</Button>]}
        >
          <List.Item.Meta
            title={
              <span>
                <Tag color={SEVERITY[todo.severity]?.color} style={{ marginRight: 8 }}>
                  {SEVERITY[todo.severity]?.label}
                </Tag>
                {todo.title}
                <Tag style={{ marginLeft: 8 }}>{TODO_TYPE_LABELS[todo.type] || todo.type}</Tag>
              </span>
            }
            description={
              <span>
                <Text type="secondary" style={{ fontSize: 13 }}>{todo.detail}</Text>
                {!!todo.days_pending && todo.days_pending > 0 && (
                  <Text type="danger" style={{ fontSize: 12, marginLeft: 8 }}>
                    <ClockCircleOutlined /> {todo.days_pending} 天
                  </Text>
                )}
                {todo.due_date && (
                  <Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>期限 {todo.due_date}</Text>
                )}
              </span>
            }
          />
        </List.Item>
      )}
    />
  );
}
