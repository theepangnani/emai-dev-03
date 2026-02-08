export interface CalendarAssignment {
  id: number;
  title: string;
  description: string | null;
  courseId: number;
  courseName: string;
  courseColor: string;
  dueDate: Date;
  childName: string;
  maxPoints: number | null;
}

export const COURSE_COLORS = [
  '#49b8c0', '#f4801f', '#7c5cbf', '#e05a9e', '#4caf50',
  '#ff7043', '#5c6bc0', '#26a69a', '#ef5350', '#42a5f5',
];

export function getCourseColor(courseId: number, courseIds: number[]): string {
  const index = courseIds.indexOf(courseId);
  return COURSE_COLORS[(index >= 0 ? index : courseId) % COURSE_COLORS.length];
}

export function dateKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}
