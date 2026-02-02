import { useState, useEffect } from 'react';
import { adminApi } from '../api/client';
import type { AdminStats, AdminUserItem } from '../api/client';
import { DashboardLayout } from '../components/DashboardLayout';
import { useDebounce } from '../utils/useDebounce';
import './AdminDashboard.css';

const PAGE_SIZE = 10;

export function AdminDashboard() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [totalUsers, setTotalUsers] = useState(0);
  const [roleFilter, setRoleFilter] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const debouncedSearch = useDebounce(search, 400);

  useEffect(() => {
    loadStats();
  }, []);

  useEffect(() => {
    loadUsers();
  }, [roleFilter, debouncedSearch, page]);

  const loadStats = async () => {
    try {
      const data = await adminApi.getStats();
      setStats(data);
    } catch {
      // Failed to load stats
    }
  };

  const loadUsers = async () => {
    setLoading(true);
    try {
      const data = await adminApi.getUsers({
        role: roleFilter || undefined,
        search: debouncedSearch || undefined,
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      setUsers(data.users);
      setTotalUsers(data.total);
    } catch {
      // Failed to load users
    } finally {
      setLoading(false);
    }
  };

  const totalPages = Math.ceil(totalUsers / PAGE_SIZE);

  return (
    <DashboardLayout welcomeSubtitle="Platform administration">
      <div className="dashboard-grid">
        <div className="dashboard-card">
          <div className="card-icon">👥</div>
          <h3>Total Users</h3>
          <p className="card-value">{stats?.total_users ?? '—'}</p>
          <p className="card-label">Registered users</p>
        </div>

        <div className="dashboard-card">
          <div className="card-icon">🎓</div>
          <h3>Students</h3>
          <p className="card-value">{stats?.users_by_role?.student ?? 0}</p>
          <p className="card-label">Active students</p>
        </div>

        <div className="dashboard-card">
          <div className="card-icon">👨‍🏫</div>
          <h3>Teachers</h3>
          <p className="card-value">{stats?.users_by_role?.teacher ?? 0}</p>
          <p className="card-label">Active teachers</p>
        </div>

        <div className="dashboard-card">
          <div className="card-icon">📚</div>
          <h3>Courses</h3>
          <p className="card-value">{stats?.total_courses ?? 0}</p>
          <p className="card-label">Total courses</p>
        </div>
      </div>

      <div className="dashboard-sections">
        <section className="section admin-users-section">
          <h3>User Management</h3>

          <div className="admin-filters">
            <select
              value={roleFilter}
              onChange={(e) => { setRoleFilter(e.target.value); setPage(0); }}
            >
              <option value="">All Roles</option>
              <option value="student">Student</option>
              <option value="parent">Parent</option>
              <option value="teacher">Teacher</option>
              <option value="admin">Admin</option>
            </select>
            <input
              type="text"
              placeholder="Search by name or email..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(0); }}
            />
          </div>

          {loading ? (
            <div className="loading-state">Loading users...</div>
          ) : (
            <>
              <table className="admin-users-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr key={user.id}>
                      <td>{user.full_name}</td>
                      <td>{user.email}</td>
                      <td>
                        <span className={`role-badge-small ${user.role}`}>
                          {user.role}
                        </span>
                      </td>
                      <td>
                        <span className={`status-dot ${user.is_active ? 'active' : 'inactive'}`} />
                        {user.is_active ? 'Active' : 'Inactive'}
                      </td>
                      <td>{new Date(user.created_at).toLocaleDateString()}</td>
                    </tr>
                  ))}
                  {users.length === 0 && (
                    <tr>
                      <td colSpan={5} style={{ textAlign: 'center', padding: '24px', color: '#999' }}>
                        No users found
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>

              {totalPages > 1 && (
                <div className="admin-pagination">
                  <span>
                    Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, totalUsers)} of {totalUsers}
                  </span>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button disabled={page === 0} onClick={() => setPage(page - 1)}>
                      Previous
                    </button>
                    <button disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)}>
                      Next
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </DashboardLayout>
  );
}
