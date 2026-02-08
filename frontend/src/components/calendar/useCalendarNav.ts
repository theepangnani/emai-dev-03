import { useState, useMemo } from 'react';

export type CalendarViewMode = 'day' | '3day' | 'week' | 'month';

export interface UseCalendarNavReturn {
  currentDate: Date;
  viewMode: CalendarViewMode;
  setViewMode: (mode: CalendarViewMode) => void;
  goNext: () => void;
  goPrev: () => void;
  goToday: () => void;
  goToDate: (date: Date) => void;
  rangeStart: Date;
  rangeEnd: Date;
  headerLabel: string;
}

function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

function addDays(d: Date, n: number): Date {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}

function getMonday(d: Date): Date {
  const day = d.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  return addDays(startOfDay(d), diff);
}

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

const SHORT_MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

function formatRange(start: Date, end: Date): string {
  if (start.getMonth() === end.getMonth()) {
    return `${SHORT_MONTHS[start.getMonth()]} ${start.getDate()}\u2013${end.getDate()}, ${start.getFullYear()}`;
  }
  return `${SHORT_MONTHS[start.getMonth()]} ${start.getDate()} \u2013 ${SHORT_MONTHS[end.getMonth()]} ${end.getDate()}, ${end.getFullYear()}`;
}

export function useCalendarNav(initialMode: CalendarViewMode = 'month'): UseCalendarNavReturn {
  const [currentDate, setCurrentDate] = useState(() => startOfDay(new Date()));
  const [viewMode, setViewMode] = useState<CalendarViewMode>(initialMode);

  const { rangeStart, rangeEnd, headerLabel } = useMemo(() => {
    let rs: Date, re: Date, label: string;

    switch (viewMode) {
      case 'month': {
        rs = new Date(currentDate.getFullYear(), currentDate.getMonth(), 1);
        re = new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 0);
        label = `${MONTH_NAMES[currentDate.getMonth()]} ${currentDate.getFullYear()}`;
        break;
      }
      case 'week': {
        rs = getMonday(currentDate);
        re = addDays(rs, 6);
        label = formatRange(rs, re);
        break;
      }
      case '3day': {
        rs = startOfDay(currentDate);
        re = addDays(rs, 2);
        label = formatRange(rs, re);
        break;
      }
      case 'day': {
        rs = startOfDay(currentDate);
        re = rs;
        const opts: Intl.DateTimeFormatOptions = { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' };
        label = rs.toLocaleDateString(undefined, opts);
        break;
      }
    }
    return { rangeStart: rs, rangeEnd: re, headerLabel: label };
  }, [currentDate, viewMode]);

  const goNext = () => {
    setCurrentDate(prev => {
      switch (viewMode) {
        case 'month': return new Date(prev.getFullYear(), prev.getMonth() + 1, 1);
        case 'week': return addDays(prev, 7);
        case '3day': return addDays(prev, 3);
        case 'day': return addDays(prev, 1);
      }
    });
  };

  const goPrev = () => {
    setCurrentDate(prev => {
      switch (viewMode) {
        case 'month': return new Date(prev.getFullYear(), prev.getMonth() - 1, 1);
        case 'week': return addDays(prev, -7);
        case '3day': return addDays(prev, -3);
        case 'day': return addDays(prev, -1);
      }
    });
  };

  const goToday = () => setCurrentDate(startOfDay(new Date()));
  const goToDate = (d: Date) => setCurrentDate(startOfDay(d));

  return { currentDate, viewMode, setViewMode, goNext, goPrev, goToday, goToDate, rangeStart, rangeEnd, headerLabel };
}
