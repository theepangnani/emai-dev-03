import { LottieLoader } from './LottieLoader';
import './PageLoader.css';

export function PageLoader() {
  return (
    <div className="page-loader">
      <LottieLoader size={100} />
    </div>
  );
}
