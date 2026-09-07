import { useQuery } from '@tanstack/react-query';
import { Link, Navigate } from 'react-router-dom';
import { dinerApi } from '../api/client';
import { DinerHeader } from '../components/DinerHeader';

export function ActiveCheckPage() {
  const account = useQuery({ queryKey: ['diner', 'account-preview'], queryFn: dinerApi.getAccountPreview, retry: false });
  if (account.isPending) return <div className="diner-page"><DinerHeader /><main className="product-state" aria-busy="true"><p>Buscando una cuenta activa…</p></main></div>;
  if (account.data?.active_check_id) return <Navigate to={`/check/${account.data.active_check_id}`} replace />;
  return <div className="diner-page"><DinerHeader /><main className="product-state"><p className="eyebrow">Sin cuenta activa</p><h1>No hay una cuenta por revisar</h1><p>{account.isError ? 'No pudimos comprobar el estado actual. Ninguna cuenta fue creada.' : 'Revisa tu consumo y decide explícitamente si deseas preparar una cuenta.'}</p><Link className="primary-button button-link" to="/account">Ir a mi cuenta</Link></main></div>;
}
