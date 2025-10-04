import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './contexts/AuthContext';

// Layout Components
import AdminLayout from './components/layouts/AdminLayout';
import ManagerLayout from './components/layouts/ManagerLayout';
import EmployeeLayout from './components/layouts/EmployeeLayout';

// Auth Components
import Login from './components/auth/Login';
import PasswordChange from './components/auth/PasswordChange';

// Admin Components
import AdminDashboard from './components/admin/AdminDashboard';
import UserManagement from './components/admin/UserManagement';
import CompanySettings from './components/admin/CompanySettings';
import CategoryManagement from './components/admin/CategoryManagement';
import ApprovalRules from './components/admin/ApprovalRules';
import AuditLogs from './components/admin/AuditLogs';
import Reports from './components/admin/Reports';

// Manager Components
import ManagerDashboard from './components/manager/ManagerDashboard';
import PendingApprovals from './components/manager/PendingApprovals';
import ApprovalHistory from './components/manager/ApprovalHistory';
import TeamReports from './components/manager/TeamReports';

// Employee Components
import EmployeeDashboard from './components/employee/EmployeeDashboard';
import ExpenseForm from './components/employee/ExpenseForm';
import ExpenseHistory from './components/employee/ExpenseHistory';

// Protected Route Component
import ProtectedRoute from './components/common/ProtectedRoute';

const App: React.FC = () => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        fontSize: '18px'
      }}>
        Loading...
      </div>
    );
  }

  return (
    <Routes>
      {/* Public Routes */}
      <Route path="/login" element={
        user ? <Navigate to="/" replace /> : <Login />
      } />

      {/* Protected Routes */}
      <Route path="/" element={
        <ProtectedRoute>
          {user?.role === 'admin' ? <AdminLayout /> :
           user?.role === 'manager' ? <ManagerLayout /> :
           <EmployeeLayout />}
        </ProtectedRoute>
      }>
        {/* Admin Routes */}
        <Route path="/admin/*" element={
          user?.role === 'admin' ? (
            <Routes>
              <Route index element={<AdminDashboard />} />
              <Route path="users" element={<UserManagement />} />
              <Route path="company" element={<CompanySettings />} />
              <Route path="categories" element={<CategoryManagement />} />
              <Route path="approval-rules" element={<ApprovalRules />} />
              <Route path="audit-logs" element={<AuditLogs />} />
              <Route path="reports" element={<Reports />} />
            </Routes>
          ) : <Navigate to="/" replace />
        } />

        {/* Manager Routes */}
        <Route path="/manager/*" element={
          user?.role === 'manager' ? (
            <Routes>
              <Route index element={<ManagerDashboard />} />
              <Route path="approvals" element={<PendingApprovals />} />
              <Route path="history" element={<ApprovalHistory />} />
              <Route path="reports" element={<TeamReports />} />
            </Routes>
          ) : <Navigate to="/" replace />
        } />

        {/* Employee Routes */}
        <Route path="/employee/*" element={
          user?.role === 'employee' ? (
            <Routes>
              <Route index element={<EmployeeDashboard />} />
              <Route path="submit" element={<ExpenseForm />} />
              <Route path="history" element={<ExpenseHistory />} />
            </Routes>
          ) : <Navigate to="/" replace />
        } />

        {/* Common Routes */}
        <Route path="/change-password" element={<PasswordChange />} />
      </Route>

      {/* Default redirect */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

export default App;

