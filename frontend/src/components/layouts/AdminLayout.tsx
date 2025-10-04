import React, { useState } from 'react';
import { Routes, Route, Navigate, Outlet } from 'react-router-dom';
import styled from 'styled-components';
import {
  LayoutDashboard,
  Users,
  Building2,
  Tag,
  Settings,
  FileText,
  BarChart3,
  Menu,
  X,
  LogOut,
  Bell,
  User
} from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

const LayoutContainer = styled.div`
  display: flex;
  min-height: 100vh;
  background-color: #f8fafc;
`;

const Sidebar = styled.aside<{ isOpen: boolean }>`
  width: ${props => props.isOpen ? '280px' : '0'};
  background: white;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
  transition: width 0.3s ease-in-out;
  overflow: hidden;
  position: fixed;
  top: 0;
  left: 0;
  height: 100vh;
  z-index: 1000;
  
  @media (min-width: 768px) {
    position: relative;
    width: 280px;
    transform: none;
  }
`;

const SidebarHeader = styled.div`
  padding: 1.5rem;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

const Logo = styled.div`
  font-size: 1.25rem;
  font-weight: 700;
  color: #1f2937;
`;

const CloseButton = styled.button`
  display: block;
  background: none;
  border: none;
  color: #6b7280;
  cursor: pointer;
  
  @media (min-width: 768px) {
    display: none;
  }
`;

const Navigation = styled.nav`
  padding: 1rem 0;
`;

const NavItem = styled.div<{ active?: boolean }>`
  display: flex;
  align-items: center;
  padding: 0.75rem 1.5rem;
  color: ${props => props.active ? '#3b82f6' : '#6b7280'};
  background-color: ${props => props.active ? '#eff6ff' : 'transparent'};
  border-right: 3px solid ${props => props.active ? '#3b82f6' : 'transparent'};
  transition: all 0.2s ease-in-out;
  cursor: pointer;
  
  &:hover {
    background-color: #f3f4f6;
    color: #374151;
  }
  
  svg {
    margin-right: 0.75rem;
    width: 20px;
    height: 20px;
  }
`;

const MainContent = styled.main`
  flex: 1;
  display: flex;
  flex-direction: column;
  margin-left: 0;
  
  @media (min-width: 768px) {
    margin-left: 280px;
  }
`;

const Header = styled.header`
  background: white;
  border-bottom: 1px solid #e5e7eb;
  padding: 1rem 1.5rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
`;

const HeaderLeft = styled.div`
  display: flex;
  align-items: center;
  gap: 1rem;
`;

const MenuButton = styled.button`
  display: block;
  background: none;
  border: none;
  color: #6b7280;
  cursor: pointer;
  
  @media (min-width: 768px) {
    display: none;
  }
`;

const HeaderRight = styled.div`
  display: flex;
  align-items: center;
  gap: 1rem;
`;

const NotificationButton = styled.button`
  position: relative;
  background: none;
  border: none;
  color: #6b7280;
  cursor: pointer;
  padding: 0.5rem;
  border-radius: 6px;
  
  &:hover {
    background-color: #f3f4f6;
  }
`;

const NotificationBadge = styled.span`
  position: absolute;
  top: 0;
  right: 0;
  background: #ef4444;
  color: white;
  border-radius: 50%;
  width: 18px;
  height: 18px;
  font-size: 0.75rem;
  display: flex;
  align-items: center;
  justify-content: center;
`;

const UserMenu = styled.div`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  padding: 0.5rem;
  border-radius: 6px;
  transition: background-color 0.2s ease-in-out;
  
  &:hover {
    background-color: #f3f4f6;
  }
`;

const UserInfo = styled.div`
  display: flex;
  flex-direction: column;
  align-items: flex-end;
`;

const UserName = styled.span`
  font-weight: 500;
  color: #1f2937;
  font-size: 0.875rem;
`;

const UserRole = styled.span`
  color: #6b7280;
  font-size: 0.75rem;
`;

const Content = styled.div`
  flex: 1;
  padding: 1.5rem;
`;

const Overlay = styled.div<{ isOpen: boolean }>`
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 999;
  display: ${props => props.isOpen ? 'block' : 'none'};
  
  @media (min-width: 768px) {
    display: none;
  }
`;

const AdminLayout: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { user, logout } = useAuth();

  const navigationItems = [
    { path: '/admin', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/admin/users', icon: Users, label: 'User Management' },
    { path: '/admin/company', icon: Building2, label: 'Company Settings' },
    { path: '/admin/categories', icon: Tag, label: 'Categories' },
    { path: '/admin/approval-rules', icon: Settings, label: 'Approval Rules' },
    { path: '/admin/audit-logs', icon: FileText, label: 'Audit Logs' },
    { path: '/admin/reports', icon: BarChart3, label: 'Reports' },
  ];

  const handleLogout = () => {
    logout();
  };

  return (
    <LayoutContainer>
      <Overlay isOpen={sidebarOpen} onClick={() => setSidebarOpen(false)} />
      
      <Sidebar isOpen={sidebarOpen}>
        <SidebarHeader>
          <Logo>Expense Manager</Logo>
          <CloseButton onClick={() => setSidebarOpen(false)}>
            <X size={24} />
          </CloseButton>
        </SidebarHeader>
        
        <Navigation>
          {navigationItems.map((item) => (
            <NavItem
              key={item.path}
              active={window.location.pathname === item.path}
              onClick={() => {
                setSidebarOpen(false);
                window.location.href = item.path;
              }}
            >
              <item.icon />
              {item.label}
            </NavItem>
          ))}
        </Navigation>
      </Sidebar>

      <MainContent>
        <Header>
          <HeaderLeft>
            <MenuButton onClick={() => setSidebarOpen(true)}>
              <Menu size={24} />
            </MenuButton>
            <h1 style={{ fontSize: '1.5rem', fontWeight: '600', color: '#1f2937' }}>
              Admin Dashboard
            </h1>
          </HeaderLeft>
          
          <HeaderRight>
            <NotificationButton>
              <Bell size={20} />
              <NotificationBadge>3</NotificationBadge>
            </NotificationButton>
            
            <UserMenu onClick={handleLogout}>
              <UserInfo>
                <UserName>{user?.first_name} {user?.last_name}</UserName>
                <UserRole>Admin</UserRole>
              </UserInfo>
              <User size={20} />
              <LogOut size={20} />
            </UserMenu>
          </HeaderRight>
        </Header>

        <Content>
          <Outlet />
        </Content>
      </MainContent>
    </LayoutContainer>
  );
};

export default AdminLayout;

