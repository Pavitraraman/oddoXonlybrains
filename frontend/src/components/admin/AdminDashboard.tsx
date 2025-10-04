import React from 'react';
import { useQuery } from 'react-query';
import styled from 'styled-components';
import {
  Users,
  DollarSign,
  FileText,
  TrendingUp,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle
} from 'lucide-react';
import axios from 'axios';

const DashboardContainer = styled.div`
  max-width: 1200px;
  margin: 0 auto;
`;

const WelcomeSection = styled.div`
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 2rem;
  border-radius: 12px;
  margin-bottom: 2rem;
`;

const WelcomeTitle = styled.h1`
  font-size: 2rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
`;

const WelcomeSubtitle = styled.p`
  font-size: 1.125rem;
  opacity: 0.9;
`;

const StatsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1.5rem;
  margin-bottom: 2rem;
`;

const StatCard = styled.div`
  background: white;
  padding: 1.5rem;
  border-radius: 12px;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
  border: 1px solid #e5e7eb;
`;

const StatHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
`;

const StatIcon = styled.div<{ color: string }>`
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: ${props => props.color};
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
`;

const StatValue = styled.div`
  font-size: 2rem;
  font-weight: 700;
  color: #1f2937;
  margin-bottom: 0.25rem;
`;

const StatLabel = styled.div`
  color: #6b7280;
  font-size: 0.875rem;
`;

const StatChange = styled.div<{ positive?: boolean }>`
  font-size: 0.875rem;
  color: ${props => props.positive ? '#10b981' : '#ef4444'};
  font-weight: 500;
`;

const RecentActivity = styled.div`
  background: white;
  border-radius: 12px;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
  border: 1px solid #e5e7eb;
`;

const SectionHeader = styled.div`
  padding: 1.5rem 1.5rem 0;
  border-bottom: 1px solid #e5e7eb;
  margin-bottom: 1rem;
`;

const SectionTitle = styled.h2`
  font-size: 1.25rem;
  font-weight: 600;
  color: #1f2937;
`;

const ActivityList = styled.div`
  padding: 0 1.5rem 1.5rem;
`;

const ActivityItem = styled.div`
  display: flex;
  align-items: center;
  padding: 1rem 0;
  border-bottom: 1px solid #f3f4f6;
  
  &:last-child {
    border-bottom: none;
  }
`;

const ActivityIcon = styled.div<{ type: string }>`
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: ${props => {
    switch (props.type) {
      case 'expense': return '#eff6ff';
      case 'approval': return '#f0fdf4';
      case 'user': return '#fef3c7';
      default: return '#f3f4f6';
    }
  }};
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 1rem;
  color: ${props => {
    switch (props.type) {
      case 'expense': return '#3b82f6';
      case 'approval': return '#10b981';
      case 'user': return '#f59e0b';
      default: return '#6b7280';
    }
  }};
`;

const ActivityContent = styled.div`
  flex: 1;
`;

const ActivityTitle = styled.div`
  font-weight: 500;
  color: #1f2937;
  margin-bottom: 0.25rem;
`;

const ActivityDescription = styled.div`
  color: #6b7280;
  font-size: 0.875rem;
`;

const ActivityTime = styled.div`
  color: #9ca3af;
  font-size: 0.75rem;
`;

const LoadingSpinner = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  height: 200px;
  font-size: 1.125rem;
  color: #6b7280;
`;

const AdminDashboard: React.FC = () => {
  // Fetch dashboard statistics
  const { data: stats, isLoading: statsLoading } = useQuery(
    'admin-dashboard-stats',
    async () => {
      const response = await axios.get('/admin/dashboard/stats');
      return response.data;
    }
  );

  // Fetch recent activity
  const { data: activities, isLoading: activitiesLoading } = useQuery(
    'admin-recent-activity',
    async () => {
      const response = await axios.get('/admin/dashboard/activity');
      return response.data;
    }
  );

  if (statsLoading || activitiesLoading) {
    return (
      <DashboardContainer>
        <LoadingSpinner>Loading dashboard...</LoadingSpinner>
      </DashboardContainer>
    );
  }

  const statCards = [
    {
      icon: Users,
      color: '#3b82f6',
      value: stats?.totalUsers || 0,
      label: 'Total Users',
      change: '+12%'
    },
    {
      icon: DollarSign,
      color: '#10b981',
      value: `$${stats?.totalExpenses?.toLocaleString() || 0}`,
      label: 'Total Expenses',
      change: '+8%'
    },
    {
      icon: FileText,
      color: '#f59e0b',
      value: stats?.pendingApprovals || 0,
      label: 'Pending Approvals',
      change: '-5%'
    },
    {
      icon: TrendingUp,
      color: '#8b5cf6',
      value: `$${stats?.monthlySavings?.toLocaleString() || 0}`,
      label: 'Monthly Savings',
      change: '+15%'
    }
  ];

  return (
    <DashboardContainer>
      <WelcomeSection>
        <WelcomeTitle>Welcome back, Admin!</WelcomeTitle>
        <WelcomeSubtitle>
          Here's what's happening with your expense management system today.
        </WelcomeSubtitle>
      </WelcomeSection>

      <StatsGrid>
        {statCards.map((stat, index) => (
          <StatCard key={index}>
            <StatHeader>
              <StatIcon color={stat.color}>
                <stat.icon size={24} />
              </StatIcon>
              <StatChange positive={!stat.label.includes('Pending')}>
                {stat.change}
              </StatChange>
            </StatHeader>
            <StatValue>{stat.value}</StatValue>
            <StatLabel>{stat.label}</StatLabel>
          </StatCard>
        ))}
      </StatsGrid>

      <RecentActivity>
        <SectionHeader>
          <SectionTitle>Recent Activity</SectionTitle>
        </SectionHeader>
        <ActivityList>
          {activities?.map((activity: any, index: number) => (
            <ActivityItem key={index}>
              <ActivityIcon type={activity.type}>
                {activity.type === 'expense' && <DollarSign size={20} />}
                {activity.type === 'approval' && <CheckCircle size={20} />}
                {activity.type === 'user' && <Users size={20} />}
              </ActivityIcon>
              <ActivityContent>
                <ActivityTitle>{activity.title}</ActivityTitle>
                <ActivityDescription>{activity.description}</ActivityDescription>
              </ActivityContent>
              <ActivityTime>{activity.time}</ActivityTime>
            </ActivityItem>
          ))}
        </ActivityList>
      </RecentActivity>
    </DashboardContainer>
  );
};

export default AdminDashboard;

