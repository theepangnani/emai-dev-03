import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ConsentGateway } from './ConsentGateway';

interface ProtectedRouteProps {
  children: React.ReactNode;
  allowedRoles?: string[];
}

export function ProtectedRoute({ children, allowedRoles }: ProtectedRouteProps) {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="loading-container">
        <div className="loading-spinner">Loading...</div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  // Redirect users who need onboarding (check both flags for robustness)
  if (user.needs_onboarding || !user.onboarding_completed) {
    return <Navigate to="/onboarding" replace />;
  }

  if (allowedRoles) {
    const userRoles = user.roles?.length ? user.roles : (user.role ? [user.role] : []);
    if (!userRoles.some(r => allowedRoles.includes(r))) {
      return <Navigate to="/dashboard" replace />;
    }
  }

  // ConsentGateway blocks students who haven't given consent (#783)
  return <ConsentGateway>{children}</ConsentGateway>;
}
