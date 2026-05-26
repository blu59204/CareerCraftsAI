-- Migration: 0016_linkedin_outreach_queue
-- Creates the linkedin_outreach_queue table for managing LinkedIn outreach messages
-- with human-in-the-loop approval workflow.

CREATE TABLE linkedin_outreach_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    company VARCHAR(255) NOT NULL,
    contact_name VARCHAR(255) NOT NULL,
    contact_title VARCHAR(255),
    contact_linkedin_url TEXT,
    message TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending_approval'
        CHECK (status IN ('pending_approval', 'approved', 'sent', 'rejected', 'edited')),
    approved_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_loq_user_status ON linkedin_outreach_queue(user_id, status);
