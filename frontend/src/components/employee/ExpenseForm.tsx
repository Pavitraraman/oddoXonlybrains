import React, { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery } from 'react-query';
import styled from 'styled-components';
import { useDropzone } from 'react-dropzone';
import { Upload, X, Eye, EyeOff, DollarSign, Calendar, FileText, AlertCircle } from 'lucide-react';
import { toast } from 'react-toastify';
import axios from 'axios';

const FormContainer = styled.div`
  max-width: 800px;
  margin: 0 auto;
  padding: 2rem;
`;

const FormTitle = styled.h1`
  font-size: 2rem;
  font-weight: 700;
  color: #1f2937;
  margin-bottom: 2rem;
  text-align: center;
`;

const Form = styled.form`
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  padding: 2rem;
`;

const FormGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1.5rem;
  margin-bottom: 2rem;
`;

const FormGroup = styled.div`
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
`;

const Label = styled.label`
  font-weight: 600;
  color: #374151;
  font-size: 0.875rem;
`;

const Input = styled.input<{ hasError?: boolean }>`
  padding: 0.75rem;
  border: 1px solid ${props => props.hasError ? '#ef4444' : '#d1d5db'};
  border-radius: 8px;
  font-size: 1rem;
  transition: border-color 0.2s ease-in-out;
  
  &:focus {
    outline: none;
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  }
`;

const TextArea = styled.textarea<{ hasError?: boolean }>`
  padding: 0.75rem;
  border: 1px solid ${props => props.hasError ? '#ef4444' : '#d1d5db'};
  border-radius: 8px;
  font-size: 1rem;
  resize: vertical;
  min-height: 100px;
  transition: border-color 0.2s ease-in-out;
  
  &:focus {
    outline: none;
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  }
`;

const Select = styled.select<{ hasError?: boolean }>`
  padding: 0.75rem;
  border: 1px solid ${props => props.hasError ? '#ef4444' : '#d1d5db'};
  border-radius: 8px;
  font-size: 1rem;
  background: white;
  
  &:focus {
    outline: none;
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  }
`;

const ErrorMessage = styled.span`
  color: #ef4444;
  font-size: 0.875rem;
  margin-top: 0.25rem;
`;

const FileUploadArea = styled.div<{ isDragActive: boolean }>`
  border: 2px dashed ${props => props.isDragActive ? '#3b82f6' : '#d1d5db'};
  border-radius: 8px;
  padding: 2rem;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease-in-out;
  background: ${props => props.isDragActive ? '#eff6ff' : '#f9fafb'};
  
  &:hover {
    border-color: #3b82f6;
    background: #eff6ff;
  }
`;

const FilePreview = styled.div`
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  background: #f3f4f6;
  border-radius: 8px;
  margin-top: 1rem;
`;

const FileInfo = styled.div`
  flex: 1;
`;

const FileName = styled.div`
  font-weight: 500;
  color: #1f2937;
`;

const FileSize = styled.div`
  font-size: 0.875rem;
  color: #6b7280;
`;

const RemoveFileButton = styled.button`
  background: #ef4444;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 0.5rem;
  cursor: pointer;
  
  &:hover {
    background: #dc2626;
  }
`;

const OCRResults = styled.div`
  background: #f0f9ff;
  border: 1px solid #0ea5e9;
  border-radius: 8px;
  padding: 1rem;
  margin-top: 1rem;
`;

const OCRTitle = styled.h3`
  font-weight: 600;
  color: #0369a1;
  margin-bottom: 0.5rem;
`;

const OCRItem = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
`;

const OCRLabel = styled.span`
  font-weight: 500;
  color: #374151;
`;

const OCRValue = styled.span`
  color: #059669;
  font-weight: 600;
`;

const ButtonGroup = styled.div`
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
  margin-top: 2rem;
`;

const Button = styled.button<{ variant?: 'primary' | 'secondary' }>`
  padding: 0.75rem 1.5rem;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease-in-out;
  
  ${props => props.variant === 'primary' ? `
    background: #3b82f6;
    color: white;
    border: none;
    
    &:hover:not(:disabled) {
      background: #2563eb;
      transform: translateY(-1px);
    }
  ` : `
    background: white;
    color: #374151;
    border: 1px solid #d1d5db;
    
    &:hover:not(:disabled) {
      background: #f9fafb;
      border-color: #9ca3af;
    }
  `}
  
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
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

interface ExpenseFormData {
  category_id: string;
  description: string;
  amount: number;
  currency: string;
  expense_date: string;
  paid_by: string;
  remarks?: string;
}

interface OCRResult {
  detected_amount?: number;
  detected_currency?: string;
  detected_date?: string;
  confidence_score?: number;
  raw_text?: string;
}

const ExpenseForm: React.FC = () => {
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [ocrResult, setOcrResult] = useState<OCRResult | null>(null);
  const [isProcessingOCR, setIsProcessingOCR] = useState(false);
  
  const {
    register,
    handleSubmit,
    formState: { errors },
    setValue,
    watch,
    reset
  } = useForm<ExpenseFormData>();

  // Fetch expense categories
  const { data: categories } = useQuery(
    'expense-categories',
    async () => {
      const response = await axios.get('/expense-categories');
      return response.data;
    }
  );

  // Create expense mutation
  const createExpenseMutation = useMutation(
    async (data: ExpenseFormData) => {
      const response = await axios.post('/expenses', data);
      return response.data;
    },
    {
      onSuccess: () => {
        toast.success('Expense created successfully!');
        reset();
        setUploadedFile(null);
        setOcrResult(null);
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || 'Failed to create expense');
      }
    }
  );

  // Submit expense mutation
  const submitExpenseMutation = useMutation(
    async (expenseId: string) => {
      const response = await axios.post(`/expenses/${expenseId}/submit`);
      return response.data;
    },
    {
      onSuccess: () => {
        toast.success('Expense submitted for approval!');
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || 'Failed to submit expense');
      }
    }
  );

  // File drop handler
  const onDrop = async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    setUploadedFile(file);
    
    // Process OCR
    setIsProcessingOCR(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await axios.post('/ocr/process', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      const ocrData = response.data.data;
      setOcrResult(ocrData);
      
      // Auto-fill form with OCR results
      if (ocrData.detected_amount) {
        setValue('amount', ocrData.detected_amount);
      }
      if (ocrData.detected_currency) {
        setValue('currency', ocrData.detected_currency);
      }
      if (ocrData.detected_date) {
        setValue('expense_date', ocrData.detected_date);
      }
      
      toast.success('Receipt processed successfully!');
    } catch (error) {
      toast.error('Failed to process receipt');
    } finally {
      setIsProcessingOCR(false);
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.jpeg', '.jpg', '.png'],
      'application/pdf': ['.pdf']
    },
    maxFiles: 1
  });

  const removeFile = () => {
    setUploadedFile(null);
    setOcrResult(null);
  };

  const onSubmit = async (data: ExpenseFormData) => {
    try {
      const expense = await createExpenseMutation.mutateAsync(data);
      
      // Ask user if they want to submit immediately
      const shouldSubmit = window.confirm(
        'Expense created successfully! Would you like to submit it for approval now?'
      );
      
      if (shouldSubmit) {
        await submitExpenseMutation.mutateAsync(expense.id);
      }
    } catch (error) {
      // Error is handled by mutation
    }
  };

  const onSaveDraft = async (data: ExpenseFormData) => {
    try {
      await createExpenseMutation.mutateAsync(data);
    } catch (error) {
      // Error is handled by mutation
    }
  };

  return (
    <FormContainer>
      <FormTitle>Submit New Expense</FormTitle>
      
      <Form onSubmit={handleSubmit(onSubmit)}>
        <FormGrid>
          <FormGroup>
            <Label htmlFor="category_id">Category *</Label>
            <Select
              id="category_id"
              hasError={!!errors.category_id}
              {...register('category_id', { required: 'Category is required' })}
            >
              <option value="">Select a category</option>
              {categories?.map((category: any) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </Select>
            {errors.category_id && (
              <ErrorMessage>{errors.category_id.message}</ErrorMessage>
            )}
          </FormGroup>

          <FormGroup>
            <Label htmlFor="description">Description *</Label>
            <TextArea
              id="description"
              hasError={!!errors.description}
              placeholder="Enter expense description"
              {...register('description', { required: 'Description is required' })}
            />
            {errors.description && (
              <ErrorMessage>{errors.description.message}</ErrorMessage>
            )}
          </FormGroup>

          <FormGroup>
            <Label htmlFor="amount">Amount *</Label>
            <Input
              id="amount"
              type="number"
              step="0.01"
              hasError={!!errors.amount}
              placeholder="0.00"
              {...register('amount', { 
                required: 'Amount is required',
                min: { value: 0.01, message: 'Amount must be greater than 0' }
              })}
            />
            {errors.amount && (
              <ErrorMessage>{errors.amount.message}</ErrorMessage>
            )}
          </FormGroup>

          <FormGroup>
            <Label htmlFor="currency">Currency *</Label>
            <Select
              id="currency"
              hasError={!!errors.currency}
              {...register('currency', { required: 'Currency is required' })}
            >
              <option value="">Select currency</option>
              <option value="USD">USD - US Dollar</option>
              <option value="EUR">EUR - Euro</option>
              <option value="GBP">GBP - British Pound</option>
              <option value="JPY">JPY - Japanese Yen</option>
              <option value="CAD">CAD - Canadian Dollar</option>
              <option value="AUD">AUD - Australian Dollar</option>
            </Select>
            {errors.currency && (
              <ErrorMessage>{errors.currency.message}</ErrorMessage>
            )}
          </FormGroup>

          <FormGroup>
            <Label htmlFor="expense_date">Expense Date *</Label>
            <Input
              id="expense_date"
              type="date"
              hasError={!!errors.expense_date}
              {...register('expense_date', { required: 'Expense date is required' })}
            />
            {errors.expense_date && (
              <ErrorMessage>{errors.expense_date.message}</ErrorMessage>
            )}
          </FormGroup>

          <FormGroup>
            <Label htmlFor="paid_by">Paid By *</Label>
            <Input
              id="paid_by"
              hasError={!!errors.paid_by}
              placeholder="Who paid for this expense?"
              {...register('paid_by', { required: 'Paid by is required' })}
            />
            {errors.paid_by && (
              <ErrorMessage>{errors.paid_by.message}</ErrorMessage>
            )}
          </FormGroup>
        </FormGrid>

        <FormGroup>
          <Label htmlFor="remarks">Remarks</Label>
          <TextArea
            id="remarks"
            hasError={!!errors.remarks}
            placeholder="Additional notes or comments"
            {...register('remarks')}
          />
        </FormGroup>

        <FormGroup>
          <Label>Receipt Upload</Label>
          <FileUploadArea {...getRootProps()} isDragActive={isDragActive}>
            <input {...getInputProps()} />
            <Upload size={48} color="#6b7280" />
            <div style={{ marginTop: '1rem' }}>
              {isDragActive ? (
                <p>Drop the receipt here...</p>
              ) : (
                <div>
                  <p>Drag & drop a receipt here, or click to select</p>
                  <p style={{ fontSize: '0.875rem', color: '#6b7280' }}>
                    Supports JPG, PNG, PDF (max 10MB)
                  </p>
                </div>
              )}
            </div>
          </FileUploadArea>

          {uploadedFile && (
            <FilePreview>
              <FileInfo>
                <FileName>{uploadedFile.name}</FileName>
                <FileSize>{(uploadedFile.size / 1024 / 1024).toFixed(2)} MB</FileSize>
              </FileInfo>
              <RemoveFileButton onClick={removeFile}>
                <X size={16} />
              </RemoveFileButton>
            </FilePreview>
          )}

          {isProcessingOCR && (
            <div style={{ textAlign: 'center', padding: '1rem' }}>
              <LoadingSpinner />
              Processing receipt with OCR...
            </div>
          )}

          {ocrResult && (
            <OCRResults>
              <OCRTitle>OCR Results</OCRTitle>
              {ocrResult.detected_amount && (
                <OCRItem>
                  <OCRLabel>Detected Amount:</OCRLabel>
                  <OCRValue>${ocrResult.detected_amount}</OCRValue>
                </OCRItem>
              )}
              {ocrResult.detected_currency && (
                <OCRItem>
                  <OCRLabel>Detected Currency:</OCRLabel>
                  <OCRValue>{ocrResult.detected_currency}</OCRValue>
                </OCRItem>
              )}
              {ocrResult.detected_date && (
                <OCRItem>
                  <OCRLabel>Detected Date:</OCRLabel>
                  <OCRValue>{ocrResult.detected_date}</OCRValue>
                </OCRItem>
              )}
              {ocrResult.confidence_score && (
                <OCRItem>
                  <OCRLabel>Confidence Score:</OCRLabel>
                  <OCRValue>{(ocrResult.confidence_score * 100).toFixed(1)}%</OCRValue>
                </OCRItem>
              )}
            </OCRResults>
          )}
        </FormGroup>

        <ButtonGroup>
          <Button
            type="button"
            variant="secondary"
            onClick={handleSubmit(onSaveDraft)}
            disabled={createExpenseMutation.isLoading}
          >
            {createExpenseMutation.isLoading ? (
              <>
                <LoadingSpinner />
                Saving...
              </>
            ) : (
              'Save as Draft'
            )}
          </Button>
          
          <Button
            type="submit"
            variant="primary"
            disabled={createExpenseMutation.isLoading || submitExpenseMutation.isLoading}
          >
            {createExpenseMutation.isLoading || submitExpenseMutation.isLoading ? (
              <>
                <LoadingSpinner />
                {createExpenseMutation.isLoading ? 'Creating...' : 'Submitting...'}
              </>
            ) : (
              'Create & Submit'
            )}
          </Button>
        </ButtonGroup>
      </Form>
    </FormContainer>
  );
};

export default ExpenseForm;
