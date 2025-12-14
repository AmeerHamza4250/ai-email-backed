-- Migration: Add missing columns to campaign_leads table
-- Run this script to sync the database schema with the model

-- Add subject column
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'campaign_leads' 
        AND column_name = 'subject'
    ) THEN
        ALTER TABLE campaign_leads 
        ADD COLUMN subject VARCHAR(500);
        RAISE NOTICE 'Column subject added to campaign_leads table';
    END IF;
END $$;

-- Add body column
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'campaign_leads' 
        AND column_name = 'body'
    ) THEN
        ALTER TABLE campaign_leads 
        ADD COLUMN body TEXT;
        RAISE NOTICE 'Column body added to campaign_leads table';
    END IF;
END $$;

-- Add sent column
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'campaign_leads' 
        AND column_name = 'sent'
    ) THEN
        ALTER TABLE campaign_leads 
        ADD COLUMN sent BOOLEAN NOT NULL DEFAULT FALSE;
        RAISE NOTICE 'Column sent added to campaign_leads table';
    END IF;
END $$;

-- Add sent_at column
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'campaign_leads' 
        AND column_name = 'sent_at'
    ) THEN
        ALTER TABLE campaign_leads 
        ADD COLUMN sent_at TIMESTAMP WITH TIME ZONE;
        RAISE NOTICE 'Column sent_at added to campaign_leads table';
    END IF;
END $$;

-- Add opened column
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'campaign_leads' 
        AND column_name = 'opened'
    ) THEN
        ALTER TABLE campaign_leads 
        ADD COLUMN opened BOOLEAN NOT NULL DEFAULT FALSE;
        RAISE NOTICE 'Column opened added to campaign_leads table';
    END IF;
END $$;

-- Add clicked column
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'campaign_leads' 
        AND column_name = 'clicked'
    ) THEN
        ALTER TABLE campaign_leads 
        ADD COLUMN clicked BOOLEAN NOT NULL DEFAULT FALSE;
        RAISE NOTICE 'Column clicked added to campaign_leads table';
    END IF;
END $$;

-- Add replied column
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'campaign_leads' 
        AND column_name = 'replied'
    ) THEN
        ALTER TABLE campaign_leads 
        ADD COLUMN replied BOOLEAN NOT NULL DEFAULT FALSE;
        RAISE NOTICE 'Column replied added to campaign_leads table';
    END IF;
END $$;

-- Add bounced column
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'campaign_leads' 
        AND column_name = 'bounced'
    ) THEN
        ALTER TABLE campaign_leads 
        ADD COLUMN bounced BOOLEAN NOT NULL DEFAULT FALSE;
        RAISE NOTICE 'Column bounced added to campaign_leads table';
    END IF;
END $$;

-- Add resend_message_id column
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'campaign_leads' 
        AND column_name = 'resend_message_id'
    ) THEN
        ALTER TABLE campaign_leads 
        ADD COLUMN resend_message_id VARCHAR(255);
        RAISE NOTICE 'Column resend_message_id added to campaign_leads table';
    END IF;
END $$;
