import './ToastNotification.css';

interface ToastNotificationProps {
  message: string | null;
}

export function ToastNotification({ message }: ToastNotificationProps) {
  if (!message) return null;

  return <div className="toast-notification">{message}</div>;
}
