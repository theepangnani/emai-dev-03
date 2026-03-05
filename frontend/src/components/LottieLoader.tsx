import Lottie from 'lottie-react';
import { useMemo } from 'react';
import { useTheme } from '../context/ThemeContext';

interface LottieLoaderProps {
  size?: number;
  loop?: boolean;
  autoplay?: boolean;
}

// Brand colors in Lottie [R, G, B, A] format (0-1 range)
const THEME_COLORS: Record<string, [number, number, number, number]> = {
  light:  [0.290, 0.565, 0.851, 1], // #4a90d9 blue
  dark:   [0.655, 0.545, 0.980, 1], // #a78bfa purple (warm charcoal accent)
  focus:  [0.655, 0.545, 0.980, 1], // #a78bfa purple
};

function createDotLayer(
  index: number,
  x: number,
  frameOffset: number,
  color: [number, number, number, number],
) {
  return {
    ddd: 0, ind: index, ty: 4, nm: `Dot ${index}`, sr: 1,
    ks: {
      o: {
        a: 1,
        k: [
          { i: { x: [0.33], y: [1] }, o: { x: [0.67], y: [0] }, t: frameOffset, s: [40] },
          { i: { x: [0.33], y: [1] }, o: { x: [0.67], y: [0] }, t: frameOffset + 8, s: [100] },
          { t: frameOffset + 16, s: [40] },
        ],
      },
      r: { a: 0, k: 0 },
      p: {
        a: 1,
        k: [
          { i: { x: 0.33, y: 1 }, o: { x: 0.67, y: 0 }, t: frameOffset, s: [x, 80, 0] },
          { i: { x: 0.33, y: 1 }, o: { x: 0.67, y: 0 }, t: frameOffset + 8, s: [x, 56, 0] },
          { t: frameOffset + 16, s: [x, 80, 0] },
        ],
      },
      a: { a: 0, k: [0, 0, 0] },
      s: {
        a: 1,
        k: [
          { i: { x: [0.33, 0.33, 0.67], y: [1, 1, 1] }, o: { x: [0.67, 0.67, 0.33], y: [0, 0, 0] }, t: frameOffset, s: [100, 100, 100] },
          { i: { x: [0.33, 0.33, 0.67], y: [1, 1, 1] }, o: { x: [0.67, 0.67, 0.33], y: [0, 0, 0] }, t: frameOffset + 8, s: [120, 120, 100] },
          { t: frameOffset + 16, s: [100, 100, 100] },
        ],
      },
    },
    ao: 0,
    shapes: [{
      ty: 'gr', nm: 'Dot', np: 3,
      it: [
        { d: 1, ty: 'el', s: { a: 0, k: [16, 16] }, p: { a: 0, k: [0, 0] }, nm: 'Ellipse' },
        { ty: 'fl', c: { a: 0, k: color }, o: { a: 0, k: 100 }, r: 1, nm: 'Fill' },
        { ty: 'tr', p: { a: 0, k: [0, 0] }, a: { a: 0, k: [0, 0] }, s: { a: 0, k: [100, 100] }, r: { a: 0, k: 0 }, o: { a: 0, k: 100 } },
      ],
    }],
    ip: 0, op: 50, st: 0,
  };
}

function createAnimationData(color: [number, number, number, number]) {
  return {
    v: '5.7.1', fr: 30, ip: 0, op: 50, w: 140, h: 140,
    nm: 'ClassBridge Loader', ddd: 0, assets: [],
    layers: [
      createDotLayer(1, 46, 0, color),
      createDotLayer(2, 70, 8, color),
      createDotLayer(3, 94, 16, color),
    ],
  };
}

export function LottieLoader({ size = 140, loop = true, autoplay = true }: LottieLoaderProps) {
  const { theme } = useTheme();
  const animationData = useMemo(
    () => createAnimationData(THEME_COLORS[theme] ?? THEME_COLORS.light),
    [theme],
  );

  return (
    <Lottie
      animationData={animationData}
      loop={loop}
      autoplay={autoplay}
      style={{ width: size, height: size }}
    />
  );
}
