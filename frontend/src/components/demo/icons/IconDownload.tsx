import { baseProps, type IconProps } from './index';

export const IconDownload = ({ size = 20, className, ...rest }: IconProps) => (
  <svg {...baseProps(size, className, rest)}>
    <path d="M12 4v11" />
    <path d="m7 10 5 5 5-5" />
    <path d="M5 20h14" />
  </svg>
);

export default IconDownload;
