-- PostgreSQL Script to Delete All Leads in "NEW" Stage and the Stage Itself
-- WARNING: This will permanently delete data. Make sure you have a backup!

-- ============================================
-- IDENTIFIED STAGES:
-- ID 6 = "New Lead" (sequence 0)
-- ID 8 = "Quality Lead" (sequence 1) - TARGET for reassignment
-- ID 1 = "New" (sequence 2) - TO DELETE
-- ID 3 = "Proposition" (sequence 4)
-- ID 4 = "Won" (sequence 5)
-- ============================================

-- ============================================
-- STEP 1: Check how many leads are in "New" stage (ID = 1) - TO DELETE
-- ============================================
SELECT COUNT(*) as leads_in_new_stage
FROM crm_lead 
WHERE stage_id = 1;

-- View the leads that will be reassigned
SELECT id, name, active, stage_id, create_date
FROM crm_lead 
WHERE stage_id = 1
ORDER BY create_date DESC;

-- This will show you:
-- 1. All stage IDs
-- 2. The exact format of the name field
-- 3. Which stage is the duplicate "NEW" one
-- 4. Which stage is the correct "New" one (usually sequence = 1)

-- ============================================
-- STEP 2: Check how many leads are in "NEW" stage
-- ============================================
-- Replace <NEW_STAGE_ID> with the actual ID from Step 1
-- SELECT COUNT(*) as total_leads_in_new_stage
-- FROM crm_lead 
-- WHERE stage_id = <NEW_STAGE_ID>;

-- ============================================
-- STEP 3: OPTION A - REASSIGN LEADS (Recommended - preserves data)
-- ============================================
-- This reassigns all leads from "NEW" stage to "New" stage (sequence 1)
-- Replace <NEW_STAGE_ID> with the "NEW" stage ID
-- Replace <CORRECT_NEW_STAGE_ID> with the correct "New" stage ID (usually sequence = 1)

-- Example (if NEW stage ID = 10 and correct New stage ID = 1):
-- UPDATE crm_lead 
-- SET stage_id = 1 
-- WHERE stage_id = 10;

-- ============================================
-- STEP 4: OPTION B - DELETE ALL LEADS (Destructive - use with caution)
-- ============================================
-- Only use this if you want to delete all leads in "NEW" stage
-- Replace <NEW_STAGE_ID> with the actual ID from Step 1
-- DELETE FROM crm_lead WHERE stage_id = <NEW_STAGE_ID>;

-- ============================================
-- STEP 5: Delete the "NEW" stage (after reassigning or deleting leads)
-- ============================================
-- Replace <NEW_STAGE_ID> with the actual ID from Step 1
-- DELETE FROM crm_stage WHERE id = <NEW_STAGE_ID>;

-- ============================================
-- COMPLETE AUTOMATED SOLUTION (Run all at once)
-- ============================================
-- This script automatically finds and handles everything:

-- Step 2: Check how many leads are in "NEW" stage (replace <STAGE_ID> with actual ID from Step 1)
-- First, find the stage ID manually, then use it below
-- SELECT COUNT(*) as total_leads_in_new_stage
-- FROM crm_lead 
-- WHERE stage_id = <STAGE_ID>;

-- Step 3: View the leads that will be deleted (replace <STAGE_ID> with actual ID)
-- SELECT id, name, active, stage_id, create_date
-- FROM crm_lead 
-- WHERE stage_id = <STAGE_ID>
-- ORDER BY create_date DESC;

-- Step 4: Delete all CRM leads in "NEW" stage (replace <STAGE_ID> with actual ID from Step 1)
-- This deletes leads regardless of their active status
-- DELETE FROM crm_lead WHERE stage_id = <STAGE_ID>;

-- Step 5: Delete the "NEW" stage itself (replace <STAGE_ID> with actual ID)
-- DELETE FROM crm_stage WHERE id = <STAGE_ID>;

-- ============================================
-- ALTERNATIVE: Using JSON operators (if name is JSON)
-- ============================================

-- Step 1 (Alternative): Find "NEW" stage using JSON query
SELECT id, name, sequence 
FROM crm_stage 
WHERE (name::jsonb ? 'en_US' AND name::jsonb->>'en_US' = 'NEW')
   OR (name::jsonb ? 'en' AND name::jsonb->>'en' = 'NEW')
   OR (name::text = 'NEW')
   OR (name::text LIKE '%"NEW"%');

-- Step 2 (Alternative): Delete leads using JSON query
-- DELETE FROM crm_lead 
-- WHERE stage_id IN (
--     SELECT id FROM crm_stage 
--     WHERE (name::jsonb ? 'en_US' AND name::jsonb->>'en_US' = 'NEW')
--        OR (name::jsonb ? 'en' AND name::jsonb->>'en' = 'NEW')
--        OR (name::text = 'NEW')
-- );

-- Step 3 (Alternative): Delete stage using JSON query
-- DELETE FROM crm_stage 
-- WHERE (name::jsonb ? 'en_US' AND name::jsonb->>'en_US' = 'NEW')
--    OR (name::jsonb ? 'en' AND name::jsonb->>'en' = 'NEW')
--    OR (name::text = 'NEW');

-- ============================================
-- SIMPLEST METHOD: Find by ID first, then delete
-- ============================================

-- Run this first to see all stages and find the "NEW" one:
SELECT id, name::text as stage_name, sequence 
FROM crm_stage 
ORDER BY sequence, id;

-- ============================================
-- AUTOMATED SOLUTION: Reassign and Delete (Recommended)
-- ============================================
-- This will:
-- 1. Find the "NEW" stage (the one to delete)
-- 2. Find the correct "New" stage (sequence = 1)
-- 3. Reassign all leads from "NEW" to "New"
-- 4. Delete the "NEW" stage

-- ============================================
-- STEP 2: Find stages with "NEW" in name (multiple methods)
-- ============================================
-- Try these queries to find the "NEW" stage:

-- Method 1: Direct text search
SELECT id, name::text, sequence 
FROM crm_stage 
WHERE name::text ILIKE '%new%';

-- Method 2: JSON search (if name is JSONB)
SELECT id, name, name::jsonb, sequence 
FROM crm_stage 
WHERE name::jsonb::text ILIKE '%new%';

-- Method 3: Check all stages and manually identify
SELECT id, name, sequence, 
       CASE WHEN sequence = 1 THEN 'CORRECT (sequence=1)' 
            WHEN sequence > 1 THEN 'POSSIBLE DUPLICATE' 
            ELSE 'OTHER' END as status
FROM crm_stage 
ORDER BY sequence, id;

-- ============================================
-- STEP 3: MANUAL METHOD - Use the ID directly
-- ============================================
-- After running Step 1, you'll see all stages.
-- Find the "NEW" stage ID manually, then use these commands:
-- Replace <NEW_STAGE_ID> with the actual ID
-- Replace <CORRECT_STAGE_ID> with the correct "New" stage ID (usually sequence=1)

-- Example (if NEW stage ID = 10 and correct New stage ID = 1):
-- UPDATE crm_lead SET stage_id = 1 WHERE stage_id = 10;
-- DELETE FROM crm_stage WHERE id = 10;

-- ============================================
-- STEP 2: REASSIGN LEADS AND DELETE "New" STAGE (ID = 1)
-- ============================================
-- Based on your stages:
-- - "New" stage ID = 1 (TO DELETE)
-- - "New Lead" stage ID = 6 (TARGET - sequence 0)

-- Step 2a: Reassign all leads from "New" (ID=1) to "New Lead" (ID=6)
UPDATE crm_lead 
SET stage_id = 6 
WHERE stage_id = 1;

-- Step 2b: Verify reassignment (should return 0)
SELECT COUNT(*) as remaining_leads_in_new_stage
FROM crm_lead 
WHERE stage_id = 1;

-- Step 2c: Delete the "New" stage (ID = 1)
DELETE FROM crm_stage WHERE id = 1;

-- Step 2d: Verify deletion (should return 0 rows)
SELECT id, name::text, sequence 
FROM crm_stage 
WHERE id = 1;

-- ============================================
-- STEP 3: ONE-COMMAND SOLUTION (Run all at once)
-- ============================================
-- This does everything in one transaction:

BEGIN;

-- Reassign all leads from "New" (ID=1) to "New Lead" (ID=6)
UPDATE crm_lead SET stage_id = 6 WHERE stage_id = 1;

-- Delete the "New" stage (ID = 1)
DELETE FROM crm_stage WHERE id = 1;

-- Verify (optional - check before committing)
-- SELECT COUNT(*) FROM crm_lead WHERE stage_id = 1;  -- Should be 0
-- SELECT COUNT(*) FROM crm_stage WHERE id = 1;       -- Should be 0

COMMIT;

-- ============================================
-- QUICK COPY-PASTE SOLUTION (Just run these 3 lines)
-- ============================================
-- UPDATE crm_lead SET stage_id = 6 WHERE stage_id = 1;
-- DELETE FROM crm_stage WHERE id = 1;
-- SELECT 'Done! "New" stage deleted and leads reassigned to "New Lead".' as result;

-- ============================================
-- FIX: Missing Record Error (crm.lead ID 18)
-- ============================================
-- If you're getting "Missing Record" error for lead ID 18, run these:

-- Step 1: Check if lead 18 exists and its current stage
SELECT id, name, stage_id, active, create_date
FROM crm_lead 
WHERE id = 18;

-- Step 2: Check if the stage_id is valid (exists in crm_stage)
SELECT 
    l.id as lead_id,
    l.name as lead_name,
    l.stage_id,
    s.id as stage_exists,
    s.name::text as stage_name
FROM crm_lead l
LEFT JOIN crm_stage s ON l.stage_id = s.id
WHERE l.id = 18;

-- Step 3: If stage_id is invalid (NULL in stage_exists), fix it:
-- Option A: Set to "New Lead" stage (ID = 6)
UPDATE crm_lead 
SET stage_id = 6 
WHERE id = 18 AND stage_id NOT IN (SELECT id FROM crm_stage);

-- Option B: Or set to any valid stage (first available)
-- UPDATE crm_lead 
-- SET stage_id = (SELECT id FROM crm_stage ORDER BY sequence LIMIT 1)
-- WHERE id = 18 AND stage_id NOT IN (SELECT id FROM crm_stage);

-- Step 4: Find ALL leads with invalid stage_id references
SELECT 
    l.id,
    l.name,
    l.stage_id as invalid_stage_id,
    l.active
FROM crm_lead l
WHERE l.stage_id IS NOT NULL 
  AND l.stage_id NOT IN (SELECT id FROM crm_stage);

-- Step 5: Fix ALL leads with invalid stage_id (set to "New Lead" ID = 6)
UPDATE crm_lead 
SET stage_id = 6 
WHERE stage_id IS NOT NULL 
  AND stage_id NOT IN (SELECT id FROM crm_stage);

-- Step 6: Verify fix
SELECT id, name, stage_id 
FROM crm_lead 
WHERE id = 18;

DO $$
DECLARE
    new_stage_id INTEGER;
    correct_new_stage_id INTEGER;
    leads_count INTEGER;
    stage_record RECORD;
BEGIN
    RAISE NOTICE 'Starting search for "NEW" stage...';
    
    -- Method 1: Try to find stage with "NEW" in name (case insensitive)
    FOR stage_record IN 
        SELECT id, name::text as name_text, sequence
        FROM crm_stage 
        WHERE name::text ILIKE '%new%'
        ORDER BY sequence DESC, id DESC
    LOOP
        RAISE NOTICE 'Found stage: ID=%, Name=%, Sequence=%', 
            stage_record.id, stage_record.name_text, stage_record.sequence;
        
        -- If sequence > 1, it's likely the duplicate
        IF stage_record.sequence > 1 AND new_stage_id IS NULL THEN
            new_stage_id := stage_record.id;
            RAISE NOTICE 'Selected as "NEW" stage (duplicate): ID=%', new_stage_id;
        END IF;
    END LOOP;
    
    -- Method 2: If not found, try JSON search
    IF new_stage_id IS NULL THEN
        FOR stage_record IN 
            SELECT id, name::jsonb::text as name_text, sequence
            FROM crm_stage 
            WHERE name::jsonb::text ILIKE '%new%'
            ORDER BY sequence DESC, id DESC
        LOOP
            IF stage_record.sequence > 1 AND new_stage_id IS NULL THEN
                new_stage_id := stage_record.id;
                RAISE NOTICE 'Selected as "NEW" stage (from JSON): ID=%', new_stage_id;
            END IF;
        END LOOP;
    END IF;
    
    -- Method 3: If still not found, show all stages and ask user to identify
    IF new_stage_id IS NULL THEN
        RAISE NOTICE 'Could not automatically find "NEW" stage.';
        RAISE NOTICE 'Please run this query to see all stages:';
        RAISE NOTICE 'SELECT id, name::text, sequence FROM crm_stage ORDER BY sequence, id;';
        RAISE NOTICE 'Then manually identify the "NEW" stage ID and use the manual method.';
        RETURN;
    END IF;
    
    -- Find the correct "New" stage (sequence = 1)
    SELECT id INTO correct_new_stage_id
    FROM crm_stage 
    WHERE sequence = 1
    ORDER BY id
    LIMIT 1;
    
    IF correct_new_stage_id IS NULL THEN
        RAISE NOTICE 'ERROR: Correct "New" stage (sequence=1) not found!';
        RETURN;
    END IF;
    
    -- Count leads in "NEW" stage
    SELECT COUNT(*) INTO leads_count
    FROM crm_lead 
    WHERE stage_id = new_stage_id;
    
    RAISE NOTICE '';
    RAISE NOTICE '=== EXECUTION PLAN ===';
    RAISE NOTICE 'Found "NEW" stage ID: %', new_stage_id;
    RAISE NOTICE 'Found correct "New" stage ID: %', correct_new_stage_id;
    RAISE NOTICE 'Leads to reassign: %', leads_count;
    RAISE NOTICE '';
    
    -- Reassign all leads from "NEW" to "New"
    UPDATE crm_lead 
    SET stage_id = correct_new_stage_id 
    WHERE stage_id = new_stage_id;
    
    RAISE NOTICE 'Reassigned % leads', leads_count;
    
    -- Delete the "NEW" stage
    DELETE FROM crm_stage WHERE id = new_stage_id;
    
    RAISE NOTICE 'Deleted "NEW" stage (ID: %)', new_stage_id;
    RAISE NOTICE '';
    RAISE NOTICE 'SUCCESS: Operation completed!';
END $$;

-- ============================================
-- ALTERNATIVE: Delete All Leads (Destructive)
-- ============================================
-- Use this ONLY if you want to delete all leads in "NEW" stage
-- Uncomment and run:

-- DO $$
-- DECLARE
--     new_stage_id INTEGER;
--     leads_count INTEGER;
-- BEGIN
--     -- Find the "NEW" stage
--     SELECT id INTO new_stage_id
--     FROM crm_stage 
--     WHERE name::text LIKE '%NEW%' OR name::text = '"NEW"'
--     ORDER BY sequence DESC
--     LIMIT 1;
--     
--     IF new_stage_id IS NULL THEN
--         RAISE NOTICE 'ERROR: "NEW" stage not found!';
--         RETURN;
--     END IF;
--     
--     -- Count leads
--     SELECT COUNT(*) INTO leads_count
--     FROM crm_lead 
--     WHERE stage_id = new_stage_id;
--     
--     RAISE NOTICE 'Found "NEW" stage ID: %', new_stage_id;
--     RAISE NOTICE 'Leads to delete: %', leads_count;
--     
--     -- Delete all leads
--     DELETE FROM crm_lead WHERE stage_id = new_stage_id;
--     
--     RAISE NOTICE 'Deleted % leads', leads_count;
--     
--     -- Delete the stage
--     DELETE FROM crm_stage WHERE id = new_stage_id;
--     
--     RAISE NOTICE 'Deleted "NEW" stage (ID: %)', new_stage_id;
--     RAISE NOTICE 'SUCCESS: Operation completed!';
-- END $$;

-- ============================================
-- Optional: Clean up orphaned related records
-- ============================================
-- DELETE FROM mail_message 
-- WHERE model = 'crm.lead' 
-- AND res_id NOT IN (SELECT id FROM crm_lead);

-- DELETE FROM mail_activity 
-- WHERE res_model = 'crm.lead' 
-- AND res_id NOT IN (SELECT id FROM crm_lead);

