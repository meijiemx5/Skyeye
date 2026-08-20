/**
 * 前端权限表 - 与后端 app/utils/permissions.py 保持一致。
 * 仅用于隐藏无权限的菜单和按钮；真正的拦截在后端。
 */
export const ALL_ROLES = [
  'admin', 'finance', 'project_manager', 'procurement', 'construction', 'warehouse',
] as const;

export const PERMISSION_ROLES: Record<string, readonly string[]> = {
  'project:list': ['admin', 'project_manager'],
  'project:options': ALL_ROLES,
  'project:write': ['admin', 'project_manager'],
  'project:delete': ['admin'],
  'contract:view': ['admin', 'project_manager'],
  'contract:options': ['admin', 'project_manager', 'finance', 'procurement'],
  'contract:write': ['admin', 'project_manager', 'procurement'],
  'contract:delete': ['admin'],
  'contract:payment': ['admin', 'finance'],
  'acceptance:view': ['admin', 'project_manager'],
  'acceptance:write': ['admin', 'project_manager'],
  'acceptance:delete': ['admin'],
  'invoice:view': ['admin', 'project_manager', 'finance'],
  'invoice:manage': ['admin', 'finance'],
  'reimburse:audit_manager': ['admin', 'project_manager'],
  'reimburse:audit_finance': ['admin', 'finance'],
  'reimburse:receipt': ['admin', 'finance'],
  'reimburse:receipt_skip': ['admin'],
  'reimburse:document': ['admin', 'finance'],
  'reimburse:voucher': ['admin', 'finance'],
  'reimburse:pay': ['admin', 'finance'],
  'reimburse:delete': ['admin'],
  'analysis:overview': ['admin', 'finance', 'project_manager'],
  // 看板文案含预算/合同金额，与项目查看权限对齐；「我的待办」对所有人开放
  'alerts:board': ['admin', 'finance', 'project_manager'],
};

export function hasPermission(role: string | undefined, permission: string): boolean {
  if (!role) return false;
  return (PERMISSION_ROLES[permission] ?? ['admin']).includes(role);
}

export function currentUser(): { user_id?: string; role?: string; display_name?: string; username?: string } {
  try {
    return JSON.parse(localStorage.getItem('user') || '{}');
  } catch {
    return {};
  }
}

export function can(permission: string): boolean {
  return hasPermission(currentUser().role, permission);
}
