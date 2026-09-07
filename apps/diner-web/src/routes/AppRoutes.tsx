import type { ReactNode } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { LoadingState } from '../components/LoadingState';
import { StateMessage } from '../components/StateMessage';
import { DinerHomePage } from '../pages/DinerHomePage';
import { JoinPage } from '../pages/JoinPage';
import { MenuPage } from '../pages/MenuPage';
import { ProductDetailPage } from '../pages/ProductDetailPage';
import { useAuth } from '../session/AuthContext';

function SessionBoundary({ children }: { children: ReactNode }) {
  const { status, retryRestoration, leaveSession } = useAuth();
  if (status === 'checking') return <LoadingState message="Comprobando tu acceso…" />;
  if (status === 'authenticated') return children;
  if (status === 'restoration-error') {
    return <StateMessage eyebrow="Conexión interrumpida" title="No pudimos comprobar tu acceso"><p>Revisa tu conexión. Conservamos tu sesión para que puedas intentarlo de nuevo.</p><button className="primary-button" type="button" onClick={retryRestoration}>Reintentar</button></StateMessage>;
  }
  if (status === 'closed') {
    return <StateMessage eyebrow="Visita finalizada" title="Esta sesión ha terminado"><p>La sesión de tu mesa ya fue cerrada. Para una nueva visita, escanea el código QR de la mesa.</p><a className="primary-button button-link" href="/" onClick={leaveSession}>Volver al acceso</a></StateMessage>;
  }
  if (status === 'expired') {
    return <StateMessage eyebrow="Acceso vencido" title="Tu acceso ya no está activo"><p>Por seguridad, vuelve a escanear el código QR de tu mesa para entrar.</p><a className="primary-button button-link" href="/" onClick={leaveSession}>Volver al acceso</a></StateMessage>;
  }
  return <Navigate to="/" replace />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<JoinPage />} />
      <Route path="/join/:joinContextKey" element={<JoinPage />} />
      <Route path="/app" element={<SessionBoundary><DinerHomePage /></SessionBoundary>} />
      <Route path="/menu" element={<SessionBoundary><MenuPage /></SessionBoundary>} />
      <Route path="/products/:productId" element={<SessionBoundary><ProductDetailPage /></SessionBoundary>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
