DO $$ BEGIN
  IF (SELECT count(*) FROM information_schema.columns WHERE table_schema='public'
      AND table_name='extension_tasks' AND column_name IN ('review_hash','review_url',
      'review_expires_at','approved_at','submission_token_hash','submission_expires_at',
      'submission_reported_at')) <> 7 THEN
    RAISE EXCEPTION 'Approval columns missing';
  END IF;
  IF NOT (SELECT relrowsecurity FROM pg_class WHERE oid='public.extension_tasks'::regclass)
      OR NOT (SELECT payload->>'preserved' = 'true' FROM public.extension_tasks LIMIT 1) THEN
    RAISE EXCEPTION 'RLS or task data changed';
  END IF;
END $$;
