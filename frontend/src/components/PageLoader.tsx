import './PageLoader.css';

export function PageLoader() {
  return (
    <div className="page-loader">
      <div className="page-loader-card">
        <div className="skeleton loader-line" />
        <div className="skeleton loader-line short" />
        <div className="skeleton loader-line" />
      </div>
    </div>
  );
}
