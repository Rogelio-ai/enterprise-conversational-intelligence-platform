export interface Workspace {
  key: 'host' | 'waiter' | 'kitchen' | 'cashier' | 'manager';
  label: string;
  description: string;
  path: string;
  permissions: string[];
}

export const workspaces: Workspace[] = [
  {
    key: 'host',
    label: 'Host',
    description: 'Servicio y mesas',
    path: '/host',
    permissions: ['location.read', 'resource.read', 'restaurant_service.read'],
  },
  {
    key: 'waiter',
    label: 'Mesero',
    description: 'Solicitudes y atención',
    path: '/waiter',
    permissions: ['restaurant_service.read', 'restaurant_order.read', 'restaurant_check.read', 'operational_request.read'],
  },
  {
    key: 'kitchen',
    label: 'Cocina',
    description: 'Preparación',
    path: '/kitchen',
    permissions: ['preparation.read'],
  },
  {
    key: 'cashier',
    label: 'Caja',
    description: 'Cobro y cierre',
    path: '/cashier',
    permissions: ['cash_management.read', 'restaurant_check.read', 'restaurant_payment.read'],
  },
  {
    key: 'manager',
    label: 'Gerencia',
    description: 'Control operativo',
    path: '/manager',
    permissions: ['resource.read', 'preparation.read', 'restaurant_check.read', 'restaurant_payment.read', 'cash_management.read'],
  },
];

export function canUseWorkspace(permissions: string[], workspace: Workspace): boolean {
  return workspace.permissions.every((permission) => permissions.includes(permission));
}
