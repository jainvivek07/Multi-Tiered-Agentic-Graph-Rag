import { useState, useEffect } from 'react';
import { Shield, User, Loader2, CheckCircle, XCircle } from 'lucide-react';
import { adminApi } from '../../../api/adminApi';
import styles from './UserManagement.module.css';

interface UserData {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export function UserManagement() {
  const [users, setUsers] = useState<UserData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const data = await adminApi.getUsers();
      setUsers(data);
    } catch (err) {
      console.error('Failed to load users', err);
    } finally {
      setLoading(false);
    }
  };

  const toggleActive = async (userId: string, currentStatus: boolean) => {
    try {
      const newStatus = !currentStatus;
      await adminApi.updateUserStatus(userId, newStatus);
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, is_active: newStatus } : u))
      );
    } catch (err) {
      console.error('Failed to update status', err);
    }
  };


  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.loading}>
          <Loader2 className={styles.spinner} size={24} />
          <span>Loading users...</span>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2>User Management</h2>
        <p>Manage system access and roles</p>
      </div>

      <div className={styles.tableWrapper}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Email</th>
              <th>Role</th>
              <th>Status</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id}>
                <td>{user.email}</td>
                <td>
                  <span
                    className={[
                      styles.roleBadge,
                      user.role === 'admin' ? styles.roleAdmin : styles.roleUser,
                    ].join(' ')}
                  >
                    {user.role === 'admin' ? <Shield size={14} /> : <User size={14} />}
                    {user.role}
                  </span>
                </td>
                <td>
                  <span
                    className={[
                      styles.statusBadge,
                      user.is_active ? styles.statusActive : styles.statusInactive,
                    ].join(' ')}
                  >
                    {user.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td>{new Date(user.created_at).toLocaleDateString()}</td>
                <td>
                  <button
                    className={styles.actionBtn}
                    onClick={() => toggleActive(user.id, user.is_active)}
                    title={user.is_active ? 'Deactivate User' : 'Activate User'}
                  >
                    {user.is_active ? <XCircle size={16} /> : <CheckCircle size={16} />}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
