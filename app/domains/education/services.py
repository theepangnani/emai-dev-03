"""Education domain service - business logic for courses and enrollments."""

from typing import Optional

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.course import Course, student_courses
from app.models.student import Student, parent_students
from app.models.teacher import Teacher
from app.models.user import User, UserRole


class EducationService:
    """Service for course and enrollment-related business logic."""

    def __init__(self, db: Session):
        self.db = db

    def get_visible_courses(self, user: User) -> list[Course]:
        """Get courses visible to user based on role.

        Args:
            user: The current user

        Returns:
            List of visible courses based on user role and relationships
        """
        # Public courses are visible to all
        filters = [Course.is_private == False]  # noqa: E712

        # Users can always see courses they created
        filters.append(Course.created_by_user_id == user.id)

        if user.role == UserRole.STUDENT:
            # Students can see courses they're enrolled in
            student = self.db.query(Student).filter(Student.user_id == user.id).first()
            if student:
                enrolled_ids = [c.id for c in student.courses]
                if enrolled_ids:
                    filters.append(Course.id.in_(enrolled_ids))

        elif user.role == UserRole.PARENT:
            # Parents can see courses assigned to their children
            child_student_ids = (
                self.db.query(parent_students.c.student_id)
                .filter(parent_students.c.parent_id == user.id)
                .all()
            )
            child_sids = [r[0] for r in child_student_ids]
            if child_sids:
                enrolled_course_ids = (
                    self.db.query(student_courses.c.course_id)
                    .filter(student_courses.c.student_id.in_(child_sids))
                    .all()
                )
                ecids = [r[0] for r in enrolled_course_ids]
                if ecids:
                    filters.append(Course.id.in_(ecids))
                # Also include courses created by co-parents
                co_parent_rows = (
                    self.db.query(parent_students.c.parent_id)
                    .filter(
                        parent_students.c.student_id.in_(child_sids),
                        parent_students.c.parent_id != user.id,
                    )
                    .all()
                )
                co_parent_uids = [r[0] for r in co_parent_rows]
                if co_parent_uids:
                    filters.append(Course.created_by_user_id.in_(co_parent_uids))

        elif user.role == UserRole.ADMIN:
            # Admins see everything
            return self.db.query(Course).all()

        return self.db.query(Course).filter(or_(*filters)).all()

    def verify_enrollment(self, student: Student, course: Course) -> bool:
        """Check if student is enrolled in course.

        Args:
            student: The student to check
            course: The course to check

        Returns:
            True if enrolled, False otherwise
        """
        return course in student.courses

    def get_parent_child_courses(self, parent_id: int) -> dict[int, list[Course]]:
        """Get all courses for all children of a parent.

        Args:
            parent_id: The parent's user ID

        Returns:
            Dict mapping child user_id to list of Course objects
        """
        # Get all child student IDs
        child_student_ids = (
            self.db.query(parent_students.c.student_id)
            .filter(parent_students.c.parent_id == parent_id)
            .all()
        )
        child_sids = [r[0] for r in child_student_ids]

        if not child_sids:
            return {}

        # Get students and their courses
        students = (
            self.db.query(Student)
            .filter(Student.id.in_(child_sids))
            .all()
        )

        result = {}
        for student in students:
            result[student.user_id] = student.courses

        return result

    def can_manage_course(self, user: User, course: Course) -> bool:
        """Check if user can manage a course (edit, manage roster, etc.).

        Args:
            user: The user to check
            course: The course to check

        Returns:
            True if user can manage the course, False otherwise
        """
        # Admin can manage everything
        if user.has_role(UserRole.ADMIN):
            return True

        # Course creator can manage
        if course.created_by_user_id == user.id:
            return True

        # Teacher of the course can manage
        if user.has_role(UserRole.TEACHER):
            teacher = self.db.query(Teacher).filter(Teacher.user_id == user.id).first()
            if teacher and course.teacher_id == teacher.id:
                return True

        return False

    def get_teaching_courses(self, user: User) -> list[Course]:
        """Get courses taught by a teacher.

        Args:
            user: The teacher user

        Returns:
            List of courses taught by this teacher

        Raises:
            HTTPException if user is not a teacher
        """
        if not user.has_role(UserRole.TEACHER):
            raise HTTPException(status_code=403, detail="User is not a teacher")

        teacher = self.db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if not teacher:
            return []

        return self.db.query(Course).filter(Course.teacher_id == teacher.id).all()

    def get_enrolled_courses(self, user: User) -> list[Course]:
        """Get courses a student is enrolled in.

        Args:
            user: The student user

        Returns:
            List of courses the student is enrolled in

        Raises:
            HTTPException if user is not a student
        """
        if not user.has_role(UserRole.STUDENT):
            raise HTTPException(status_code=403, detail="User is not a student")

        student = self.db.query(Student).filter(Student.user_id == user.id).first()
        if not student:
            return []

        return student.courses

    def can_access_course(self, user: User, course_id: int) -> bool:
        """Check if user has access to a course.

        Args:
            user: The user to check
            course_id: The course ID

        Returns:
            True if user can access the course, False otherwise
        """
        course = self.db.query(Course).filter(Course.id == course_id).first()
        if not course:
            return False

        # Public courses are accessible to all
        if not course.is_private:
            return True

        # Creator always has access
        if course.created_by_user_id == user.id:
            return True

        # Admin has access to everything
        if user.has_role(UserRole.ADMIN):
            return True

        # Teacher has access to courses they teach
        if user.has_role(UserRole.TEACHER):
            teacher = self.db.query(Teacher).filter(Teacher.user_id == user.id).first()
            if teacher and course.teacher_id == teacher.id:
                return True

        # Student has access to enrolled courses
        if user.has_role(UserRole.STUDENT):
            student = self.db.query(Student).filter(Student.user_id == user.id).first()
            if student and course in student.courses:
                return True

        # Parent has access to children's courses + co-parent courses
        if user.has_role(UserRole.PARENT):
            child_courses = self.get_parent_child_courses(user.id)
            for courses in child_courses.values():
                if course in courses:
                    return True

            # Also grant access to courses created by co-parents
            # (other parents linked to the same children)
            child_student_ids = (
                self.db.query(parent_students.c.student_id)
                .filter(parent_students.c.parent_id == user.id)
                .all()
            )
            child_sids = [r[0] for r in child_student_ids]
            if child_sids:
                co_parent_ids = (
                    self.db.query(parent_students.c.parent_id)
                    .filter(
                        parent_students.c.student_id.in_(child_sids),
                        parent_students.c.parent_id != user.id,
                    )
                    .all()
                )
                co_parent_uids = [r[0] for r in co_parent_ids]
                if co_parent_uids and course.created_by_user_id in co_parent_uids:
                    return True

        return False
