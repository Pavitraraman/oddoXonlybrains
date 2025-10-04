import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import styled from 'styled-components';
import { 
  CheckCircle, XCircle, Clock, DollarSign, User, Calendar, 
  MessageSquare, AlertTriangle, Eye, Filter
} from 'lucide-react';
import { toast } from 'react-toastify';
import axios from 'axios';

const Container = styled.div`
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
`;

const Header = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
`;

const Title = styled.h1`
  font-size: 2rem;
  font-weight: 700;
  color: #1f2937;
`;

const FilterBar = styled.div`
  display: flex;
  gap: 1rem;
  margin-bottom: 2rem;
  padding: 1rem;
  background: white;
  border-radius: 8px;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
`;

const FilterSelect = styled.select`
  padding: 0.5rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: white;
`;

const ApprovalsGrid = styled.div`
  display: grid;
  gap: 1.5rem;
`;

const ApprovalCard = styled.div`
  background: white;
  border-radius: 12px;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
  overflow: hidden;
  transition: transform 0.2s ease-in-out;
  
  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  }
`;

const CardHeader = styled.div`
  padding: 1.5rem;
  border-bottom: 1px solid #e5e7eb;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
`;

const CardTitle = styled.h3`
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
`;

const CardSubtitle = styled.p`
  opacity: 0.9;
  font-size: 0.875rem;
`;

const CardBody = styled.div`
  padding: 1.5rem;
`;

const InfoGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
`;

const InfoItem = styled.div`
  display: flex;
  align-items: center;
  gap: 0.5rem;
`;

const InfoIcon = styled.div`
  color: #6b7280;
`;

const InfoLabel = styled.span`
  font-size: 0.875rem;
  color: #6b7280;
`;

const InfoValue = styled.span`
  font-weight: 500;
  color: #1f2937;
`;

const AmountDisplay = styled.div`
  font-size: 1.5rem;
  font-weight: 700;
  color: #059669;
  margin-bottom: 1rem;
`;

const StatusBadge = styled.span<{ status: string }>`
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
  
  ${props => {
    switch (props.status) {
      case 'pending':
        return `
          background: #fef3c7;
          color: #92400e;
        `;
      case 'overdue':
        return `
          background: #fee2e2;
          color: #991b1b;
        `;
      default:
        return `
          background: #f3f4f6;
          color: #374151;
        `;
    }
  }}
`;

const ActionButtons = styled.div`
  display: flex;
  gap: 1rem;
  margin-top: 1.5rem;
`;

const Button = styled.button<{ variant: 'approve' | 'reject' | 'view' }>`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease-in-out;
  border: none;
  
  ${props => {
    switch (props.variant) {
      case 'approve':
        return `
          background: #10b981;
          color: white;
          
          &:hover:not(:disabled) {
            background: #059669;
            transform: translateY(-1px);
          }
        `;
      case 'reject':
        return `
          background: #ef4444;
          color: white;
          
          &:hover:not(:disabled) {
            background: #dc2626;
            transform: translateY(-1px);
          }
        `;
      case 'view':
        return `
          background: #f3f4f6;
          color: #374151;
          
          &:hover:not(:disabled) {
            background: #e5e7eb;
          }
        `;
    }
  }}
  
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
`;

const CommentsSection = styled.div`
  margin-top: 1rem;
`;

const CommentsLabel = styled.label`
  display: block;
  font-weight: 600;
  color: #374151;
  margin-bottom: 0.5rem;
`;

const CommentsTextarea = styled.textarea`
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 0.875rem;
  resize: vertical;
  min-height: 80px;
  
  &:focus {
    outline: none;
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  }
`;

const EmptyState = styled.div`
  text-align: center;
  padding: 4rem 2rem;
  color: #6b7280;
`;

const LoadingSpinner = styled.div`
  display: inline-block;
  width: 1rem;
  height: 1rem;
  border: 2px solid #ffffff;
  border-radius: 50%;
  border-top-color: transparent;
  animation: spin 1s ease-in-out infinite;
  margin-right: 0.5rem;
  
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
`;

const BulkActions = styled.div`
  display: flex;
  gap: 1rem;
  margin-bottom: 2rem;
  padding: 1rem;
  background: #f9fafb;
  border-radius: 8px;
  align-items: center;
`;

const Checkbox = styled.input`
  margin-right: 0.5rem;
`;

interface Approval {
  id: string;
  expense_id: string;
  approver_id: string;
  status: 'pending' | 'approved' | 'rejected';
  comments?: string;
  created_at: string;
  expense: {
    id: string;
    description: string;
    amount: number;
    currency: string;
    amount_in_base_currency: number;
    expense_date: string;
    paid_by: string;
    user: {
      first_name: string;
      last_name: string;
      email: string;
    };
    category: {
      name: string;
    };
  };
}

const PendingApprovals: React.FC = () => {
  const [selectedApprovals, setSelectedApprovals] = useState<string[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [comments, setComments] = useState<{ [key: string]: string }>({});
  
  const queryClient = useQueryClient();

  // Fetch pending approvals
  const { data: approvalsData, isLoading } = useQuery(
    ['pending-approvals', statusFilter],
    async () => {
      const response = await axios.get('/approvals/pending', {
        params: { status: statusFilter }
      });
      return response.data;
    }
  );

  // Approve expense mutation
  const approveMutation = useMutation(
    async ({ approvalId, comments: approvalComments }: { approvalId: string; comments?: string }) => {
      const response = await axios.post(`/approvals/${approvalId}/approve`, {
        comments: approvalComments
      });
      return response.data;
    },
    {
      onSuccess: () => {
        toast.success('Expense approved successfully!');
        queryClient.invalidateQueries('pending-approvals');
        setComments({});
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || 'Failed to approve expense');
      }
    }
  );

  // Reject expense mutation
  const rejectMutation = useMutation(
    async ({ approvalId, comments: rejectionComments }: { approvalId: string; comments?: string }) => {
      const response = await axios.post(`/approvals/${approvalId}/reject`, {
        comments: rejectionComments
      });
      return response.data;
    },
    {
      onSuccess: () => {
        toast.success('Expense rejected');
        queryClient.invalidateQueries('pending-approvals');
        setComments({});
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || 'Failed to reject expense');
      }
    }
  );

  // Bulk approve mutation
  const bulkApproveMutation = useMutation(
    async (approvalIds: string[]) => {
      const response = await axios.post('/approvals/bulk-approve', {
        approval_ids: approvalIds,
        comments: 'Bulk approved'
      });
      return response.data;
    },
    {
      onSuccess: (data) => {
        toast.success(`Bulk approved: ${data.successful}/${data.total} expenses`);
        queryClient.invalidateQueries('pending-approvals');
        setSelectedApprovals([]);
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || 'Failed to bulk approve expenses');
      }
    }
  );

  // Bulk reject mutation
  const bulkRejectMutation = useMutation(
    async (approvalIds: string[]) => {
      const response = await axios.post('/approvals/bulk-reject', {
        approval_ids: approvalIds,
        comments: 'Bulk rejected'
      });
      return response.data;
    },
    {
      onSuccess: (data) => {
        toast.success(`Bulk rejected: ${data.successful}/${data.total} expenses`);
        queryClient.invalidateQueries('pending-approvals');
        setSelectedApprovals([]);
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || 'Failed to bulk reject expenses');
      }
    }
  );

  const handleApprove = async (approvalId: string) => {
    const approvalComments = comments[approvalId] || '';
    await approveMutation.mutateAsync({ approvalId, comments: approvalComments });
  };

  const handleReject = async (approvalId: string) => {
    const rejectionComments = comments[approvalId] || '';
    await rejectMutation.mutateAsync({ approvalId, comments: rejectionComments });
  };

  const handleSelectApproval = (approvalId: string, checked: boolean) => {
    if (checked) {
      setSelectedApprovals([...selectedApprovals, approvalId]);
    } else {
      setSelectedApprovals(selectedApprovals.filter(id => id !== approvalId));
    }
  };

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedApprovals(approvalsData?.items?.map((approval: Approval) => approval.id) || []);
    } else {
      setSelectedApprovals([]);
    }
  };

  const handleBulkApprove = async () => {
    if (selectedApprovals.length === 0) return;
    await bulkApproveMutation.mutateAsync(selectedApprovals);
  };

  const handleBulkReject = async () => {
    if (selectedApprovals.length === 0) return;
    await bulkRejectMutation.mutateAsync(selectedApprovals);
  };

  const updateComments = (approvalId: string, value: string) => {
    setComments({ ...comments, [approvalId]: value });
  };

  const getDaysOverdue = (createdAt: string) => {
    const created = new Date(createdAt);
    const now = new Date();
    const diffTime = Math.abs(now.getTime() - created.getTime());
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays > 3 ? diffDays : 0;
  };

  if (isLoading) {
    return (
      <Container>
        <div style={{ textAlign: 'center', padding: '4rem' }}>
          <LoadingSpinner />
          <p>Loading pending approvals...</p>
        </div>
      </Container>
    );
  }

  const approvals: Approval[] = approvalsData?.items || [];

  return (
    <Container>
      <Header>
        <Title>Pending Approvals</Title>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <span style={{ color: '#6b7280' }}>
            {approvals.length} pending approval{approvals.length !== 1 ? 's' : ''}
          </span>
        </div>
      </Header>

      <FilterBar>
        <FilterSelect value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="all">All Status</option>
          <option value="pending">Pending</option>
          <option value="overdue">Overdue</option>
        </FilterSelect>
      </FilterBar>

      {selectedApprovals.length > 0 && (
        <BulkActions>
          <span>{selectedApprovals.length} selected</span>
          <Button
            variant="approve"
            onClick={handleBulkApprove}
            disabled={bulkApproveMutation.isLoading}
          >
            {bulkApproveMutation.isLoading ? (
              <>
                <LoadingSpinner />
                Approving...
              </>
            ) : (
              <>
                <CheckCircle size={16} />
                Bulk Approve
              </>
            )}
          </Button>
          <Button
            variant="reject"
            onClick={handleBulkReject}
            disabled={bulkRejectMutation.isLoading}
          >
            {bulkRejectMutation.isLoading ? (
              <>
                <LoadingSpinner />
                Rejecting...
              </>
            ) : (
              <>
                <XCircle size={16} />
                Bulk Reject
              </>
            )}
          </Button>
        </BulkActions>
      )}

      {approvals.length === 0 ? (
        <EmptyState>
          <CheckCircle size={48} color="#10b981" style={{ marginBottom: '1rem' }} />
          <h3>No Pending Approvals</h3>
          <p>All caught up! There are no expenses waiting for your approval.</p>
        </EmptyState>
      ) : (
        <ApprovalsGrid>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1rem' }}>
            <Checkbox
              type="checkbox"
              checked={selectedApprovals.length === approvals.length}
              onChange={(e) => handleSelectAll(e.target.checked)}
            />
            <span>Select All</span>
          </div>
          
          {approvals.map((approval) => {
            const daysOverdue = getDaysOverdue(approval.created_at);
            
            return (
              <ApprovalCard key={approval.id}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem', padding: '1rem' }}>
                  <Checkbox
                    type="checkbox"
                    checked={selectedApprovals.includes(approval.id)}
                    onChange={(e) => handleSelectApproval(approval.id, e.target.checked)}
                  />
                  
                  <div style={{ flex: 1 }}>
                    <CardHeader>
                      <CardTitle>{approval.expense.description}</CardTitle>
                      <CardSubtitle>
                        {approval.expense.category.name} • Submitted by {approval.expense.user.first_name} {approval.expense.user.last_name}
                      </CardSubtitle>
                    </CardHeader>
                    
                    <CardBody>
                      <AmountDisplay>
                        {approval.expense.currency} {approval.expense.amount.toLocaleString()}
                        <span style={{ fontSize: '1rem', color: '#6b7280', marginLeft: '0.5rem' }}>
                          (Base: ${approval.expense.amount_in_base_currency.toLocaleString()})
                        </span>
                      </AmountDisplay>
                      
                      <InfoGrid>
                        <InfoItem>
                          <InfoIcon><Calendar size={16} /></InfoIcon>
                          <InfoLabel>Expense Date:</InfoLabel>
                          <InfoValue>{new Date(approval.expense.expense_date).toLocaleDateString()}</InfoValue>
                        </InfoItem>
                        
                        <InfoItem>
                          <InfoIcon><User size={16} /></InfoIcon>
                          <InfoLabel>Paid By:</InfoLabel>
                          <InfoValue>{approval.expense.paid_by}</InfoValue>
                        </InfoItem>
                        
                        <InfoItem>
                          <InfoIcon><Clock size={16} /></InfoIcon>
                          <InfoLabel>Submitted:</InfoLabel>
                          <InfoValue>{new Date(approval.created_at).toLocaleDateString()}</InfoValue>
                        </InfoItem>
                        
                        <InfoItem>
                          <InfoIcon><DollarSign size={16} /></InfoIcon>
                          <InfoLabel>Category:</InfoLabel>
                          <InfoValue>{approval.expense.category.name}</InfoValue>
                        </InfoItem>
                      </InfoGrid>
                      
                      {daysOverdue > 0 && (
                        <StatusBadge status="overdue">
                          <AlertTriangle size={12} />
                          {daysOverdue} days overdue
                        </StatusBadge>
                      )}
                      
                      <CommentsSection>
                        <CommentsLabel>
                          <MessageSquare size={16} style={{ marginRight: '0.5rem' }} />
                          Comments (Optional)
                        </CommentsLabel>
                        <CommentsTextarea
                          value={comments[approval.id] || ''}
                          onChange={(e) => updateComments(approval.id, e.target.value)}
                          placeholder="Add comments for this approval decision..."
                        />
                      </CommentsSection>
                      
                      <ActionButtons>
                        <Button
                          variant="approve"
                          onClick={() => handleApprove(approval.id)}
                          disabled={approveMutation.isLoading}
                        >
                          {approveMutation.isLoading ? (
                            <>
                              <LoadingSpinner />
                              Approving...
                            </>
                          ) : (
                            <>
                              <CheckCircle size={16} />
                              Approve
                            </>
                          )}
                        </Button>
                        
                        <Button
                          variant="reject"
                          onClick={() => handleReject(approval.id)}
                          disabled={rejectMutation.isLoading}
                        >
                          {rejectMutation.isLoading ? (
                            <>
                              <LoadingSpinner />
                              Rejecting...
                            </>
                          ) : (
                            <>
                              <XCircle size={16} />
                              Reject
                            </>
                          )}
                        </Button>
                        
                        <Button variant="view">
                          <Eye size={16} />
                          View Details
                        </Button>
                      </ActionButtons>
                    </CardBody>
                  </div>
                </div>
              </ApprovalCard>
            );
          })}
        </ApprovalsGrid>
      )}
    </Container>
  );
};

export default PendingApprovals;
