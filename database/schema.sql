-- Expense Management System Database Schema
-- Production-ready PostgreSQL schema with proper constraints and indexes

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create custom types/enums
CREATE TYPE user_role AS ENUM ('admin', 'manager', 'employee');
CREATE TYPE expense_status AS ENUM ('pending', 'approved', 'rejected', 'draft');
CREATE TYPE approval_type AS ENUM ('compulsory', 'necessary');
CREATE TYPE approval_status AS ENUM ('pending', 'approved', 'rejected');
CREATE TYPE notification_type AS ENUM ('invite', 'password_reset', 'expense_submitted', 'expense_approved', 'expense_rejected', 'overdue_approval');
CREATE TYPE audit_action AS ENUM ('create', 'update', 'delete', 'approve', 'reject', 'login', 'logout', 'password_change', 'invite_sent');

-- Companies table
CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    base_currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Users table with role-based access
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    role user_role NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    must_change_password BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id)
);

-- Expense categories (managed by admin)
CREATE TABLE expense_categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL REFERENCES users(id)
);

-- Approval rules (configurable per category)
CREATE TABLE approval_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    category_id UUID REFERENCES expense_categories(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    approval_type approval_type NOT NULL,
    is_sequential BOOLEAN DEFAULT FALSE, -- TRUE for sequential, FALSE for parallel
    order_index INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL REFERENCES users(id)
);

-- Expenses table
CREATE TABLE expenses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category_id UUID NOT NULL REFERENCES expense_categories(id),
    description TEXT NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    amount_in_base_currency DECIMAL(15,2) NOT NULL,
    exchange_rate DECIMAL(10,6) NOT NULL,
    exchange_rate_date DATE NOT NULL,
    expense_date DATE NOT NULL,
    paid_by VARCHAR(100) NOT NULL,
    remarks TEXT,
    receipt_url VARCHAR(500),
    status expense_status DEFAULT 'draft',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    submitted_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT positive_amount CHECK (amount > 0),
    CONSTRAINT positive_base_amount CHECK (amount_in_base_currency > 0)
);

-- Approvals table (tracks individual approval actions)
CREATE TABLE approvals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    expense_id UUID NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
    approver_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status approval_status DEFAULT 'pending',
    comments TEXT,
    approved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Currency exchange rates
CREATE TABLE currency_rates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    from_currency VARCHAR(3) NOT NULL,
    to_currency VARCHAR(3) NOT NULL,
    rate DECIMAL(10,6) NOT NULL,
    rate_date DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(from_currency, to_currency, rate_date)
);

-- OCR results for receipt processing
CREATE TABLE ocr_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    expense_id UUID REFERENCES expenses(id) ON DELETE CASCADE,
    receipt_url VARCHAR(500) NOT NULL,
    detected_amount DECIMAL(15,2),
    detected_currency VARCHAR(3),
    detected_date DATE,
    confidence_score DECIMAL(3,2),
    raw_text TEXT,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_verified BOOLEAN DEFAULT FALSE
);

-- Notifications table
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type notification_type NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP WITH TIME ZONE
);

-- Audit logs for all system actions
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action audit_action NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID,
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance optimization
CREATE INDEX idx_users_company_email ON users(company_id, email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_expenses_user_status ON expenses(user_id, status);
CREATE INDEX idx_expenses_company_date ON expenses(company_id, expense_date);
CREATE INDEX idx_expenses_category ON expenses(category_id);
CREATE INDEX idx_approvals_expense_status ON approvals(expense_id, status);
CREATE INDEX idx_approvals_approver ON approvals(approver_id, status);
CREATE INDEX idx_currency_rates_date ON currency_rates(rate_date);
CREATE INDEX idx_currency_rates_currencies ON currency_rates(from_currency, to_currency);
CREATE INDEX idx_notifications_user_unread ON notifications(user_id, is_read);
CREATE INDEX idx_audit_logs_company_date ON audit_logs(company_id, created_at);
CREATE INDEX idx_audit_logs_user_date ON audit_logs(user_id, created_at);
CREATE INDEX idx_approval_rules_category ON approval_rules(category_id);
CREATE INDEX idx_approval_rules_user ON approval_rules(user_id);

-- Create triggers for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_companies_updated_at BEFORE UPDATE ON companies FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_expenses_updated_at BEFORE UPDATE ON expenses FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_approvals_updated_at BEFORE UPDATE ON approvals FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert default currencies (ISO 4217 major currencies)
INSERT INTO currency_rates (from_currency, to_currency, rate, rate_date) VALUES
('USD', 'USD', 1.000000, CURRENT_DATE),
('EUR', 'USD', 1.050000, CURRENT_DATE),
('GBP', 'USD', 1.250000, CURRENT_DATE),
('JPY', 'USD', 0.007500, CURRENT_DATE),
('CAD', 'USD', 0.750000, CURRENT_DATE),
('AUD', 'USD', 0.650000, CURRENT_DATE),
('CHF', 'USD', 1.100000, CURRENT_DATE),
('CNY', 'USD', 0.140000, CURRENT_DATE),
('INR', 'USD', 0.012000, CURRENT_DATE),
('BRL', 'USD', 0.200000, CURRENT_DATE);

-- Create views for common queries
CREATE VIEW expense_summary AS
SELECT 
    e.id,
    e.company_id,
    e.user_id,
    u.first_name || ' ' || u.last_name as user_name,
    u.email as user_email,
    ec.name as category_name,
    e.description,
    e.amount,
    e.currency,
    e.amount_in_base_currency,
    e.status,
    e.expense_date,
    e.created_at,
    e.submitted_at
FROM expenses e
JOIN users u ON e.user_id = u.id
JOIN expense_categories ec ON e.category_id = ec.id;

CREATE VIEW pending_approvals AS
SELECT 
    a.id,
    a.expense_id,
    a.approver_id,
    u.first_name || ' ' || u.last_name as approver_name,
    es.user_name as submitter_name,
    es.category_name,
    es.description,
    es.amount,
    es.currency,
    es.amount_in_base_currency,
    es.expense_date,
    a.status,
    a.created_at,
    ar.approval_type,
    ar.order_index
FROM approvals a
JOIN users u ON a.approver_id = u.id
JOIN expense_summary es ON a.expense_id = es.id
LEFT JOIN approval_rules ar ON ar.user_id = a.approver_id AND ar.category_id = es.category_id
WHERE a.status = 'pending';

-- Create function for currency conversion
CREATE OR REPLACE FUNCTION convert_currency(
    amount DECIMAL,
    from_currency VARCHAR(3),
    to_currency VARCHAR(3),
    conversion_date DATE DEFAULT CURRENT_DATE
) RETURNS DECIMAL AS $$
DECLARE
    rate DECIMAL;
    result DECIMAL;
BEGIN
    -- If same currency, return original amount
    IF from_currency = to_currency THEN
        RETURN amount;
    END IF;
    
    -- Try to find exact rate for the date
    SELECT cr.rate INTO rate
    FROM currency_rates cr
    WHERE cr.from_currency = from_currency
    AND cr.to_currency = to_currency
    AND cr.rate_date = conversion_date;
    
    -- If not found, try to find the most recent rate before the date
    IF rate IS NULL THEN
        SELECT cr.rate INTO rate
        FROM currency_rates cr
        WHERE cr.from_currency = from_currency
        AND cr.to_currency = to_currency
        AND cr.rate_date <= conversion_date
        ORDER BY cr.rate_date DESC
        LIMIT 1;
    END IF;
    
    -- If still not found, try reverse rate
    IF rate IS NULL THEN
        SELECT (1.0 / cr.rate) INTO rate
        FROM currency_rates cr
        WHERE cr.from_currency = to_currency
        AND cr.to_currency = from_currency
        AND cr.rate_date <= conversion_date
        ORDER BY cr.rate_date DESC
        LIMIT 1;
    END IF;
    
    -- If still not found, return NULL
    IF rate IS NULL THEN
        RETURN NULL;
    END IF;
    
    result := amount * rate;
    RETURN ROUND(result, 2);
END;
$$ LANGUAGE plpgsql;

-- Create function to get approval status for an expense
CREATE OR REPLACE FUNCTION get_expense_approval_status(expense_uuid UUID)
RETURNS expense_status AS $$
DECLARE
    total_approvals INTEGER;
    compulsory_approvals INTEGER;
    necessary_approvals INTEGER;
    approved_compulsory INTEGER;
    approved_necessary INTEGER;
    rejected_compulsory INTEGER;
    rejected_necessary INTEGER;
BEGIN
    -- Count total approvals needed
    SELECT COUNT(*) INTO total_approvals
    FROM approvals a
    WHERE a.expense_id = expense_uuid;
    
    IF total_approvals = 0 THEN
        RETURN 'pending';
    END IF;
    
    -- Count compulsory approvals
    SELECT COUNT(*) INTO compulsory_approvals
    FROM approvals a
    JOIN approval_rules ar ON a.approver_id = ar.user_id
    JOIN expenses e ON a.expense_id = e.id
    WHERE a.expense_id = expense_uuid
    AND ar.approval_type = 'compulsory'
    AND ar.category_id = e.category_id;
    
    -- Count necessary approvals
    SELECT COUNT(*) INTO necessary_approvals
    FROM approvals a
    JOIN approval_rules ar ON a.approver_id = ar.user_id
    JOIN expenses e ON a.expense_id = e.id
    WHERE a.expense_id = expense_uuid
    AND ar.approval_type = 'necessary'
    AND ar.category_id = e.category_id;
    
    -- Count approved compulsory
    SELECT COUNT(*) INTO approved_compulsory
    FROM approvals a
    JOIN approval_rules ar ON a.approver_id = ar.user_id
    JOIN expenses e ON a.expense_id = e.id
    WHERE a.expense_id = expense_uuid
    AND ar.approval_type = 'compulsory'
    AND ar.category_id = e.category_id
    AND a.status = 'approved';
    
    -- Count approved necessary
    SELECT COUNT(*) INTO approved_necessary
    FROM approvals a
    JOIN approval_rules ar ON a.approver_id = ar.user_id
    JOIN expenses e ON a.expense_id = e.id
    WHERE a.expense_id = expense_uuid
    AND ar.approval_type = 'necessary'
    AND ar.category_id = e.category_id
    AND a.status = 'approved';
    
    -- Count rejected compulsory
    SELECT COUNT(*) INTO rejected_compulsory
    FROM approvals a
    JOIN approval_rules ar ON a.approver_id = ar.user_id
    JOIN expenses e ON a.expense_id = e.id
    WHERE a.expense_id = expense_uuid
    AND ar.approval_type = 'compulsory'
    AND ar.category_id = e.category_id
    AND a.status = 'rejected';
    
    -- Count rejected necessary
    SELECT COUNT(*) INTO rejected_necessary
    FROM approvals a
    JOIN approval_rules ar ON a.approver_id = ar.user_id
    JOIN expenses e ON a.expense_id = e.id
    WHERE a.expense_id = expense_uuid
    AND ar.approval_type = 'necessary'
    AND ar.category_id = e.category_id
    AND a.status = 'rejected';
    
    -- Check if any compulsory approval is rejected
    IF rejected_compulsory > 0 THEN
        RETURN 'rejected';
    END IF;
    
    -- Check if all compulsory approvals are approved
    IF approved_compulsory < compulsory_approvals THEN
        RETURN 'pending';
    END IF;
    
    -- Check necessary approvals (60% rule)
    IF necessary_approvals > 0 THEN
        DECLARE
            necessary_approval_rate DECIMAL;
        BEGIN
            necessary_approval_rate := (approved_necessary::DECIMAL / necessary_approvals::DECIMAL) * 100;
            
            IF necessary_approval_rate < 60 THEN
                RETURN 'rejected';
            END IF;
        END;
    END IF;
    
    -- If we reach here, expense is approved
    RETURN 'approved';
END;
$$ LANGUAGE plpgsql;

